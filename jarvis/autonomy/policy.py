"""When should Jarvis interrupt vs wait vs silently log?"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from jarvis.config_loader import Settings
from jarvis.memory.store import MemoryStore
from jarvis.perception.events import Event

SPEAK = "speak"
WAIT = "wait"
LOG = "logged"


def in_quiet_hours(settings: Settings, now: datetime | None = None) -> bool:
    now = now or datetime.now().astimezone()
    start = settings.quiet_hours_start
    end = settings.quiet_hours_end
    hour = now.hour
    if start == end:
        return False
    if start < end:
        return start <= hour < end
    return hour >= start or hour < end


def decide(event: Event, settings: Settings, memory: MemoryStore, *, now: datetime | None = None) -> str:
    """Return speak | wait | logged."""
    now = now or datetime.now(timezone.utc)
    if event.importance < settings.importance_threshold:
        return LOG
    if in_quiet_hours(settings, now.astimezone() if now.tzinfo else now):
        return WAIT
    since = (now - timedelta(hours=1)).isoformat()
    spoken = memory.count_recent_dispositions(SPEAK, since_iso=since)
    if spoken >= settings.max_proactive_per_hour:
        return WAIT
    return SPEAK
