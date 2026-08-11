"""Permissions, path allowlists, and dangerous-command denylist."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from jarvis.security.paths import assert_allowed, is_forbidden_command
from jarvis.security.permissions import PermissionGate, PermissionLevel


class PathTests(unittest.TestCase):
    def test_sandbox_escape_denied(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "sandbox"
            root.mkdir()
            with self.assertRaises(PermissionError):
                assert_allowed((root / ".." / "outside.txt").resolve(), (root,))

    def test_inside_sandbox_ok(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "sandbox"
            (root / "a").mkdir(parents=True)
            resolved = assert_allowed(root / "a", (root,))
            self.assertTrue(str(resolved).startswith(str(root.resolve())))


class CommandDenyTests(unittest.TestCase):
    def test_rm_rf_root_denied(self) -> None:
        self.assertTrue(is_forbidden_command("rm -rf /"))
        self.assertTrue(is_forbidden_command("sudo apt install evil"))
        self.assertFalse(is_forbidden_command("ls -la"))


class ConfirmTests(unittest.TestCase):
    def test_sensitive_allowed_after_confirm(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            audit = Path(tmp) / "audit.jsonl"
            gate = PermissionGate(audit_path=audit, confirm_fn=lambda _p: True)
            denied = gate.check("send_email", PermissionLevel.SENSITIVE)
            self.assertFalse(denied.allowed)
            allowed = gate.authorize("send_email", PermissionLevel.SENSITIVE, detail={"to": "a@b.c"})
            self.assertTrue(allowed.allowed)
            lines = audit.read_text(encoding="utf-8").strip().splitlines()
            self.assertGreaterEqual(len(lines), 2)
            self.assertTrue(json.loads(lines[-1])["allowed"])


if __name__ == "__main__":
    unittest.main()
