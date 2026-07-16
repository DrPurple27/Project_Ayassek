from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Any


@dataclass
class SessionContext:
    session_id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    user_id: str = "default"
    messages: list[dict[str, Any]] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    active_tools: list[str] = field(default_factory=list)
    current_provider: str = ""
    current_model: str = ""

    def add_message(self, role: str, content: str, **extra: Any):
        msg = {"role": role, "content": content, **extra}
        self.messages.append(msg)

    def clear(self):
        self.messages.clear()
        self.metadata.clear()

    def to_dict(self) -> dict[str, Any]:
        return {
            "session_id": self.session_id,
            "user_id": self.user_id,
            "messages": self.messages[-20:],
            "metadata": self.metadata,
            "current_provider": self.current_provider,
            "current_model": self.current_model,
        }


class ContextManager:
    def __init__(self):
        self._sessions: dict[str, SessionContext] = {}

    def get_or_create(self, session_id: str | None = None) -> SessionContext:
        if session_id and session_id in self._sessions:
            return self._sessions[session_id]
        ctx = SessionContext(session_id=session_id or uuid.uuid4().hex[:12])
        self._sessions[ctx.session_id] = ctx
        return ctx

    def get(self, session_id: str) -> SessionContext | None:
        return self._sessions.get(session_id)

    def delete(self, session_id: str):
        self._sessions.pop(session_id, None)

    def clear_all(self):
        self._sessions.clear()