from __future__ import annotations

import asyncio
from typing import Any

from ayassek.tools.base import BaseTool, ToolResult, ToolSpec


class WebSearchTool(BaseTool):
    name = "web_search"
    description = "Search the web using DuckDuckGo. Returns text summaries of results."

    def get_spec(self) -> ToolSpec:
        return ToolSpec(
            name=self.name,
            description=self.description,
            parameters={
                "query": {
                    "type": "string",
                    "description": "Search query",
                },
                "max_results": {
                    "type": "integer",
                    "description": "Maximum number of results (1-10)",
                    "default": 5,
                },
            },
            required=["query"],
        )

    async def execute(self, query: str, max_results: int = 5) -> ToolResult:
        try:
            from duckduckgo_search import DDGS

            def _search():
                with DDGS() as ddgs:
                    return list(ddgs.text(query, max_results=min(max_results, 10)))

            results = await asyncio.to_thread(_search)

            if not results:
                return ToolResult(
                    success=True,
                    output="No results found.",
                    data={"results": []},
                )

            output_lines = []
            for i, r in enumerate(results[:max_results], 1):
                title = r.get("title", "")
                body = r.get("body", "")
                href = r.get("href", "")
                output_lines.append(f"{i}. {title}\n   {body}\n   URL: {href}")

            return ToolResult(
                success=True,
                output="\n\n".join(output_lines),
                data={"results": results[:max_results]},
            )
        except Exception as e:
            return ToolResult(
                success=False,
                output="",
                error=f"Web search failed: {e}",
            )