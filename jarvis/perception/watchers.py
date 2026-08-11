"""Host watchers: battery, disk, scheduled clock ticks."""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

from jarvis.perception.events import Event, EventBus


def poll_battery(bus: EventBus) -> None:
    pct = _battery_percent()
    if pct is None:
        return
    importance = 0.9 if pct <= 12 else 0.4 if pct <= 20 else 0.1
    bus.emit(Event("battery", {"percent": pct}, importance=importance))


def poll_disk(bus: EventBus, path: Path) -> None:
    try:
        usage = shutil.disk_usage(path)
    except OSError:
        return
    free_gb = usage.free / 1024**3
    importance = 0.85 if free_gb < 2 else 0.2
    bus.emit(Event("disk", {"free_gb": round(free_gb, 2)}, importance=importance))


def emit_tick(bus: EventBus, name: str, payload: dict | None = None) -> None:
    bus.emit(Event("schedule", {"name": name, **(payload or {})}, importance=0.5))


def _battery_percent() -> int | None:
    if sys.platform.startswith("win"):
        cmd = [
            "powershell",
            "-NoProfile",
            "-Command",
            "(Get-WmiObject Win32_Battery).EstimatedChargeRemaining",
        ]
        completed = subprocess.run(cmd, capture_output=True, text=True, timeout=10, check=False)
        text = (completed.stdout or "").strip()
        if text.isdigit():
            return int(text)
        return None
    supply = Path("/sys/class/power_supply")
    if supply.is_dir():
        for bat in supply.glob("BAT*"):
            cap = bat / "capacity"
            if cap.is_file():
                try:
                    return int(cap.read_text().strip())
                except ValueError:
                    return None
    return None
