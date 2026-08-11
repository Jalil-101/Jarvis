"""Load the Jarvis personality / system prompt."""

from __future__ import annotations

from pathlib import Path

_DEFAULT_PROMPT = """\
You are Jarvis, a calm British-inspired personal AI assistant.
Be concise, capable, and lightly witty. Never claim to be Marvel's JARVIS \
or reproduce copyrighted Marvel dialogue. You are an original assistant \
inspired by the helpful butler archetype.
"""


def load_system_prompt() -> str:
    """Read personality from config/personality.md, falling back to a built-in stub."""
    candidates = [
        Path.cwd() / "config" / "personality.md",
        Path(__file__).resolve().parents[2] / "config" / "personality.md",
    ]
    for path in candidates:
        if path.is_file():
            return path.read_text(encoding="utf-8").strip()
    return _DEFAULT_PROMPT.strip()
