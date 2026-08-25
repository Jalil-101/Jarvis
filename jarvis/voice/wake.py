"""Wake-word detection: openWakeWord if present, else STT keyword, else Enter hotkey."""

from __future__ import annotations

import sys
import threading
from collections.abc import Callable

from jarvis.config_loader import get_settings


def wait_for_wake(*, on_status: Callable[[str], None] | None = None) -> str:
    """Block until wake. Returns the method used: oww | stt | hotkey."""
    settings = get_settings()
    word = settings.wake_word.lower()
    if on_status:
        on_status(
            f"Listening for wake… Say clearly: 'Hey {settings.wake_word.title()}' "
            "— or press Enter anytime."
        )

    # openWakeWord with Enter interrupt (workshop-friendly on Windows).
    method = _try_openwakeword(word, on_status=on_status)
    if method:
        return method

    if _mic_available():
        try:
            from jarvis.voice.stt import listen_once

            while True:
                if on_status:
                    on_status(
                        f"Say 'Hey {settings.wake_word}' or press Enter "
                        "(speech recognition fallback)…"
                    )
                # Parallel Enter while STT listens is awkward; poll short STT windows.
                text = listen_once(max_seconds=3).lower()
                if on_status and text:
                    on_status(f"(heard: {text!r})")
                if word in text or "hey jarvis" in text or "hey jarves" in text:
                    return "stt"
                # Offer hotkey between attempts without blocking forever on STT.
                if _stdin_ready():
                    sys.stdin.readline()
                    return "hotkey"
        except RuntimeError as exc:
            if on_status:
                on_status(f"Mic/STT unavailable: {exc}")

    if on_status:
        on_status("Press Enter to wake Jarvis (hotkey fallback).")
    try:
        sys.stdin.readline()
    except KeyboardInterrupt as exc:
        raise SystemExit(0) from exc
    return "hotkey"


def _try_openwakeword(word: str, *, on_status: Callable[[str], None] | None) -> str | None:
    try:
        import numpy as np
        import openwakeword
        import sounddevice as sd
        from openwakeword.model import Model
    except ImportError:
        return None

    try:
        openwakeword.utils.download_models()
    except Exception:
        pass

    try:
        model = Model(wakeword_models=["hey_jarvis"])
    except Exception:
        return None

    from jarvis.voice.mic import capture_channels, capture_samplerate, downmix_mono, resolve_input_device

    device = resolve_input_device()
    info = sd.query_devices(device)
    native_rate = capture_samplerate(device)
    channels = capture_channels(device)
    target = 16000
    chunk = max(1, int(0.08 * native_rate))
    if on_status:
        on_status(
            f"openWakeWord armed — say: Hey Jarvis  "
            f"(mic [{device}] {channels}ch). Press Enter to wake manually."
        )

    stop = threading.Event()
    woke = {"method": None}

    def _enter_watcher() -> None:
        try:
            sys.stdin.readline()
            woke["method"] = "hotkey"
            stop.set()
        except Exception:
            stop.set()

    watcher = threading.Thread(target=_enter_watcher, daemon=True)
    watcher.start()

    try:
        with sd.InputStream(
            device=device,
            channels=channels,
            samplerate=native_rate,
            dtype="float32",
            blocksize=chunk,
        ) as stream:
            stream.read(chunk)  # warmup
            while not stop.is_set():
                audio, _ = stream.read(chunk)
                flat = downmix_mono(audio).astype(np.float32)
                if native_rate != target:
                    duration = flat.size / float(native_rate)
                    dst_len = max(1, int(round(duration * target)))
                    x_old = np.linspace(0.0, 1.0, num=flat.size, endpoint=False)
                    x_new = np.linspace(0.0, 1.0, num=dst_len, endpoint=False)
                    flat = np.interp(x_new, x_old, flat).astype(np.float32)
                pcm16 = np.clip(flat * 32767.0, -32768, 32767).astype(np.int16)
                scores = model.predict(pcm16)
                for name, score in scores.items():
                    if score >= 0.4 and ("jarvis" in name.lower() or word in name.lower()):
                        if on_status:
                            on_status(f"Wake detected ({name}={score:.2f})")
                        woke["method"] = "oww"
                        stop.set()
                        break
    except Exception as exc:
        if on_status:
            on_status(f"openWakeWord failed ({exc}); falling back.")
        return None

    return woke["method"]


def _stdin_ready() -> bool:
    try:
        import msvcrt

        return bool(msvcrt.kbhit())
    except ImportError:
        try:
            import select

            return bool(select.select([sys.stdin], [], [], 0)[0])
        except Exception:
            return False


def _mic_available() -> bool:
    try:
        import sounddevice as sd  # noqa: F401

        return True
    except ImportError:
        return False
