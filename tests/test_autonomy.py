"""Quiet hours, rate limits, and event dispositions."""

from __future__ import annotations

import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace

from jarvis.autonomy.policy import LOG, SPEAK, WAIT, decide, in_quiet_hours
from jarvis.memory.store import MemoryStore
from jarvis.perception.events import Event, EventBus


class QuietHoursTests(unittest.TestCase):
    def test_overnight_window(self) -> None:
        settings = SimpleNamespace(quiet_hours_start=22, quiet_hours_end=7)
        self.assertTrue(in_quiet_hours(settings, datetime(2026, 1, 1, 23, 0)))  # type: ignore[arg-type]
        self.assertTrue(in_quiet_hours(settings, datetime(2026, 1, 1, 3, 0)))  # type: ignore[arg-type]
        self.assertFalse(in_quiet_hours(settings, datetime(2026, 1, 1, 10, 0)))  # type: ignore[arg-type]


class DecideTests(unittest.TestCase):
    def test_low_importance_is_logged(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            memory = MemoryStore(Path(tmp) / "m.db")
            settings = SimpleNamespace(
                quiet_hours_start=22,
                quiet_hours_end=7,
                importance_threshold=0.6,
                max_proactive_per_hour=4,
            )
            event = Event("disk", {"free_gb": 80}, importance=0.1)
            self.assertEqual(decide(event, settings, memory, now=datetime(2026, 1, 1, 10)), LOG)  # type: ignore[arg-type]

    def test_important_daytime_speaks(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            memory = MemoryStore(Path(tmp) / "m.db")
            settings = SimpleNamespace(
                quiet_hours_start=22,
                quiet_hours_end=7,
                importance_threshold=0.6,
                max_proactive_per_hour=4,
            )
            event = Event("battery", {"percent": 8}, importance=0.9)
            self.assertEqual(
                decide(event, settings, memory, now=datetime(2026, 1, 1, 15)),  # type: ignore[arg-type]
                SPEAK,
            )

    def test_quiet_hours_wait(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            memory = MemoryStore(Path(tmp) / "m.db")
            settings = SimpleNamespace(
                quiet_hours_start=22,
                quiet_hours_end=7,
                importance_threshold=0.6,
                max_proactive_per_hour=4,
            )
            event = Event("battery", {"percent": 8}, importance=0.9)
            self.assertEqual(
                decide(event, settings, memory, now=datetime(2026, 1, 1, 23)),  # type: ignore[arg-type]
                WAIT,
            )


class EventBusTests(unittest.TestCase):
    def test_wildcard_receives_events(self) -> None:
        bus = EventBus()
        seen: list[str] = []
        bus.subscribe("*", lambda e: seen.append(e.kind))
        bus.emit(Event("battery", {"percent": 12}, importance=0.9))
        self.assertEqual(seen, ["battery"])


if __name__ == "__main__":
    unittest.main()
