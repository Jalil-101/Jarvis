"""British TTS via ElevenLabs (preferred) or edge-tts fallback."""

from __future__ import annotations

import asyncio
import os
import re
from pathlib import Path

from jarvis.config_loader import get_settings
from jarvis.voice.playback import play_audio

# George — calm British male in ElevenLabs Voice Library (override with ELEVENLABS_VOICE_ID).
_DEFAULT_ELEVEN_VOICE = "JBFqnCBsd6RMkjVDRZzb"
# Flash is lower latency than multilingual_v2 — better for always-on conversation.
_DEFAULT_ELEVEN_MODEL = "eleven_flash_v2_5"


def speak(text: str, *, play: bool = True) -> Path:
    """Synthesise speech and optionally play it. Returns the audio file path."""
    settings = get_settings()
    text = _for_speech(text)
    if not text:
        raise ValueError("Nothing to speak.")
    out_dir = settings.data_dir / "tts"
    out_dir.mkdir(parents=True, exist_ok=True)
    dest = out_dir / "last.mp3"

    if _use_elevenlabs(settings.tts_provider):
        print("(TTS: ElevenLabs)")
        _elevenlabs(text, dest)
    else:
        voice = settings.tts_voice or "en-GB-RyanNeural"
        print(f"(TTS: edge-tts / {voice})")
        _edge_tts(text, dest, voice=voice)

    if play:
        try:
            print("(speaking…)")
            play_audio(dest)
        except Exception as exc:  # noqa: BLE001 — never swallow the reply for a speaker glitch
            print(f"[TTS saved to {dest} — playback failed: {exc}]")
    return dest


def _use_elevenlabs(provider: str) -> bool:
    key = os.getenv("ELEVENLABS_API_KEY", "").strip()
    if not key:
        return False
    # Explicit edge-tts wins; otherwise key present → ElevenLabs (premium path).
    if provider.strip().lower() in {"edge-tts", "edge", "edge_tts"}:
        return False
    return provider.strip().lower() in {"elevenlabs", "eleven", "auto", ""}


def _for_speech(text: str) -> str:
    """Strip markdown / clutter so TTS does not sound like it is reading a document."""
    text = (text or "").strip()
    if not text:
        return ""
    text = re.sub(r"```[\s\S]*?```", " ", text)
    text = re.sub(r"`([^`]+)`", r"\1", text)
    text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)
    text = re.sub(r"[*_#~>]+", "", text)
    text = re.sub(r"\s+", " ", text).strip()
    # Keep spoken replies short; long tool dumps feel like narration.
    if len(text) > 600:
        cut = text[:600]
        if " " in cut:
            cut = cut.rsplit(" ", 1)[0]
        text = cut.rstrip(",;:") + "."
    return text


def _edge_tts(text: str, dest: Path, *, voice: str) -> None:
    try:
        import edge_tts
    except ImportError as exc:
        raise RuntimeError("edge-tts is not installed. pip install edge-tts") from exc

    async def _run() -> None:
        communicate = edge_tts.Communicate(text, voice=voice)
        await communicate.save(str(dest))

    asyncio.run(_run())


def _elevenlabs(text: str, dest: Path) -> None:
    import httpx

    voice = os.getenv("ELEVENLABS_VOICE_ID", _DEFAULT_ELEVEN_VOICE).strip() or _DEFAULT_ELEVEN_VOICE
    model = os.getenv("ELEVENLABS_MODEL", _DEFAULT_ELEVEN_MODEL).strip() or _DEFAULT_ELEVEN_MODEL
    key = os.environ["ELEVENLABS_API_KEY"].strip()
    response = httpx.post(
        f"https://api.elevenlabs.io/v1/text-to-speech/{voice}",
        headers={"xi-api-key": key, "Accept": "audio/mpeg"},
        json={
            "text": text,
            "model_id": model,
            "voice_settings": {
                "stability": 0.45,
                "similarity_boost": 0.75,
                "style": 0.15,
                "use_speaker_boost": True,
            },
        },
        timeout=60.0,
        params={"optimize_streaming_latency": 2},
    )
    response.raise_for_status()
    dest.write_bytes(response.content)
