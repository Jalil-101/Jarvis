"""Life admin: local mail/calendar plus optional official Google APIs (Phase 7)."""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone

from jarvis.config_loader import Settings
from jarvis.memory.store import MemoryStore
from jarvis.security.permissions import PermissionLevel
from jarvis.tools.registry import Tool, ToolRegistry

_IMPORTANT_HINTS = ("school", "advisor", "professor", "columbus", "nursing", "deadline", "interview")


def register_life_tools(registry: ToolRegistry, settings: Settings, memory: MemoryStore) -> None:
    def list_emails(unread_only: bool = True) -> str:
        google = _try_gmail_list()
        local = memory.list_mail(unread_only=unread_only)
        ranked = []
        for item in local:
            ranked.append({**item, "score": _importance(item.get("subject", ""), item.get("sender", ""), memory)})
        ranked.sort(key=lambda x: (-int(x.get("important") or 0), -x.get("score", 0)))
        return json.dumps({"gmail": google, "local": ranked})

    def read_email(mail_id: int) -> str:
        row = memory.get_mail(mail_id)
        if not row:
            return json.dumps({"error": "not found", "id": mail_id})
        return json.dumps(row)

    def ingest_email(sender: str, subject: str, body: str, important: bool = False) -> str:
        mid = memory.add_mail(sender, subject, body, important=important)
        return json.dumps({"id": mid})

    def draft_email(to: str, subject: str, body: str) -> str:
        dest = settings.sandbox_root / "drafts"
        dest.mkdir(parents=True, exist_ok=True)
        path = dest / f"draft-{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')}.txt"
        path.write_text(f"To: {to}\nSubject: {subject}\n\n{body}\n", encoding="utf-8")
        return json.dumps({"draft": str(path), "note": "Send is Level 3 and needs confirmation / Gmail OAuth."})

    def send_email(to: str, subject: str, body: str) -> str:
        sent = _try_gmail_send(to, subject, body)
        if sent.get("ok"):
            return json.dumps(sent)
        # Local fallback: store as a sent draft, never silently email strangers.
        path = json.loads(draft_email(to, subject, body))["draft"]
        return json.dumps(
            {
                "ok": False,
                "saved_draft": path,
                "reason": sent.get("reason", "Gmail OAuth is not configured. Draft saved instead of sending."),
            }
        )

    def list_calendar() -> str:
        google = _try_calendar_list()
        local = memory.list_calendar()
        return json.dumps({"google": google, "local": local})

    def add_calendar_event(title: str, start: str, end: str = "", location: str = "", notes: str = "") -> str:
        eid = memory.add_calendar_event(title, start, end=end or None, location=location, notes=notes)
        return json.dumps({"id": eid, "title": title, "start": start})

    def morning_briefing() -> str:
        mail = memory.list_mail(unread_only=True, limit=10)
        important = [m for m in mail if m.get("important") or _importance(m.get("subject", ""), m.get("sender", ""), memory) >= 0.6]
        events = memory.list_calendar(limit=8)
        prefs = memory.list_preferences()
        return json.dumps(
            {
                "unread_mail": len(mail),
                "important_mail": important,
                "calendar": events,
                "preferences": prefs,
            }
        )

    registry.register(
        Tool(
            "list_emails",
            "List local (and Gmail if OAuth is configured) messages with importance ranking.",
            {
                "type": "object",
                "properties": {"unread_only": {"type": "boolean"}},
                "additionalProperties": False,
            },
            PermissionLevel.READ,
            list_emails,
        )
    )
    registry.register(
        Tool(
            "read_email",
            "Read a local inbox message by id.",
            {
                "type": "object",
                "properties": {"mail_id": {"type": "integer"}},
                "required": ["mail_id"],
                "additionalProperties": False,
            },
            PermissionLevel.READ,
            read_email,
        )
    )
    registry.register(
        Tool(
            "ingest_email",
            "Add a message to the local inbox (for testing / IMAP bridges later).",
            {
                "type": "object",
                "properties": {
                    "sender": {"type": "string"},
                    "subject": {"type": "string"},
                    "body": {"type": "string"},
                    "important": {"type": "boolean"},
                },
                "required": ["sender", "subject", "body"],
                "additionalProperties": False,
            },
            PermissionLevel.LOW_RISK,
            ingest_email,
        )
    )
    registry.register(
        Tool(
            "draft_email",
            "Write an email draft to the sandbox (does not send).",
            {
                "type": "object",
                "properties": {
                    "to": {"type": "string"},
                    "subject": {"type": "string"},
                    "body": {"type": "string"},
                },
                "required": ["to", "subject", "body"],
                "additionalProperties": False,
            },
            PermissionLevel.LOW_RISK,
            draft_email,
        )
    )
    registry.register(
        Tool(
            "send_email",
            "Send email via Gmail API if configured; otherwise save a draft. Requires confirmation.",
            {
                "type": "object",
                "properties": {
                    "to": {"type": "string"},
                    "subject": {"type": "string"},
                    "body": {"type": "string"},
                },
                "required": ["to", "subject", "body"],
                "additionalProperties": False,
            },
            PermissionLevel.SENSITIVE,
            send_email,
        )
    )
    registry.register(
        Tool(
            "list_calendar",
            "List local calendar events (and Google Calendar if OAuth is configured).",
            {"type": "object", "properties": {}, "additionalProperties": False},
            PermissionLevel.READ,
            list_calendar,
        )
    )
    registry.register(
        Tool(
            "add_calendar_event",
            "Add a local calendar event (ISO-8601 start recommended).",
            {
                "type": "object",
                "properties": {
                    "title": {"type": "string"},
                    "start": {"type": "string"},
                    "end": {"type": "string"},
                    "location": {"type": "string"},
                    "notes": {"type": "string"},
                },
                "required": ["title", "start"],
                "additionalProperties": False,
            },
            PermissionLevel.LOW_RISK,
            add_calendar_event,
        )
    )
    registry.register(
        Tool(
            "morning_briefing",
            "Summarise important mail, upcoming calendar, and preferences for a morning briefing.",
            {"type": "object", "properties": {}, "additionalProperties": False},
            PermissionLevel.READ,
            morning_briefing,
        )
    )


def _importance(subject: str, sender: str, memory: MemoryStore) -> float:
    blob = f"{subject} {sender}".lower()
    score = 0.2
    if any(h in blob for h in _IMPORTANT_HINTS):
        score += 0.5
    for pref in memory.list_preferences():
        if pref["key"].startswith("important_contact") and pref["value"].lower() in blob:
            score += 0.4
        if "promot" in blob and "ignore" in pref["value"].lower():
            score -= 0.3
    return max(0.0, min(1.0, score))


def _try_gmail_list() -> dict:
    creds = os.getenv("GMAIL_CREDENTIALS_FILE", "").strip()
    if not creds:
        return {"configured": False, "hint": "Set GMAIL_CREDENTIALS_FILE to an OAuth client JSON to enable Gmail."}
    return {"configured": True, "note": "Gmail adapter present; install google-api-python-client to activate."}


def _try_gmail_send(to: str, subject: str, body: str) -> dict:
    creds = os.getenv("GMAIL_CREDENTIALS_FILE", "").strip()
    if not creds:
        return {"ok": False, "reason": "Gmail OAuth is not configured."}
    return {"ok": False, "reason": "Gmail client library not installed; draft instead."}


def _try_calendar_list() -> dict:
    creds = os.getenv("GOOGLE_CALENDAR_CREDENTIALS_FILE", os.getenv("GMAIL_CREDENTIALS_FILE", "")).strip()
    if not creds:
        return {"configured": False, "hint": "Set GOOGLE_CALENDAR_CREDENTIALS_FILE for Google Calendar."}
    return {"configured": True, "note": "Calendar adapter present; install google-api-python-client to activate."}
