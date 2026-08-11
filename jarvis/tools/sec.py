"""Controlled security toolkit (Phase 9). Localhost / allowlisted targets only."""

from __future__ import annotations

import json
import shutil
import socket
import subprocess
import sys
from urllib.parse import urlparse

from jarvis.config_loader import Settings
from jarvis.security.permissions import PermissionLevel
from jarvis.tools.registry import Tool, ToolRegistry

_LOCAL_HOSTS = {"localhost", "127.0.0.1", "::1", "0.0.0.0"}


def register_security_tools(registry: ToolRegistry, settings: Settings) -> None:
    def list_listening_ports() -> str:
        if shutil.which("ss"):
            cmd = ["ss", "-lntup"]
        elif shutil.which("netstat"):
            cmd = ["netstat", "-ano"] if sys.platform.startswith("win") else ["netstat", "-lntup"]
        else:
            return json.dumps({"error": "Neither ss nor netstat is available."})
        completed = subprocess.run(cmd, capture_output=True, text=True, timeout=15, check=False)
        return json.dumps(
            {
                "command": cmd,
                "returncode": completed.returncode,
                "stdout": (completed.stdout or "")[-8000:],
                "stderr": (completed.stderr or "")[-1000:],
            }
        )

    def nmap_scan(target: str = "127.0.0.1", ports: str = "22,80,443,3000,8000,8080") -> str:
        host = _normalise_target(target)
        if host not in _LOCAL_HOSTS and host != socket.gethostname().lower():
            raise PermissionError(
                "nmap_scan is limited to localhost / this machine. "
                "Remote scanning is not enabled in this controlled toolkit."
            )
        nmap = shutil.which("nmap")
        if not nmap:
            return json.dumps(
                {
                    "error": "nmap is not installed",
                    "fallback": json.loads(list_listening_ports()),
                }
            )
        if not _safe_ports(ports):
            raise ValueError("ports must be a comma-separated list of integers.")
        cmd = [nmap, "-Pn", "-sT", "-p", ports, host]
        completed = subprocess.run(cmd, capture_output=True, text=True, timeout=60, check=False)
        return json.dumps(
            {
                "command": cmd,
                "returncode": completed.returncode,
                "stdout": completed.stdout[-8000:],
                "stderr": completed.stderr[-2000:],
            }
        )

    registry.register(
        Tool(
            "list_listening_ports",
            "List listening TCP/UDP services on this machine (ss or netstat). Read-only.",
            {"type": "object", "properties": {}, "additionalProperties": False},
            PermissionLevel.READ,
            list_listening_ports,
        )
    )
    registry.register(
        Tool(
            "nmap_scan",
            "Run a fast TCP connect scan of localhost only. Requires confirmation. Not a general attack tool.",
            {
                "type": "object",
                "properties": {
                    "target": {"type": "string", "description": "Must be localhost / 127.0.0.1"},
                    "ports": {"type": "string", "description": "Comma-separated ports"},
                },
                "additionalProperties": False,
            },
            PermissionLevel.SENSITIVE,
            nmap_scan,
        )
    )


def _normalise_target(target: str) -> str:
    raw = target.strip().lower()
    if "://" in raw:
        raw = urlparse(raw).hostname or raw
    return raw.split("%")[0]


def _safe_ports(ports: str) -> bool:
    parts = [p.strip() for p in ports.split(",") if p.strip()]
    if not parts or len(parts) > 50:
        return False
    return all(p.isdigit() and 1 <= int(p) <= 65535 for p in parts)
