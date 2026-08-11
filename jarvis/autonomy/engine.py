"""Autonomy engine: watchers + scheduled jobs + interrupt policy."""

from __future__ import annotations

import time
from datetime import datetime, timezone

from jarvis.config_loader import get_settings
from jarvis.autonomy.policy import LOG, SPEAK, WAIT, decide
from jarvis.memory.store import MemoryStore
from jarvis.perception.events import Event, EventBus
from jarvis.perception.watchers import poll_battery, poll_disk


class AutonomyEngine:
    def __init__(self, *, memory: MemoryStore | None = None) -> None:
        self.settings = get_settings()
        self.memory = memory or MemoryStore(self.settings.db_path)
        self.bus = EventBus()
        self.bus.subscribe("*", self._on_event)  # all events
        self._last_briefing_date = ""

    def _on_event(self, event: Event) -> None:
        disposition = decide(event, self.settings, self.memory)
        self.memory.log_event(event.kind, event.payload, importance=event.importance, disposition=disposition)
        if disposition == SPEAK:
            text = self._render(event)
            print(f"[Jarvis] {text}")
            try:
                from jarvis.voice.tts import speak

                speak(text)
            except Exception as exc:  # noqa: BLE001
                print(f"(TTS skipped: {exc})")
        elif disposition == WAIT:
            print(f"[queued] {event.kind} {event.payload}")
        else:
            print(f"[log] {event.kind}")

    def _render(self, event: Event) -> str:
        if event.kind == "battery":
            return f"Your battery is at {event.payload.get('percent')} percent."
        if event.kind == "disk":
            return f"Disk space is getting low: {event.payload.get('free_gb')} gigabytes free."
        if event.kind == "schedule" and event.payload.get("name") == "morning":
            return "Good morning. Shall I give you the briefing?"
        return f"Something needs your attention: {event.kind}."

    def tick(self) -> None:
        poll_battery(self.bus)
        poll_disk(self.bus, self.settings.data_dir)
        today = datetime.now().date().isoformat()
        hour = datetime.now().hour
        if hour == 8 and self._last_briefing_date != today:
            self._last_briefing_date = today
            self.bus.emit(Event("schedule", {"name": "morning"}, importance=0.75))
        self._run_due_jobs()

    def _run_due_jobs(self) -> None:
        now = datetime.now(timezone.utc)
        for job in self.memory.list_jobs():
            if not job.get("enabled"):
                continue
            run_at = job.get("run_at")
            if run_at and run_at <= now.isoformat():
                self.bus.emit(
                    Event("schedule", {"name": job["name"], "action": job["action"]}, importance=0.7)
                )

    def run_forever(self, *, interval_seconds: float = 60) -> None:
        print("Autonomy engine running. Ctrl+C to stop.")
        while True:
            try:
                self.tick()
                time.sleep(interval_seconds)
            except KeyboardInterrupt:
                print("Autonomy engine stopped.")
                break
