"""Thin Claude text-chat agent with SQLite turn logging."""

from __future__ import annotations

import uuid
from typing import Any

from anthropic import Anthropic

from jarvis.config_loader import get_settings
from jarvis.core.personality import load_system_prompt
from jarvis.memory.store import MemoryStore
from jarvis.security.permissions import PermissionGate


class Agent:
    """Minimal message → Claude → reply loop (tools come in later phases)."""

    def __init__(
        self,
        *,
        session_id: str | None = None,
        memory: MemoryStore | None = None,
        permissions: PermissionGate | None = None,
    ) -> None:
        self.settings = get_settings()
        if not self.settings.anthropic_api_key:
            raise RuntimeError(
                "ANTHROPIC_API_KEY is not set. Copy .env.example to .env and add your key."
            )
        self.client = Anthropic(api_key=self.settings.anthropic_api_key)
        self.memory = memory or MemoryStore(self.settings.db_path)
        self.permissions = permissions or PermissionGate(
            audit_path=self.settings.audit_log_path
        )
        self.session_id = session_id or str(uuid.uuid4())
        self.system_prompt = load_system_prompt()
        self._history: list[dict[str, Any]] = self.memory.load_messages(
            self.session_id,
            limit=self.settings.max_history_turns,
        )

    def chat(self, user_text: str) -> str:
        user_text = user_text.strip()
        if not user_text:
            return ""

        self.memory.append_turn(self.session_id, "user", user_text)
        self._history.append({"role": "user", "content": user_text})

        response = self.client.messages.create(
            model=self.settings.model,
            max_tokens=self.settings.max_tokens,
            system=self.system_prompt,
            messages=self._history,
        )
        assistant_text = _extract_text(response.content)
        self.memory.append_turn(self.session_id, "assistant", assistant_text)
        self._history.append({"role": "assistant", "content": assistant_text})

        # Keep in-memory history bounded
        max_msgs = self.settings.max_history_turns * 2
        if len(self._history) > max_msgs:
            self._history = self._history[-max_msgs:]

        return assistant_text


def _extract_text(content: list[Any]) -> str:
    parts: list[str] = []
    for block in content:
        text = getattr(block, "text", None)
        if text:
            parts.append(text)
    return "\n".join(parts).strip() or "(no reply)"


def run_once(message: str, *, session_id: str | None = None) -> str:
    agent = Agent(session_id=session_id)
    return agent.chat(message)


def run_chat_loop(*, session_id: str | None = None) -> None:
    agent = Agent(session_id=session_id)
    print(f"Jarvis ready (session {agent.session_id}). Type 'exit' or 'quit' to leave.\n")
    while True:
        try:
            user_text = input("You: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nGoodbye.")
            break
        if not user_text:
            continue
        if user_text.lower() in {"exit", "quit", "q"}:
            print("Jarvis: Until next time.")
            break
        reply = agent.chat(user_text)
        print(f"Jarvis: {reply}\n")
