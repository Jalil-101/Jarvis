"""Play an audio file with whatever the OS provides."""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path


def play_audio(path: Path) -> None:
    path = Path(path).resolve()
    if not path.is_file():
        raise FileNotFoundError(path)

    if sys.platform.startswith("win"):
        try:
            _play_windows_mci(path)
            return
        except OSError:
            pass

    try:
        import pygame  # type: ignore

        pygame.mixer.init()
        pygame.mixer.music.load(str(path))
        pygame.mixer.music.play()
        while pygame.mixer.music.get_busy():
            pygame.time.wait(100)
        pygame.mixer.quit()
        return
    except Exception:
        pass

    for cmd in (
        ["ffplay", "-nodisp", "-autoexit", "-loglevel", "quiet", str(path)],
        ["mpg123", "-q", str(path)],
        ["paplay", str(path)],
        ["afplay", str(path)],
    ):
        if shutil.which(cmd[0]):
            subprocess.run(cmd, check=False, timeout=120)
            return

    if sys.platform.startswith("win"):
        # Last resort: default associated player (WMP / Groove / etc.)
        subprocess.run(["cmd", "/c", "start", "/wait", "", str(path)], check=False, timeout=120)
        return

    raise RuntimeError(f"No audio player available for {path}")


def _play_windows_mci(path: Path) -> None:
    """Play MP3/WAV via winmm MCI and block until finished."""
    import ctypes
    from ctypes import wintypes

    winmm = ctypes.WinDLL("winmm")
    mci_send = winmm.mciSendStringW
    mci_send.argtypes = [wintypes.LPCWSTR, wintypes.LPWSTR, wintypes.UINT, wintypes.HANDLE]
    mci_send.restype = wintypes.DWORD
    mci_err = winmm.mciGetErrorStringW
    mci_err.argtypes = [wintypes.DWORD, wintypes.LPWSTR, wintypes.UINT]
    mci_err.restype = wintypes.BOOL

    buf = ctypes.create_unicode_buffer(512)
    alias = "jarvis_tts"

    def send(command: str) -> int:
        return int(mci_send(command, buf, 511, None))

    def explain(code: int) -> str:
        err_buf = ctypes.create_unicode_buffer(256)
        mci_err(code, err_buf, 255)
        return err_buf.value or f"MCI error {code}"

    send(f"close {alias}")
    opened = send(f'open "{path}" type mpegvideo alias {alias}')
    if opened:
        opened = send(f'open "{path}" alias {alias}')
    if opened:
        raise OSError(explain(opened))
    try:
        played = send(f"play {alias} wait")
        if played:
            raise OSError(explain(played))
    finally:
        send(f"close {alias}")
