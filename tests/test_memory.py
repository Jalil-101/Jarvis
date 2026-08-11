"""Long-term memory types and retrieval (no API key)."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from jarvis.memory.embeddings import cosine, embed
from jarvis.memory.store import MemoryStore


class EmbeddingTests(unittest.TestCase):
    def test_similar_text_scores_higher_than_unrelated(self) -> None:
        a = embed("Sarah is Abdul's academic advisor at Columbus State.")
        b = embed("What did Sarah say about the nursing application?")
        c = embed("The weather in Tokyo is humid.")
        self.assertGreater(cosine(a, b), cosine(a, c))


class MemoryKindTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.store = MemoryStore(Path(self.tmp.name) / "m.db")

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_people_projects_preferences_episodes(self) -> None:
        self.store.upsert_person("Sarah", relation="advisor", notes="Nursing application")
        self.store.upsert_project("ShipLink", stack="Node.js Express MongoDB", notes="mobile app")
        self.store.set_preference("email_style", "concise")
        self.store.add_episode("Worked on the Jarvis project.")
        self.store.add_semantic("Abdul uses Cursor and VS Code.")

        person = self.store.get_person("Sarah")
        self.assertIsNotNone(person)
        assert person is not None
        self.assertEqual(person["relation"], "advisor")

        brief = self.store.recall("Sarah nursing")
        self.assertIn("Sarah", brief)
        self.assertIn("nursing", brief.lower())

        prefs = self.store.list_preferences()
        self.assertEqual(prefs[0]["value"], "concise")

    def test_forget_and_export(self) -> None:
        self.store.add_semantic("temporary secret")
        self.assertGreater(self.store.forget(kind="fact", query="temporary secret"), 0)
        exported = self.store.export_all()
        self.assertIn("facts", exported)
        self.assertTrue(all("temporary secret" not in f["content"] for f in exported["facts"]))


if __name__ == "__main__":
    unittest.main()
