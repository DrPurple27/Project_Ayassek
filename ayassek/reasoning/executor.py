from __future__ import annotations

from typing import Any

from ayassek.tools.registry import ToolRegistry
from ayassek.utils.logging import get_logger


class ActionExecutor:
    def __init__(self, tool_registry: ToolRegistry):
        self._tool_registry = tool_registry
        self._logger = get_logger("executor")

    def get_openai_tools(self) -> list[dict[str, Any]]:
        return self._tool_registry.to_openai_tools()

    async def execute_tool(self, name: str, args: dict[str, Any]) -> str:
        tool = self._tool_registry.get(name)
        if not tool:
            return f"Error: Tool '{name}' not found. Available tools: {[t['name'] for t in self._tool_registry.list_tools()]}"
        self._logger.info("Executing tool: %s with args: %s", name, args)
        try:
            result = await tool.execute(**args)
            if result.success:
                return result.output
            else:
                return f"Tool '{name}' failed: {result.error or 'Unknown error'}"
        except Exception as e:
            self._logger.error("Tool execution error: %s", e)
            return f"Tool '{name}' raised an error: {e}"