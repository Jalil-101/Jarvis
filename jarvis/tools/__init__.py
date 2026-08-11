"""Register every permissioned tool Jarvis may use."""

from __future__ import annotations

from jarvis.config_loader import Settings
from jarvis.memory.store import MemoryStore
from jarvis.tools.computer import register_computer_tools
from jarvis.tools.dev import register_dev_tools
from jarvis.tools.jobs import register_job_tools
from jarvis.tools.life import register_life_tools
from jarvis.tools.memory_tools import register_memory_tools
from jarvis.tools.registry import ToolRegistry
from jarvis.tools.sec import register_security_tools
from jarvis.tools.web import register_web_tools


def build_registry(settings: Settings, memory: MemoryStore, gate) -> ToolRegistry:
    registry = ToolRegistry(gate)
    register_computer_tools(registry, settings)
    register_web_tools(registry, settings)
    register_memory_tools(registry, settings, memory)
    register_dev_tools(registry, settings)
    register_life_tools(registry, settings, memory)
    register_security_tools(registry, settings)
    register_job_tools(registry, memory)
    return registry
