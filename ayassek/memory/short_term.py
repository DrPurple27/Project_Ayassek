from __future__ import annotations

from collections import OrderedDict, defaultdict
from typing import Any

from ayassek.config.settings import settings


class ShortTermMemory:
    def __init__(self, max_messages: int = 0):
        self._max = max_messages or settings.memory.short_term.max_messages
        self._sessions: dict[str, list[dict[str, Any]]] = defaultdict(list)
        self._store: dict[str, str] = OrderedDict()

    def add(self, role: str, content: str, session_id: str = "default", **extra: Any):
        msg = {"role": role, "content": content, **extra}
        msgs = self._sessions[session_id]
        msgs.append(msg)
        if len(msgs) > self._max:
            msgs.pop(0)

    def get_messages(self, limit: int = 0, session_id: str = "default") -> list[dict[str, Any]]:
        msgs = self._sessions[session_id]
        if limit and limit < len(msgs):
            return msgs[-limit:]
        return list(msgs)

    def clear(self, session_id: str = "default"):
        if session_id in self._sessions:
            self._sessions[session_id].clear()

    def store(self, key: str, value: str):
        self._store[key] = value
        if len(self._store) > 100:
            self._store.popitem(last=False)

    def recall(self, key: str) -> str | None:
        return self._store.get(key)

    def get_all_stored(self) -> dict[str, str]:
        return dict(self._store)

    def to_list(self) -> list[dict[str, Any]]:
        return self._sessions.get("default", [])