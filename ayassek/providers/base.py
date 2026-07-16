from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, AsyncIterator


@dataclass
class ModelInfo:
    id: str
    name: str
    provider: str
    supports_streaming: bool = False
    supports_tools: bool = False
    supports_vision: bool = False


@dataclass
class ChatMessage:
    role: str
    content: str | list[dict[str, Any]]
    tool_calls: list[dict[str, Any]] | None = None
    tool_call_id: str | None = None


@dataclass
class ChatChunk:
    token: str = ""
    finish_reason: str | None = None
    tool_calls: list[dict[str, Any]] | None = None
    usage: dict[str, int] | None = None


@dataclass
class ChatResponse:
    message: ChatMessage
    usage: dict[str, int] | None = None
    model: str = ""


class BaseProvider(ABC):
    provider_id: str = "base"

    def __init__(self, base_url: str, api_key: str | None = None):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key or ""

    @abstractmethod
    async def list_models(self) -> list[ModelInfo]:
        ...

    @abstractmethod
    async def chat(
        self,
        messages: list[ChatMessage],
        model: str,
        stream: bool = False,
        tools: list[dict[str, Any]] | None = None,
        **kwargs: Any,
    ) -> AsyncIterator[ChatChunk] | ChatResponse:
        ...

    @abstractmethod
    async def health_check(self) -> bool:
        ...

    async def close(self):
        pass

    def supports_streaming(self) -> bool:
        return False

    def supports_tools(self) -> bool:
        return False

    def supports_vision(self) -> bool:
        return False

    def to_dict(self) -> dict[str, Any]:
        return {
            "provider_id": self.provider_id,
            "base_url": self.base_url,
            "models": [],
            "streaming": self.supports_streaming(),
            "tools": self.supports_tools(),
            "vision": self.supports_vision(),
        }