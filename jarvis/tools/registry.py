"""Tool registry: Anthropic schemas + permissioned execution."""

from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from jarvis.security.permissions import PermissionGate, PermissionLevel


Handler = Callable[..., Any]


@dataclass
class Tool:
    name: str
    description: str
    schema: dict[str, Any]
    level: PermissionLevel
    handler: Handler
    extra: dict[str, Any] = field(default_factory=dict)

    def anthropic(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "input_schema": self.schema,
        }


class ToolRegistry:
    def __init__(self, gate: PermissionGate) -> None:
        self.gate = gate
        self._tools: dict[str, Tool] = {}

    def register(self, tool: Tool) -> None:
        self._tools[tool.name] = tool

    def schemas(self) -> list[dict[str, Any]]:
        return [t.anthropic() for t in self._tools.values()]

    def execute(self, name: str, inputs: dict[str, Any] | None) -> str:
        inputs = inputs or {}
        tool = self._tools.get(name)
        if tool is None:
            return json.dumps({"error": f"Unknown tool: {name}"})
        decision = self.gate.authorize(name, tool.level, detail=_brief(inputs))
        if not decision.allowed:
            return json.dumps(
                {
                    "error": "permission_denied",
                    "reason": decision.reason,
                    "requires_confirm": decision.requires_confirm,
                }
            )
        try:
            result = tool.handler(**inputs)
        except TypeError as exc:
            return json.dumps({"error": f"bad arguments: {exc}"})
        except Exception as exc:  # noqa: BLE001 — surface tool failures to the model
            return json.dumps({"error": str(exc)})
        if isinstance(result, str):
            return result
        return json.dumps(result, ensure_ascii=False, default=str)


def _brief(inputs: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for key, value in inputs.items():
        text = str(value)
        out[key] = text if len(text) < 400 else text[:400] + "…"
    return out
