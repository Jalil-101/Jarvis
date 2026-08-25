"""Speech-to-text via faster-whisper (local) when installed."""

from __future__ import annotations

import re
import tempfile
import time
from collections import deque
from pathlib import Path

import numpy as np

from jarvis.config_loader import get_settings
from jarvis.voice.mic import (
    block_level,
    capture_channels,
    capture_samplerate,
    downmix_mono,
    resolve_input_device,
)

_model = None
_model_name: str | None = None
_TARGET_RATE = 16000
_MIN_SPEECH_PEAK = 0.015
# Bias Whisper toward Jarvis vocabulary without another API call.
_INITIAL_PROMPT = (
    "Hey Jarvis. Good evening. Remember that. Create a folder. "
    "What's the weather. Abdul. Columbus Ohio."
)


def preload_model() -> None:
    """Load the Whisper model once up front so the first listen is not a long pause."""
    _ensure_model()


def _ensure_model():
    global _model, _model_name
    try:
        from faster_whisper import WhisperModel
    except ImportError as exc:
        raise RuntimeError(
            "faster-whisper is not installed. pip install faster-whisper sounddevice numpy"
        ) from exc

    settings = get_settings()
    name = os_getenv_stt_model(settings.stt_model)
    if _model is not None and _model_name == name:
        return _model
    print(f"(loading speech model '{name}' — once per session…)")
    t0 = time.perf_counter()
    _model = WhisperModel(name, device="cpu", compute_type="int8")
    _model_name = name
    print(f"(speech model ready in {time.perf_counter() - t0:.1f}s)")
    return _model


def os_getenv_stt_model(fallback: str) -> str:
    import os

    return (os.getenv("JARVIS_STT_MODEL") or fallback or "tiny.en").strip()


def transcribe_file(path: Path | str) -> str:
    model = _ensure_model()
    # Fast path: beam_size=1. Soft VAD so the first syllable is not chopped.
    segments, _info = model.transcribe(
        str(path),
        language="en",
        beam_size=1,
        best_of=1,
        temperature=0.0,
        vad_filter=True,
        vad_parameters={"min_silence_duration_ms": 400, "speech_pad_ms": 300},
        condition_on_previous_text=False,
        without_timestamps=True,
        initial_prompt=_INITIAL_PROMPT,
    )
    raw = " ".join(seg.text.strip() for seg in segments).strip()
    return cleanup_transcript(raw)


def cleanup_transcript(text: str) -> str:
    """Light local cleanup — not an extra LLM call (that would slow voice further)."""
    text = (text or "").strip()
    if not text:
        return ""
    # Collapse whitespace / odd punctuation Whisper leaves behind.
    text = re.sub(r"\s+", " ", text)
    text = re.sub(r"\s+([,.!?])", r"\1", text)
    text = re.sub(r"([.!?]){2,}", r"\1", text)
    # Common near-misses for this project.
    replacements = (
        (r"\bjarves\b", "Jarvis"),
        (r"\bjavis\b", "Jarvis"),
        (r"\bjarvus\b", "Jarvis"),
        (r"\babdul\b", "Abdul"),
        (r"\bhey jarvis[,.]?\s*", "Hey Jarvis, "),
    )
    for pattern, repl in replacements:
        text = re.sub(pattern, repl, text, flags=re.IGNORECASE)
    # Drop pure hallucination fillers.
    if text.strip().lower() in {"you", "thank you", ".", "...", "hmm", "uh", "ah", "the"}:
        return ""
    if text and text[0].islower():
        text = text[0].upper() + text[1:]
    return text.strip()


def record_until_silence(*, max_seconds: float = 10, silence_seconds: float = 0.9) -> Path:
    """Continuous InputStream + pre-roll so early words are not lost."""
    try:
        import sounddevice as sd
    except ImportError as exc:
        raise RuntimeError(
            "Microphone capture needs sounddevice and numpy. pip install sounddevice numpy"
        ) from exc

    device = resolve_input_device()
    info = sd.query_devices(device)
    native_rate = capture_samplerate(device)
    channels = capture_channels(device)
    chunk_sec = 0.15
    chunk_frames = max(1, int(chunk_sec * native_rate))
    preroll_chunks = max(2, int(0.6 / chunk_sec))  # ~0.6s before speech onset
    ring: deque[np.ndarray] = deque(maxlen=preroll_chunks)
    speech_frames: list[np.ndarray] = []
    silent_for = 0.0
    heard = False
    total = 0.0
    peak_level = 0.0
    threshold = 0.012

    print(f"(mic [{device}] {channels}ch — speak when ready)")
    time.sleep(0.15)  # brief settle after TTS; keep short so early words aren't missed

    try:
        with sd.InputStream(
            device=device,
            channels=channels,
            samplerate=native_rate,
            dtype="float32",
            blocksize=chunk_frames,
        ) as stream:
            # Warmup stays in the ring (not discarded) so leading speech survives.
            warm, _ = stream.read(chunk_frames)
            ring.append(downmix_mono(warm).copy())

            while total < max_seconds:
                block, _overflowed = stream.read(chunk_frames)
                mono = downmix_mono(block).copy()
                _, peak = block_level(block)
                peak_level = max(peak_level, peak)
                total += chunk_sec

                if peak > threshold:
                    if not heard:
                        # Capture the buffered lead-in (the "early words").
                        speech_frames.extend(ring)
                        ring.clear()
                        heard = True
                    speech_frames.append(mono)
                    silent_for = 0.0
                    print(f"\r  (hearing… peak={peak_level:.3f})   ", end="", flush=True)
                elif heard:
                    speech_frames.append(mono)
                    silent_for += chunk_sec
                    if silent_for >= silence_seconds:
                        break
                else:
                    ring.append(mono)
    except Exception as exc:  # noqa: BLE001
        raise RuntimeError(f"Mic stream failed on device [{device}]: {exc}") from exc

    print()
    print(f"(recorded {len(speech_frames) * chunk_sec:.1f}s speech, peak={peak_level:.4f})")

    if peak_level < _MIN_SPEECH_PEAK or not speech_frames:
        raise RuntimeError(
            f"Microphone level too low (peak {peak_level:.4f}). "
            "Speak louder / closer, or run .\\scripts\\run.cmd mic-test again."
        )

    audio = np.concatenate(speech_frames, axis=0)
    audio_16k = _resample(audio, native_rate, _TARGET_RATE)
    tmp = Path(tempfile.gettempdir()) / "jarvis-last.wav"
    _write_wav(tmp, audio_16k, _TARGET_RATE)
    return tmp


def listen_once(*, max_seconds: float | None = None) -> str:
    settings = get_settings()
    print("(listening — speak now, then pause…)")
    t0 = time.perf_counter()
    try:
        path = record_until_silence(
            max_seconds=max_seconds or min(10.0, max(6.0, settings.session_silence_seconds)),
            silence_seconds=0.9,
        )
    except RuntimeError as exc:
        print(f"(mic error: {exc})")
        return ""
    print("(transcribing…)")
    text = transcribe_file(path)
    print(f"(stt {time.perf_counter() - t0:.1f}s)")
    if not text:
        print("(heard nothing)")
        return ""
    print(f"(heard: {text})")
    return text


def _resample(samples: np.ndarray, src_rate: int, dst_rate: int) -> np.ndarray:
    if src_rate == dst_rate:
        return samples.astype(np.float32, copy=False)
    if samples.size == 0:
        return samples.astype(np.float32)
    duration = samples.size / float(src_rate)
    dst_len = max(1, int(round(duration * dst_rate)))
    x_old = np.linspace(0.0, 1.0, num=samples.size, endpoint=False)
    x_new = np.linspace(0.0, 1.0, num=dst_len, endpoint=False)
    return np.interp(x_new, x_old, samples.astype(np.float64)).astype(np.float32)


def _write_wav(path: Path, samples, samplerate: int) -> None:
    import wave

    pcm = np.clip(samples, -1, 1)
    pcm = (pcm * 32767).astype(np.int16)
    with wave.open(str(path), "wb") as fh:
        fh.setnchannels(1)
        fh.setsampwidth(2)
        fh.setframerate(samplerate)
        fh.writeframes(pcm.tobytes())
