from __future__ import annotations

import asyncio
from collections import defaultdict
from typing import Awaitable, Callable, Optional

from ayassek.core.events import Event, EventType
from ayassek.utils.logging import get_logger

EventHandler = Callable[[Event], Awaitable[None]]

_global_event_bus: Optional["AsyncEventBus"] = None


def get_event_bus() -> "AsyncEventBus":
    """Get the global event bus instance."""
    global _global_event_bus
    if _global_event_bus is None:
        _global_event_bus = AsyncEventBus()
    return _global_event_bus


def set_event_bus(bus: "AsyncEventBus"):
    """Set the global event bus instance."""
    global _global_event_bus
    _global_event_bus = bus


class AsyncEventBus:
    def __init__(self):
        self._subscribers: dict[EventType, list[EventHandler]] = defaultdict(list)
        self._global_subscribers: list[EventHandler] = []
        self._logger = get_logger("event_bus")

    def subscribe(self, event_type: EventType, handler: EventHandler):
        self._subscribers[event_type].append(handler)

    def subscribe_global(self, handler: EventHandler):
        self._global_subscribers.append(handler)

    def unsubscribe(self, event_type: EventType, handler: EventHandler):
        if handler in self._subscribers[event_type]:
            self._subscribers[event_type].remove(handler)

    async def emit(self, event: Event):
        tasks = []

        for handler in self._global_subscribers:
            tasks.append(self._safe_call(handler, event))

        for handler in self._subscribers.get(event.type, []):
            tasks.append(self._safe_call(handler, event))

        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

    async def _safe_call(self, handler: EventHandler, event: Event):
        try:
            await handler(event)
        except Exception as e:
            self._logger.error("Handler error for %s: %s", event.type.value, e)

    def clear(self):
        self._subscribers.clear()
        self._global_subscribers.clear()