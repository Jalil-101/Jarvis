"""Memory extraction heuristics used by the agent."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock

from jarvis.core.agent import Agent
from jarvis.memory.store import MemoryStore


class MemoryExtractTests(unittest.TestCase):
    def test_remember_that_stores_fact(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            memory = MemoryStore(Path(tmp) / "m.db")
            agent = object.__new__(Agent)
            agent.memory = memory
            agent.session_id = "t1"
            agent._maybe_extract("Remember that my favorite drink is tea.")
            brief = memory.recall("favorite drink tea")
            self.assertIn("tea", brief.lower())

    def test_favorite_sets_preference(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            memory = MemoryStore(Path(tmp) / "m.db")
            agent = object.__new__(Agent)
            agent.memory = memory
            agent.session_id = "t2"
            agent._maybe_extract("my favorite color is blue")
            prefs = {p["key"]: p["value"] for p in memory.list_preferences()}
            self.assertEqual(prefs.get("favorite.color"), "blue")


class AllowlistWindowsTests(unittest.TestCase):
    def test_windows_has_date_and_disk(self) -> None:
        import sys

        from jarvis.config_loader import get_settings, reset_settings_cache

        reset_settings_cache()
        settings = get_settings()
        self.assertIn("whoami", settings.allowlisted_commands)
        self.assertIn("python_version", settings.allowlisted_commands)
        self.assertIn("date", settings.allowlisted_commands)
        self.assertIn("disk", settings.allowlisted_commands)
        if sys.platform.startswith("win"):
            self.assertEqual(settings.allowlisted_commands["date"][0], "cmd")


if __name__ == "__main__":
    unittest.main()
