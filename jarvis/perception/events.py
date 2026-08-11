"""Simple in-process event bus."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

Handler = Callable[["Event"], None]


@dataclass
class Event:
    kind: str
    payload: dict[str, Any]
    importance: float = 0.5
    ts: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class EventBus:
    def __init__(self) -> None:
        self._handlers: dict[str, list[Handler]] = defaultdict(list)

    def subscribe(self, kind: str, handler: Handler) -> None:
        self._handlers[kind].append(handler)

    def emit(self, event: Event) -> None:
        seen: set[int] = set()
        for handler in [*self._handlers.get(event.kind, []), *self._handlers.get("*", [])]:
            ident = id(handler)
            if ident in seen:
                continue
            seen.add(ident)
            handler(event)
