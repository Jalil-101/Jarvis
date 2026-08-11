"""Speech-to-text via faster-whisper (local) when installed."""

from __future__ import annotations

import tempfile
from pathlib import Path

from jarvis.config_loader import get_settings

_model = None


def transcribe_file(path: Path | str) -> str:
    try:
        from faster_whisper import WhisperModel
    except ImportError as exc:
        raise RuntimeError(
            "faster-whisper is not installed. pip install faster-whisper sounddevice numpy"
        ) from exc

    global _model
    settings = get_settings()
    if _model is None:
        _model = WhisperModel(settings.stt_model, device="cpu", compute_type="int8")
    segments, _info = _model.transcribe(str(path))
    return " ".join(seg.text.strip() for seg in segments).strip()


def record_until_silence(*, max_seconds: float = 12, silence_seconds: float = 1.2) -> Path:
    try:
        import numpy as np
        import sounddevice as sd
    except ImportError as exc:
        raise RuntimeError(
            "Microphone capture needs sounddevice and numpy. pip install sounddevice numpy"
        ) from exc

    samplerate = 16000
    chunk = 0.2
    frames: list = []
    silent_for = 0.0
    heard = False
    total = 0.0
    threshold = 0.015

    while total < max_seconds:
        block = sd.rec(int(chunk * samplerate), samplerate=samplerate, channels=1, dtype="float32")
        sd.wait()
        rms = float(np.sqrt(np.mean(np.square(block))))
        frames.append(block.copy())
        total += chunk
        if rms > threshold:
            heard = True
            silent_for = 0.0
        elif heard:
            silent_for += chunk
            if silent_for >= silence_seconds:
                break

    audio = np.concatenate(frames, axis=0)
    tmp = Path(tempfile.gettempdir()) / "jarvis-last.wav"
    _write_wav(tmp, audio.flatten(), samplerate)
    return tmp


def listen_once(*, max_seconds: float | None = None) -> str:
    settings = get_settings()
    path = record_until_silence(
        max_seconds=max_seconds or max(6.0, settings.session_silence_seconds),
        silence_seconds=1.0,
    )
    return transcribe_file(path)


def _write_wav(path: Path, samples, samplerate: int) -> None:
    import wave

    import numpy as np

    pcm = np.clip(samples, -1, 1)
    pcm = (pcm * 32767).astype(np.int16)
    with wave.open(str(path), "wb") as fh:
        fh.setnchannels(1)
        fh.setsampwidth(2)
        fh.setframerate(samplerate)
        fh.writeframes(pcm.tobytes())
