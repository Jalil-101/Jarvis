"""Explicit memory tools: remember, recall, people, projects, forget, export."""

from __future__ import annotations

import json

from jarvis.config_loader import Settings
from jarvis.memory.store import MemoryStore
from jarvis.security.paths import assert_allowed
from jarvis.security.permissions import PermissionLevel
from jarvis.tools.registry import Tool, ToolRegistry


def register_memory_tools(registry: ToolRegistry, settings: Settings, memory: MemoryStore) -> None:
    def remember(content: str, kind: str = "semantic", key: str = "") -> str:
        kind = kind if kind in {"semantic", "preference", "episode"} else "semantic"
        if kind == "preference" and key:
            memory.set_preference(key, content)
            return json.dumps({"stored": "preference", "key": key})
        if kind == "episode":
            eid = memory.add_episode(content)
            return json.dumps({"stored": "episode", "id": eid})
        fid = memory.add_semantic(content, key=key or None)
        return json.dumps({"stored": "semantic", "id": fid})

    def recall(query: str) -> str:
        brief = memory.recall(query, limit=10)
        return json.dumps({"query": query, "matches": brief or "No matching memories."})

    def upsert_person(name: str, relation: str = "", notes: str = "") -> str:
        memory.upsert_person(name, relation=relation, notes=notes)
        return json.dumps({"person": name, "relation": relation})

    def upsert_project(name: str, path: str = "", stack: str = "", notes: str = "") -> str:
        memory.upsert_project(name, path=path, stack=stack, notes=notes)
        return json.dumps({"project": name, "path": path})

    def set_preference(key: str, value: str) -> str:
        memory.set_preference(key, value)
        return json.dumps({"key": key, "value": value})

    def forget(kind: str, query: str) -> str:
        n = memory.forget(kind=kind, query=query)
        return json.dumps({"deleted": n, "kind": kind, "query": query})

    def export_memory() -> str:
        dest = assert_allowed(settings.sandbox_root / "memory-export.json", (settings.sandbox_root,))
        dest.write_text(json.dumps(memory.export_all(), indent=2), encoding="utf-8")
        return json.dumps({"wrote": str(dest)})

    registry.register(
        Tool(
            "remember",
            "Store a lasting memory. kind: semantic | episode | preference.",
            {
                "type": "object",
                "properties": {
                    "content": {"type": "string"},
                    "kind": {"type": "string"},
                    "key": {"type": "string"},
                },
                "required": ["content"],
                "additionalProperties": False,
            },
            PermissionLevel.LOW_RISK,
            remember,
        )
    )
    registry.register(
        Tool(
            "recall",
            "Search long-term memory (people, projects, facts, episodes, preferences).",
            {
                "type": "object",
                "properties": {"query": {"type": "string"}},
                "required": ["query"],
                "additionalProperties": False,
            },
            PermissionLevel.READ,
            recall,
        )
    )
    registry.register(
        Tool(
            "upsert_person",
            "Create or update a person in memory (advisor, classmate, etc.).",
            {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "relation": {"type": "string"},
                    "notes": {"type": "string"},
                },
                "required": ["name"],
                "additionalProperties": False,
            },
            PermissionLevel.LOW_RISK,
            upsert_person,
        )
    )
    registry.register(
        Tool(
            "upsert_project",
            "Create or update a project in memory.",
            {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "path": {"type": "string"},
                    "stack": {"type": "string"},
                    "notes": {"type": "string"},
                },
                "required": ["name"],
                "additionalProperties": False,
            },
            PermissionLevel.LOW_RISK,
            upsert_project,
        )
    )
    registry.register(
        Tool(
            "set_preference",
            "Save a user preference (e.g. concise emails, ignore promotions).",
            {
                "type": "object",
                "properties": {"key": {"type": "string"}, "value": {"type": "string"}},
                "required": ["key", "value"],
                "additionalProperties": False,
            },
            PermissionLevel.LOW_RISK,
            set_preference,
        )
    )
    registry.register(
        Tool(
            "forget",
            "Delete matching memories. kind: fact | person | project | preference | episode.",
            {
                "type": "object",
                "properties": {"kind": {"type": "string"}, "query": {"type": "string"}},
                "required": ["kind", "query"],
                "additionalProperties": False,
            },
            PermissionLevel.SENSITIVE,
            forget,
        )
    )
    registry.register(
        Tool(
            "export_memory",
            "Export personal knowledge (not full chat logs) to the sandbox as JSON.",
            {"type": "object", "properties": {}, "additionalProperties": False},
            PermissionLevel.READ,
            export_memory,
        )
    )
