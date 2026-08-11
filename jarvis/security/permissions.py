"""Permission gate and audit log (Levels 0–4)."""

from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import IntEnum
from pathlib import Path
from typing import Any


class PermissionLevel(IntEnum):
    """Capability tiers — higher means more dangerous."""

    READ = 0
    SUGGEST = 1
    LOW_RISK = 2
    SENSITIVE = 3
    DANGEROUS = 4


@dataclass(frozen=True)
class PermissionDecision:
    allowed: bool
    level: PermissionLevel
    reason: str
    requires_confirm: bool = False


ConfirmFn = Callable[[str], bool]


class PermissionGate:
    """Gate tool calls by level; write every decision to the audit log."""

    def __init__(
        self,
        *,
        audit_path: Path | str,
        max_autonomous_level: PermissionLevel | int = PermissionLevel.LOW_RISK,
        confirm_fn: ConfirmFn | None = None,
    ) -> None:
        self.audit_path = Path(audit_path)
        self.audit_path.parent.mkdir(parents=True, exist_ok=True)
        self.max_autonomous_level = PermissionLevel(int(max_autonomous_level))
        self.confirm_fn = confirm_fn

    def check(
        self,
        tool_name: str,
        level: PermissionLevel | int,
        *,
        detail: dict[str, Any] | None = None,
        confirmed: bool = False,
    ) -> PermissionDecision:
        level = PermissionLevel(int(level))
        detail = detail or {}

        if level >= PermissionLevel.SENSITIVE and not confirmed:
            decision = PermissionDecision(
                allowed=False,
                level=level,
                reason=f"{level.name} actions require user confirmation.",
                requires_confirm=True,
            )
        elif level > self.max_autonomous_level and not confirmed:
            decision = PermissionDecision(
                allowed=False,
                level=level,
                reason=f"Level {level.name} exceeds autonomous max {self.max_autonomous_level.name}.",
                requires_confirm=True,
            )
        else:
            extra = " (explicitly confirmed)" if confirmed else ""
            decision = PermissionDecision(
                allowed=True,
                level=level,
                reason=f"Within autonomous policy{extra}.",
                requires_confirm=False,
            )
        self.record(tool_name, decision, detail=detail)
        return decision

    def authorize(
        self,
        tool_name: str,
        level: PermissionLevel | int,
        *,
        detail: dict[str, Any] | None = None,
    ) -> PermissionDecision:
        """Check, and if confirmation is required, ask via confirm_fn."""
        decision = self.check(tool_name, level, detail=detail)
        if decision.allowed:
            return decision
        if decision.requires_confirm and self.confirm_fn is not None:
            prompt = f"Allow {tool_name} ({PermissionLevel(int(level)).name})"
            if detail:
                prompt += f": {detail}"
            prompt += "?"
            if self.confirm_fn(prompt):
                return self.check(tool_name, level, detail=detail, confirmed=True)
        return decision

    def record(
        self,
        tool_name: str,
        decision: PermissionDecision,
        *,
        detail: dict[str, Any] | None = None,
    ) -> None:
        entry = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "tool": tool_name,
            "level": int(decision.level),
            "level_name": decision.level.name,
            "allowed": decision.allowed,
            "requires_confirm": decision.requires_confirm,
            "reason": decision.reason,
            "detail": _safe_detail(detail or {}),
        }
        with self.audit_path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(entry, ensure_ascii=False) + "\n")


def _safe_detail(detail: dict[str, Any]) -> dict[str, Any]:
    redacted = {}
    for key, value in detail.items():
        lowered = str(key).lower()
        if any(s in lowered for s in ("password", "secret", "token", "api_key", "authorization")):
            redacted[key] = "[redacted]"
        else:
            redacted[key] = value if isinstance(value, (str, int, float, bool, list, dict)) or value is None else str(value)
    return redacted
