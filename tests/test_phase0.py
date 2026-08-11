"""Smoke tests for Phase 0 memory + permissions (no API key required)."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from jarvis.memory.store import MemoryStore
from jarvis.security.permissions import PermissionGate, PermissionLevel


class MemoryStoreTests(unittest.TestCase):
    def test_append_and_load_turns(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "test.db"
            store = MemoryStore(db)
            store.append_turn("s1", "user", "Hello")
            store.append_turn("s1", "assistant", "Good evening.")
            msgs = store.load_messages("s1")
            self.assertEqual(len(msgs), 2)
            self.assertEqual(msgs[0]["role"], "user")
            self.assertEqual(msgs[1]["content"], "Good evening.")


class PermissionGateTests(unittest.TestCase):
    def test_low_risk_allowed_and_audited(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            audit = Path(tmp) / "audit.jsonl"
            gate = PermissionGate(audit_path=audit)
            decision = gate.check("list_dir", PermissionLevel.READ, detail={"path": "."})
            self.assertTrue(decision.allowed)
            lines = audit.read_text(encoding="utf-8").strip().splitlines()
            self.assertEqual(len(lines), 1)
            entry = json.loads(lines[0])
            self.assertEqual(entry["tool"], "list_dir")
            self.assertTrue(entry["allowed"])

    def test_sensitive_requires_confirm(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            audit = Path(tmp) / "audit.jsonl"
            gate = PermissionGate(audit_path=audit)
            decision = gate.check("send_email", PermissionLevel.SENSITIVE)
            self.assertFalse(decision.allowed)
            self.assertTrue(decision.requires_confirm)


if __name__ == "__main__":
    unittest.main()
