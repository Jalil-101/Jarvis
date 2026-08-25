"""Microphone device selection and diagnostics (Windows workshop)."""

from __future__ import annotations

import os
import time
from typing import Any

import numpy as np


def list_input_devices() -> list[dict[str, Any]]:
    import sounddevice as sd

    out: list[dict[str, Any]] = []
    default_in = sd.default.device[0] if sd.default.device else None
    for i, d in enumerate(sd.query_devices()):
        if int(d.get("max_input_channels") or 0) <= 0:
            continue
        name = str(d.get("name") or f"device-{i}")
        out.append(
            {
                "id": i,
                "name": name,
                "rate": int(d.get("default_samplerate") or 16000),
                "channels": int(d["max_input_channels"]),
                "default": i == default_in,
                "usable": _looks_usable(name),
            }
        )
    return out


def resolve_input_device() -> int | None:
    """Honor JARVIS_MIC_DEVICE (index or substring); else prefer a usable default."""
    import sounddevice as sd
    from dotenv import load_dotenv

    from jarvis.config_loader import repo_root

    # voice paths may run before get_settings(); still honor .env
    load_dotenv(repo_root() / ".env", encoding="utf-8-sig", override=False, interpolate=False)

    raw = os.getenv("JARVIS_MIC_DEVICE", "").strip()
    devices = list_input_devices()
    if raw:
        if raw.isdigit():
            return int(raw)
        needle = raw.lower()
        for d in devices:
            if needle in d["name"].lower():
                return int(d["id"])
        raise RuntimeError(f"JARVIS_MIC_DEVICE={raw!r} matched no input device.")

    default_in = sd.default.device[0] if sd.default.device else None
    for d in devices:
        if d["default"] and d["usable"]:
            return int(d["id"])
    for d in devices:
        if d["usable"]:
            return int(d["id"])
    return default_in if default_in is not None else None


def capture_channels(device: int | None = None) -> int:
    """Intel mic arrays often return silence on mono — capture stereo then downmix."""
    import sounddevice as sd

    if device is None:
        device = resolve_input_device()
    info = sd.query_devices(device)
    max_ch = int(info.get("max_input_channels") or 1)
    # Workshop default: stereo when the hardware exposes it.
    return 2 if max_ch >= 2 else 1


def capture_samplerate(device: int | None = None) -> int:
    import sounddevice as sd

    if device is None:
        device = resolve_input_device()
    info = sd.query_devices(device)
    return int(info.get("default_samplerate") or 44100)


def downmix_mono(block: np.ndarray) -> np.ndarray:
    """Collapse multi-channel capture to mono."""
    arr = np.asarray(block, dtype=np.float32)
    if arr.ndim == 1:
        return arr
    if arr.ndim == 2 and arr.shape[1] > 1:
        return np.mean(arr, axis=1).astype(np.float32)
    return arr.reshape(-1)


def block_level(block: np.ndarray) -> tuple[float, float]:
    mono = downmix_mono(block)
    if mono.size == 0:
        return 0.0, 0.0
    rms = float(np.sqrt(np.mean(np.square(mono))))
    peak = float(np.max(np.abs(mono)))
    return rms, peak


def record_seconds(
    seconds: float,
    *,
    device: int | None = None,
    discard_warmup: float = 0.15,
) -> tuple[np.ndarray, int, int]:
    """Record audio; returns (mono float32 samples, samplerate, device id)."""
    import sounddevice as sd

    device = resolve_input_device() if device is None else device
    rate = capture_samplerate(device)
    channels = capture_channels(device)
    total = seconds + discard_warmup
    raw = sd.rec(
        int(total * rate),
        samplerate=rate,
        channels=channels,
        dtype="float32",
        device=device,
    )
    sd.wait()
    skip = int(discard_warmup * rate)
    mono = downmix_mono(raw[skip:])
    return mono, rate, int(device)


def measure_level(*, seconds: float = 1.5, device: int | None = None) -> dict[str, float | int | str]:
    import sounddevice as sd

    if device is None:
        device = resolve_input_device()
    mono, rate, device = record_seconds(seconds, device=device)
    rms = float(np.sqrt(np.mean(np.square(mono)))) if mono.size else 0.0
    peak = float(np.max(np.abs(mono))) if mono.size else 0.0
    info = sd.query_devices(device)
    return {
        "device": int(device),
        "name": str(info.get("name") or ""),
        "rate": rate,
        "channels": capture_channels(device),
        "rms": rms,
        "peak": peak,
    }


def mic_test(*, seconds: float = 4.0) -> int:
    """Live level meter. Tries each usable mic with stereo downmix."""
    import sounddevice as sd

    print("=== Jarvis mic test ===")
    print()
    print("If Windows Sound test works but Jarvis does not, we now capture STEREO")
    print("(Intel laptop mics are often silent in mono). Talk during each countdown.")
    print()

    devices = [d for d in list_input_devices() if d["usable"]]
    if not devices:
        devices = list_input_devices()

    best_id = None
    best_peak = 0.0
    for d in devices:
        print(f"Testing [{d['id']}] {d['name']}  (channels={capture_channels(d['id'])})")
        for t in range(3, 0, -1):
            print(f"  Speak in {t}…", flush=True)
            time.sleep(1)
        print("  GO — talk now…")
        try:
            mono, rate, dev_id = record_seconds(seconds, device=d["id"])
            rms = float(np.sqrt(np.mean(np.square(mono)))) if mono.size else 0.0
            peak = float(np.max(np.abs(mono))) if mono.size else 0.0
            bar = "#" * min(30, int(peak * 200))
            print(f"  peak={peak:.4f} rms={rms:.4f} |{bar:<30}|")
            if peak > best_peak:
                best_peak = peak
                best_id = dev_id
        except Exception as exc:  # noqa: BLE001
            print(f"  skipped ({exc})")
        print()

    print("=== Summary ===")
    if best_id is None or best_peak < 0.01:
        print("Still no usable speech signal.")
        print("Check Sound settings → Input: same mic selected, volume 80%+, not muted.")
        print("Then re-run: .\\scripts\\run.cmd mic-test")
        return 1

    print(f"Best mic: [{best_id}] peak={best_peak:.4f}")
    print("Add to .env (save with Ctrl+S):")
    print(f"  JARVIS_MIC_DEVICE={best_id}")
    if best_peak < 0.03:
        print("Signal is weak — move closer or raise input volume.")
    print("Next: .\\scripts\\run.cmd voice")
    return 0


def _looks_usable(name: str) -> bool:
    low = name.lower()
    bad = ("mapper", "primary", "stereo mix", "pc speaker", "what u hear", "loopback")
    return not any(b in low for b in bad)
