"""British TTS via edge-tts (default) or ElevenLabs if configured."""

from __future__ import annotations

import asyncio
import os
from pathlib import Path

from jarvis.config_loader import get_settings
from jarvis.voice.playback import play_audio


def speak(text: str, *, play: bool = True) -> Path:
    """Synthesise speech and optionally play it. Returns the audio file path."""
    settings = get_settings()
    text = (text or "").strip()
    if not text:
        raise ValueError("Nothing to speak.")
    out_dir = settings.data_dir / "tts"
    out_dir.mkdir(parents=True, exist_ok=True)
    dest = out_dir / "last.mp3"

    provider = settings.tts_provider
    if provider == "elevenlabs" and os.getenv("ELEVENLABS_API_KEY"):
        _elevenlabs(text, dest)
    else:
        _edge_tts(text, dest, voice=settings.tts_voice)

    if play:
        try:
            print("(speaking…)")
            play_audio(dest)
        except Exception as exc:  # noqa: BLE001 — never swallow the reply for a speaker glitch
            print(f"[TTS saved to {dest} — playback failed: {exc}]")
    return dest


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

    voice = os.getenv("ELEVENLABS_VOICE_ID", "JBFqnCBsd6RMkjVDRZzb")
    key = os.environ["ELEVENLABS_API_KEY"]
    response = httpx.post(
        f"https://api.elevenlabs.io/v1/text-to-speech/{voice}",
        headers={"xi-api-key": key, "Accept": "audio/mpeg"},
        json={"text": text, "model_id": "eleven_multilingual_v2"},
        timeout=60.0,
    )
    response.raise_for_status()
    dest.write_bytes(response.content)
