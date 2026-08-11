"""Sandbox tools, research parsers, and security toolkit limits."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from jarvis.config_loader import get_settings
from jarvis.memory.store import MemoryStore
from jarvis.security.permissions import PermissionGate
from jarvis.tools import build_registry
from jarvis.tools.web import _html_to_text, _parse_ddg


class SandboxToolTests(unittest.TestCase):
    def test_create_and_list_folder(self) -> None:
        settings = get_settings()
        with tempfile.TemporaryDirectory() as tmp:
            memory = MemoryStore(Path(tmp) / "m.db")
            gate = PermissionGate(audit_path=Path(tmp) / "audit.jsonl")
            registry = build_registry(settings, memory, gate)
            created = json.loads(registry.execute("create_folder", {"path": "day30-demo"}))
            self.assertIn("created", created)
            listed = json.loads(registry.execute("list_sandbox", {"path": "."}))
            names = [e["name"] for e in listed.get("entries", [])]
            self.assertIn("day30-demo", names)

    def test_path_escape_create_folder(self) -> None:
        settings = get_settings()
        with tempfile.TemporaryDirectory() as tmp:
            memory = MemoryStore(Path(tmp) / "m.db")
            gate = PermissionGate(audit_path=Path(tmp) / "audit.jsonl")
            registry = build_registry(settings, memory, gate)
            result = json.loads(registry.execute("create_folder", {"path": "../../outside"}))
            self.assertIn("error", result)

    def test_remember_tool(self) -> None:
        settings = get_settings()
        with tempfile.TemporaryDirectory() as tmp:
            memory = MemoryStore(Path(tmp) / "m.db")
            gate = PermissionGate(audit_path=Path(tmp) / "audit.jsonl")
            registry = build_registry(settings, memory, gate)
            registry.execute("remember", {"content": "The advisor is Sarah."})
            recalled = json.loads(registry.execute("recall", {"query": "advisor Sarah"}))
            self.assertIn("Sarah", recalled["matches"])


class ResearchParseTests(unittest.TestCase):
    def test_html_to_text_strips_scripts(self) -> None:
        html = "<html><script>alert(1)</script><p>Hello Jarvis</p></html>"
        text = _html_to_text(html)
        self.assertIn("Hello Jarvis", text)
        self.assertNotIn("alert", text)

    def test_ddg_parse(self) -> None:
        html = """
        <a class="result__a" href="https://example.com/nav">React Navigation</a>
        <a class="result__snippet">Compare stack vs tabs</a>
        """
        results = _parse_ddg(html, max_results=3)
        self.assertTrue(results)
        self.assertIn("example.com", results[0]["url"])


class NmapLimitTests(unittest.TestCase):
    def test_remote_target_denied_even_when_confirmed(self) -> None:
        settings = get_settings()
        with tempfile.TemporaryDirectory() as tmp:
            memory = MemoryStore(Path(tmp) / "m.db")
            gate = PermissionGate(audit_path=Path(tmp) / "audit.jsonl", confirm_fn=lambda _p: True)
            registry = build_registry(settings, memory, gate)
            result = json.loads(registry.execute("nmap_scan", {"target": "8.8.8.8"}))
            self.assertIn("error", result)
            self.assertIn("localhost", result["error"].lower())


if __name__ == "__main__":
    unittest.main()
