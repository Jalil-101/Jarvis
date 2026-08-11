"""Schedule jobs through the tool registry (Phase 8)."""

from __future__ import annotations

import json

from jarvis.memory.store import MemoryStore
from jarvis.security.permissions import PermissionLevel
from jarvis.tools.registry import Tool, ToolRegistry


def register_job_tools(registry: ToolRegistry, memory: MemoryStore) -> None:
    def schedule_job(name: str, action: str, run_at: str = "", cron_expr: str = "") -> str:
        jid = memory.add_job(name, action, cron_expr=cron_expr or None, run_at=run_at or None)
        return json.dumps({"id": jid, "name": name})

    def list_jobs() -> str:
        return json.dumps(memory.list_jobs())

    registry.register(
        Tool(
            "schedule_job",
            "Schedule a future job (run_at ISO-8601 and/or cron_expr).",
            {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "action": {"type": "string"},
                    "run_at": {"type": "string"},
                    "cron_expr": {"type": "string"},
                },
                "required": ["name", "action"],
                "additionalProperties": False,
            },
            PermissionLevel.LOW_RISK,
            schedule_job,
        )
    )
    registry.register(
        Tool(
            "list_jobs",
            "List scheduled autonomy jobs.",
            {"type": "object", "properties": {}, "additionalProperties": False},
            PermissionLevel.READ,
            list_jobs,
        )
    )
