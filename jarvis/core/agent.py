"""Claude tool-using agent with SQLite logging and memory injection."""

from __future__ import annotations

import re
import uuid
from collections.abc import Callable
from typing import Any

from anthropic import Anthropic, AuthenticationError, NotFoundError

from jarvis.config_loader import get_settings, repo_root
from jarvis.core.personality import load_system_prompt
from jarvis.memory.store import MemoryStore
from jarvis.security.permissions import PermissionGate
from jarvis.tools import build_registry
from jarvis.tools.registry import ToolRegistry

ConfirmFn = Callable[[str], bool]


class Agent:
    """Message → Claude → tools → reply."""

    def __init__(
        self,
        *,
        session_id: str | None = None,
        memory: MemoryStore | None = None,
        permissions: PermissionGate | None = None,
        confirm_fn: ConfirmFn | None = None,
        voice_mode: bool = False,
    ) -> None:
        self.settings = get_settings()
        env_path = repo_root() / ".env"
        key = self.settings.anthropic_api_key
        if not key:
            raise RuntimeError(
                f"ANTHROPIC_API_KEY is empty in {env_path}. "
                "Paste the key after the equals sign with no quotes or spaces, "
                "then save the file (Ctrl+S) before running Jarvis."
            )
        if len(key) < 80 or "..." in key:
            raise RuntimeError(
                f"ANTHROPIC_API_KEY in {env_path} looks truncated ({len(key)} chars). "
                "A real Anthropic key is ~100+ characters. "
                "Paste the full key from console.anthropic.com and save (Ctrl+S)."
            )
        self.client = Anthropic(api_key=self.settings.anthropic_api_key)
        self.memory = memory or MemoryStore(self.settings.db_path)
        self.permissions = permissions or PermissionGate(
            audit_path=self.settings.audit_log_path,
            max_autonomous_level=self.settings.max_autonomous_level,
            confirm_fn=confirm_fn,
        )
        if confirm_fn and self.permissions.confirm_fn is None:
            self.permissions.confirm_fn = confirm_fn
        self.session_id = session_id or str(uuid.uuid4())
        self.system_prompt = load_system_prompt()
        self.voice_mode = voice_mode
        self.registry: ToolRegistry = build_registry(self.settings, self.memory, self.permissions)
        self._history: list[dict[str, Any]] = _text_only(
            self.memory.load_messages(self.session_id, limit=self.settings.max_history_turns)
        )
        self._seed_projects()

    def _seed_projects(self) -> None:
        for alias in self.settings.projects.values():
            self.memory.upsert_project(
                alias.name,
                path=str(alias.path),
                stack=alias.stack,
                notes=alias.notes,
            )

    def chat(self, user_text: str) -> str:
        user_text = user_text.strip()
        if not user_text:
            return ""

        self._maybe_extract(user_text)
        self.memory.append_turn(self.session_id, "user", user_text)
        messages: list[dict[str, Any]] = [*self._history, {"role": "user", "content": user_text}]
        tools = self.registry.schemas()
        system = self._compose_system(user_text)

        assistant_text = ""
        max_tokens = (
            self.settings.voice_max_tokens if self.voice_mode else self.settings.max_tokens
        )
        max_rounds = (
            self.settings.voice_max_tool_rounds if self.voice_mode else self.settings.max_tool_rounds
        )
        for _ in range(max_rounds):
            try:
                response = self.client.messages.create(
                    model=self.settings.model,
                    max_tokens=max_tokens,
                    system=system,
                    tools=tools,
                    messages=messages,
                )
            except AuthenticationError as exc:
                raise RuntimeError(
                    "Anthropic rejected the API key (401). "
                    "Open console.anthropic.com → API keys, create a new key, "
                    f"paste the full value into {repo_root() / '.env'}, and save. "
                    "Do not paste keys into chat."
                ) from exc
            except NotFoundError as exc:
                raise RuntimeError(
                    f"Anthropic does not offer model {self.settings.model!r}. "
                    "Set JARVIS_MODEL in .env (try claude-sonnet-5) or update "
                    "config/default.yaml."
                ) from exc
            if response.stop_reason != "tool_use":
                assistant_text = _extract_text(response.content)
                break

            tool_results = []
            for block in response.content:
                if getattr(block, "type", None) != "tool_use":
                    continue
                result = self.registry.execute(block.name, dict(block.input or {}))
                tool_results.append(
                    {
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": result,
                    }
                )
            messages.append({"role": "assistant", "content": response.content})
            messages.append({"role": "user", "content": tool_results})
        else:
            assistant_text = _extract_text(getattr(response, "content", [])) or (
                "I reached the tool-round limit. Please try a narrower request."
            )

        assistant_text = assistant_text or "(no reply)"
        self.memory.append_turn(self.session_id, "assistant", assistant_text)
        self._history.append({"role": "user", "content": user_text})
        self._history.append({"role": "assistant", "content": assistant_text})
        max_msgs = self.settings.max_history_turns * 2
        if len(self._history) > max_msgs:
            self._history = self._history[-max_msgs:]
        return assistant_text

    def _compose_system(self, user_text: str) -> str:
        parts = [self.system_prompt]
        if self.voice_mode:
            parts.append(
                "## Voice mode\n"
                "The user is speaking aloud. Reply in 1–2 short spoken sentences. "
                "No markdown, lists, or URLs. Lead with the answer. "
                "If the transcript looks garbled, infer the likely intent and answer briefly; "
                "ask one clarifying question only if you truly cannot."
            )
        recalled = self.memory.recall(user_text, limit=8)
        if recalled:
            parts.append("## Recalled personal knowledge\n" + recalled)
        prefs = self.memory.list_preferences()
        if prefs:
            lines = "\n".join(f"- {p['key']}: {p['value']}" for p in prefs)
            parts.append("## Preferences\n" + lines)
        parts.append(
            "## Runtime\n"
            f"Sandbox: {self.settings.sandbox_root}\n"
            f"Data dir: {self.settings.data_dir}\n"
            f"Projects: {', '.join(self.settings.projects)}\n"
        )
        return "\n\n".join(parts)

    def _maybe_extract(self, user_text: str) -> None:
        # Voice transcripts are messy — accept several remember phrasings.
        remember = re.search(
            r"(?:please\s+)?remember(?:\s+that|\s+this)?[:\s]+(.+)",
            user_text,
            re.I,
        )
        if remember:
            fact = remember.group(1).strip(" .,!")
            if len(fact) >= 3:
                self.memory.add_semantic(fact, session_id=self.session_id)
        # "my favorite drink is tea" / "my advisor is Sarah"
        person = re.search(
            r"\bmy\s+(\w+)\s+is\s+([A-Z][a-zA-Z\-']+)\b",
            user_text,
        )
        if person:
            relation, name = person.group(1), person.group(2)
            self.memory.upsert_person(name, relation=relation, notes=user_text)
            self.memory.add_semantic(
                f"The user's {relation} is {name}.",
                session_id=self.session_id,
            )
        pref = re.search(
            r"\bmy\s+favorite\s+(\w+)\s+is\s+(.+?)(?:[.!]|$)",
            user_text,
            re.I,
        )
        if pref:
            key, value = pref.group(1).lower(), pref.group(2).strip(" .,!")
            if key and value:
                self.memory.set_preference(f"favorite.{key}", value)
                self.memory.add_semantic(
                    f"The user's favorite {key} is {value}.",
                    session_id=self.session_id,
                )


def _text_only(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out = []
    for msg in messages:
        if msg.get("role") in {"user", "assistant"} and isinstance(msg.get("content"), str):
            out.append({"role": msg["role"], "content": msg["content"]})
    return out


def _extract_text(content: list[Any]) -> str:
    parts: list[str] = []
    for block in content:
        text = getattr(block, "text", None)
        if text:
            parts.append(text)
    return "\n".join(parts).strip()


def confirm_cli(prompt: str) -> bool:
    try:
        answer = input(f"{prompt} [y/N] ").strip().lower()
    except (EOFError, KeyboardInterrupt):
        return False
    return answer in {"y", "yes"}


def run_once(message: str, *, session_id: str | None = None, confirm: bool = False) -> str:
    agent = Agent(session_id=session_id, confirm_fn=(lambda _p: True) if confirm else None)
    return agent.chat(message)


def run_chat_loop(*, session_id: str | None = None, speak_replies: bool = True) -> None:
    agent = Agent(session_id=session_id, confirm_fn=confirm_cli)
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
        if speak_replies and reply:
            from jarvis.voice.tts import speak

            speak(reply)
