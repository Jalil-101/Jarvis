"""Wake-word detection: openWakeWord if present, else STT keyword, else Enter hotkey."""

from __future__ import annotations

import sys
from collections.abc import Callable

from jarvis.config_loader import get_settings


def wait_for_wake(*, on_status: Callable[[str], None] | None = None) -> str:
    """Block until wake. Returns the method used: oww | stt | hotkey."""
    settings = get_settings()
    word = settings.wake_word.lower()
    if on_status:
        on_status(f"Listening for '{settings.wake_word}'…")

    if _try_openwakeword(word, on_status=on_status):
        return "oww"

    if _mic_available():
        try:
            from jarvis.voice.stt import listen_once

            while True:
                if on_status:
                    on_status("Say the wake word (STT fallback)…")
                text = listen_once(max_seconds=4).lower()
                if word in text or "hey jarvis" in text:
                    return "stt"
        except RuntimeError:
            pass

    if on_status:
        on_status("Press Enter to wake Jarvis (hotkey fallback).")
    try:
        sys.stdin.readline()
    except KeyboardInterrupt as exc:
        raise SystemExit(0) from exc
    return "hotkey"


def _try_openwakeword(word: str, *, on_status: Callable[[str], None] | None) -> bool:
    try:
        import numpy as np
        import openwakeword
        import sounddevice as sd
        from openwakeword.model import Model
    except ImportError:
        return False

    try:
        openwakeword.utils.download_models()
    except Exception:
        pass

    try:
        model = Model(wakeword_models=["hey_jarvis"])
    except Exception:
        return False

    samplerate = 16000
    if on_status:
        on_status("openWakeWord armed (hey_jarvis).")
    while True:
        audio = sd.rec(int(0.08 * samplerate), samplerate=samplerate, channels=1, dtype="int16")
        sd.wait()
        scores = model.predict(audio.flatten())
        for name, score in scores.items():
            if score >= 0.5 and ("jarvis" in name.lower() or word in name.lower()):
                return True


def _mic_available() -> bool:
    try:
        import sounddevice as sd  # noqa: F401

        return True
    except ImportError:
        return False
