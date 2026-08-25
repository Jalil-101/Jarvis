"""Voice duplex loops: push-to-talk, always-on wake, Day-30 demo, hands smoke."""

from __future__ import annotations

import json
import time
from pathlib import Path

from jarvis.config_loader import get_settings
from jarvis.core.agent import Agent, confirm_cli
from jarvis.voice.tts import speak


def push_to_talk(*, session_id: str | None = None) -> None:
    """Press Enter to talk; speak a reply. No wake word required."""
    settings = get_settings()
    _preload_voice()
    agent = Agent(session_id=session_id, confirm_fn=_voice_confirm, voice_mode=True)
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
        if _is_signoff(user):
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
    _preload_voice()
    agent = Agent(session_id=session_id, confirm_fn=_voice_confirm, voice_mode=True)
    print("Always-on voice. Ctrl+C to stop.")
    print("Wake phrase: say  Hey Jarvis  (or press Enter).")
    print("After he answers, speak your request; pause when finished.")
    print("Say 'that's all' to end a session.")
    while True:
        try:
            method = wait_for_wake(on_status=print)
            print(f"(woke via {method})")
        except (KeyboardInterrupt, SystemExit):
            break
        speak(settings.acknowledgment)
        deadline = time.time() + settings.session_silence_seconds + 20
        misses = 0
        while time.time() < deadline:
            user = _listen_or_type()
            if not user:
                misses += 1
                if misses >= 2:
                    speak("Standing by.")
                    break
                speak("Pardon?")
                continue
            misses = 0
            if _is_signoff(user):
                speak("Very good.")
                break
            print(f"You: {user}")
            reply = _safe_chat(agent, user)
            print(f"Jarvis: {reply}")
            speak(reply)
            deadline = time.time() + settings.session_silence_seconds + 15


def day30_demo(*, session_id: str = "day30-demo") -> None:
    """wake → greet → recall a fact → create folder → weather → sign-off."""
    from jarvis.memory.store import MemoryStore
    from jarvis.security.permissions import PermissionGate
    from jarvis.tools import build_registry

    settings = get_settings()
    memory = MemoryStore(settings.db_path)
    memory.add_semantic("Abdul is building Jarvis, a personal AI operating layer.")
    memory.upsert_person("Abdul", relation="user", notes="Prefers concise British-inspired replies.")
    memory.add_episode("Jarvis Day-30 demo ran.")
    memory.set_preference("demo.day30", "completed_seed")

    print("=== Day-30 demo ===")
    print("1) Wake acknowledgement")
    speak(settings.acknowledgment)
    print("(Wake acknowledged)")

    gate = PermissionGate(audit_path=settings.audit_log_path, confirm_fn=lambda _p: True)
    registry = build_registry(settings, memory, gate)

    print("2) Safe hands (folder + system info + weather)")
    folder = registry.execute("create_folder", {"path": "day30-demo"})
    print(f"  create_folder → {folder}")
    info = registry.execute("get_system_info", {})
    print(f"  get_system_info → {info[:120]}…")
    try:
        weather = registry.execute("get_weather", {})
        print(f"  get_weather → {weather[:160]}…")
    except Exception as weather_exc:  # noqa: BLE001
        weather = f"Weather skipped: {weather_exc}"
        print(f"  {weather}")

    print("3) Memory recall")
    recalled = registry.execute("recall", {"query": "Jarvis project Abdul"})
    print(f"  recall → {recalled[:200]}")

    print("4) Conversation (if API key works)")
    try:
        agent = Agent(
            session_id=session_id,
            memory=memory,
            permissions=gate,
            confirm_fn=lambda _p: True,
            voice_mode=True,
        )
        reply = agent.chat(
            "Briefly greet me, say what you recall about the Jarvis project, "
            "confirm the day30-demo folder exists, and give a one-line weather summary."
        )
        print(f"Jarvis: {reply}")
        speak(reply)
    except RuntimeError as exc:
        print(f"LLM unavailable ({exc}). Tool-only demo already ran.")
        speak("Demo tools ran. Add an API key for the full conversation.")

    print("5) Audit log (last tool lines)")
    _print_audit_tail(settings.audit_log_path, n=8)
    speak("That concludes the demonstration.")
    print("=== Day-30 demo complete ===")


def hands_smoke() -> int:
    """Run Level 0–2 safe hands without the LLM (Week 3 acceptance)."""
    from jarvis.memory.store import MemoryStore
    from jarvis.security.permissions import PermissionGate
    from jarvis.tools import build_registry

    settings = get_settings()
    memory = MemoryStore(settings.db_path)
    gate = PermissionGate(audit_path=settings.audit_log_path, confirm_fn=lambda _p: True)
    registry = build_registry(settings, memory, gate)

    print("=== Safe hands smoke (no LLM) ===")
    steps = [
        ("create_folder", {"path": "hands-smoke"}),
        ("list_sandbox", {"path": "."}),
        ("get_system_info", {}),
        ("run_allowlisted_command", {"name": "whoami"}),
        ("run_allowlisted_command", {"name": "python_version"}),
        ("remember", {"content": "Hands smoke test stored a sandbox fact."}),
        ("recall", {"query": "hands smoke sandbox"}),
    ]
    ok = 0
    for name, args in steps:
        try:
            if name == "get_weather":
                continue
            result = registry.execute(name, args)
            print(f"OK  {name}: {result[:160]}")
            ok += 1
        except Exception as exc:  # noqa: BLE001
            print(f"FAIL {name}: {exc}")
    try:
        weather = registry.execute("get_weather", {})
        print(f"OK  get_weather: {weather[:160]}")
        ok += 1
    except Exception as exc:  # noqa: BLE001
        print(f"SKIP get_weather: {exc}")

    _print_audit_tail(settings.audit_log_path, n=6)
    print(f"=== {ok} actions completed ===")
    speak(f"Hands check complete. {ok} safe actions ran.")
    return 0 if ok >= 5 else 1


def _print_audit_tail(path: Path, *, n: int = 6) -> None:
    try:
        lines = path.read_text(encoding="utf-8").strip().splitlines()
    except OSError:
        print("(no audit log yet)")
        return
    for line in lines[-n:]:
        try:
            row = json.loads(line)
            print(
                f"  audit: {row.get('tool') or row.get('action')} "
                f"level={row.get('level')} allowed={row.get('allowed')}"
            )
        except json.JSONDecodeError:
            print(f"  audit: {line[:120]}")


def _is_signoff(text: str) -> bool:
    low = text.lower().strip()
    return low in {
        "exit",
        "quit",
        "goodbye",
        "good bye",
        "that's all",
        "thats all",
        "go to sleep",
        "cancel",
        "stop listening",
    }


def _preload_voice() -> None:
    try:
        from jarvis.voice.stt import preload_model

        preload_model()
    except RuntimeError as exc:
        print(f"(STT preload skipped: {exc})")


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
