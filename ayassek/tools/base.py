from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass
class ToolResult:
    success: bool
    output: str
    data: dict[str, Any] = field(default_factory=dict)
    error: str | None = None


@dataclass
class ToolSpec:
    name: str
    description: str
    parameters: dict[str, Any]
    required: list[str] | None = None


class BaseTool(ABC):
    name: str = ""
    description: str = ""

    @abstractmethod
    async def execute(self, **kwargs: Any) -> ToolResult:
        ...

    def to_openai_tool(self) -> dict[str, Any]:
        spec = self.get_spec()
        return {
            "type": "function",
            "function": {
                "name": spec.name,
                "description": spec.description,
                "parameters": {
                    "type": "object",
                    "properties": spec.parameters,
                    "required": spec.required or [],
                },
            },
        }

    def get_spec(self) -> ToolSpec:
        raise NotImplementedError