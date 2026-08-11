"""Voice duplex loops: push-to-talk and always-on wake."""

from __future__ import annotations

import time

from jarvis.config_loader import get_settings
from jarvis.core.agent import Agent, confirm_cli
from jarvis.voice.tts import speak


def push_to_talk(*, session_id: str | None = None) -> None:
    """Press Enter to talk; speak a reply. No wake word required."""
    settings = get_settings()
    agent = Agent(session_id=session_id, confirm_fn=_voice_confirm)
    speak(settings.acknowledgment)
    print("Push-to-talk. Press Enter to record, Ctrl+C to exit.")
    while True:
        try:
            input("Press Enter, then speak… ")
        except (EOFError, KeyboardInterrupt):
            speak("Goodbye.")
            break
        user = _listen_or_type()
        if not user:
            speak("I didn't catch that.")
            continue
        if user.lower() in {"exit", "quit", "goodbye", "that's all"}:
            speak("Until next time.")
            break
        print(f"You: {user}")
        reply = _safe_chat(agent, user)
        print(f"Jarvis: {reply}")
        speak(reply)


def always_on(*, session_id: str | None = None) -> None:
    """Wake word → acknowledge → listen → act → speak. Session times out on silence."""
    from jarvis.voice.wake import wait_for_wake

    settings = get_settings()
    agent = Agent(session_id=session_id, confirm_fn=_voice_confirm)
    print("Always-on voice. Ctrl+C to stop.")
    while True:
        try:
            wait_for_wake(on_status=print)
        except (KeyboardInterrupt, SystemExit):
            break
        speak(settings.acknowledgment)
        deadline = time.time() + settings.session_silence_seconds + 20
        while time.time() < deadline:
            user = _listen_or_type()
            if not user:
                speak("Still here if you need me.")
                break
            if user.lower() in {"that's all", "goodbye", "go to sleep", "cancel"}:
                speak("Very good.")
                break
            print(f"You: {user}")
            reply = _safe_chat(agent, user)
            print(f"Jarvis: {reply}")
            speak(reply)
            deadline = time.time() + settings.session_silence_seconds + 15


def day30_demo(*, session_id: str = "day30-demo") -> None:
    """wake → greet → recall a fact → create folder → weather → sign-off."""
    from jarvis.config_loader import get_settings
    from jarvis.memory.store import MemoryStore

    settings = get_settings()
    memory = MemoryStore(settings.db_path)
    memory.add_semantic("Abdul is building Jarvis, a personal AI operating layer.")
    memory.upsert_person("Abdul", relation="user", notes="Prefers concise British-inspired replies.")
    memory.add_episode("Jarvis Day-30 demo ran.")

    speak(settings.acknowledgment)
    print("(Wake acknowledged)")

    try:
        agent = Agent(session_id=session_id, confirm_fn=lambda _p: True)
        reply = agent.chat(
            "Greet me briefly, recall what you know about the Jarvis project, "
            "create a sandbox folder called day30-demo, then tell me the weather at home."
        )
        print(f"Jarvis: {reply}")
        speak(reply)
    except RuntimeError as exc:
        print(f"LLM unavailable ({exc}). Running tool-only demo.")
        from jarvis.security.permissions import PermissionGate
        from jarvis.tools import build_registry

        gate = PermissionGate(audit_path=settings.audit_log_path)
        registry = build_registry(settings, memory, gate)
        print(registry.execute("create_folder", {"path": "day30-demo"}))
        print(registry.execute("get_system_info", {}))
        try:
            print(registry.execute("get_weather", {}))
        except Exception as weather_exc:  # noqa: BLE001
            print(f"Weather skipped: {weather_exc}")
        speak("Demo tools ran. Add an API key for the full conversation.")
    speak("That concludes the demonstration.")


def _listen_or_type() -> str:
    try:
        from jarvis.voice.stt import listen_once

        return listen_once()
    except RuntimeError as exc:
        print(f"(Mic/STT unavailable: {exc})")
        try:
            return input("Type instead: ").strip()
        except (EOFError, KeyboardInterrupt):
            return ""


def _voice_confirm(prompt: str) -> bool:
    try:
        from jarvis.voice.stt import listen_once
        from jarvis.voice.tts import speak as say

        say(f"{prompt} Please say yes or no.")
        answer = listen_once(max_seconds=4).lower()
        if "yes" in answer or "confirm" in answer or "allow" in answer:
            return True
        if "no" in answer or "deny" in answer or "cancel" in answer:
            return False
    except RuntimeError:
        pass
    return confirm_cli(prompt)


def _safe_chat(agent: Agent, user: str) -> str:
    try:
        return agent.chat(user)
    except Exception as exc:  # noqa: BLE001
        return f"Something went wrong: {exc}"
