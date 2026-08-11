"""Permission gate and audit log stubs (Levels 0–4)."""

from __future__ import annotations

import json
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


class PermissionGate:
    """Gate tool calls by level; write every decision to the audit log.

    Phase 0: stubs only. Week 3 tools will call ``check`` / ``record``.
    """

    def __init__(
        self,
        *,
        audit_path: Path | str,
        max_autonomous_level: PermissionLevel = PermissionLevel.LOW_RISK,
    ) -> None:
        self.audit_path = Path(audit_path)
        self.audit_path.parent.mkdir(parents=True, exist_ok=True)
        self.max_autonomous_level = max_autonomous_level

    def check(
        self,
        tool_name: str,
        level: PermissionLevel,
        *,
        detail: dict[str, Any] | None = None,
    ) -> PermissionDecision:
        detail = detail or {}
        if level >= PermissionLevel.DANGEROUS:
            decision = PermissionDecision(
                allowed=False,
                level=level,
                reason="Dangerous actions require explicit confirm + audit (not yet implemented).",
                requires_confirm=True,
            )
        elif level >= PermissionLevel.SENSITIVE:
            decision = PermissionDecision(
                allowed=False,
                level=level,
                reason="Sensitive actions require user confirmation.",
                requires_confirm=True,
            )
        elif level > self.max_autonomous_level:
            decision = PermissionDecision(
                allowed=False,
                level=level,
                reason=f"Level {level.name} exceeds autonomous max {self.max_autonomous_level.name}.",
                requires_confirm=True,
            )
        else:
            decision = PermissionDecision(
                allowed=True,
                level=level,
                reason="Within autonomous policy.",
            )
        self.record(tool_name, decision, detail=detail)
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
            "detail": detail or {},
        }
        with self.audit_path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(entry, ensure_ascii=False) + "\n")
