from __future__ import annotations

from typing import Any

from ayassek.tools.base import BaseTool, ToolResult, ToolSpec


class RememberTool(BaseTool):
    name = "remember"
    description = "Store a piece of information in short-term memory for the current session."

    def __init__(self, memory_ref: Any = None):
        super().__init__()
        self._memory = memory_ref

    def get_spec(self) -> ToolSpec:
        return ToolSpec(
            name=self.name,
            description=self.description,
            parameters={
                "key": {
                    "type": "string",
                    "description": "Identifier for the information",
                },
                "value": {
                    "type": "string",
                    "description": "The information to remember",
                },
            },
            required=["key", "value"],
        )

    async def execute(self, key: str, value: str) -> ToolResult:
        if self._memory:
            self._memory.store(key, value)
            return ToolResult(success=True, output=f"Stored '{key}' in memory.")
        return ToolResult(success=False, output="", error="Memory not available")


class RecallTool(BaseTool):
    name = "recall"
    description = "Retrieve stored information from short-term memory by key."

    def __init__(self, memory_ref: Any = None):
        super().__init__()
        self._memory = memory_ref

    def get_spec(self) -> ToolSpec:
        return ToolSpec(
            name=self.name,
            description=self.description,
            parameters={
                "key": {
                    "type": "string",
                    "description": "Identifier for the information to retrieve",
                },
            },
            required=["key"],
        )

    async def execute(self, key: str) -> ToolResult:
        if self._memory:
            value = self._memory.recall(key)
            if value is not None:
                return ToolResult(success=True, output=f"{key}: {value}", data={"value": value})
            return ToolResult(success=True, output=f"No information stored under '{key}'.")
        return ToolResult(success=False, output="", error="Memory not available")


class RAGQueryTool(BaseTool):
    name = "rag_query"
    description = "Search the RAG (Retrieval-Augmented Generation) knowledge base for relevant information from ingested documents and reference materials."

    def __init__(self, memory_ref: Any = None):
        super().__init__()
        self._memory = memory_ref

    def get_spec(self) -> ToolSpec:
        return ToolSpec(
            name=self.name,
            description=self.description,
            parameters={
                "query": {
                    "type": "string",
                    "description": "Search query to find relevant information",
                },
                "top_k": {
                    "type": "integer",
                    "description": "Number of results to return (default: 5)",
                    "default": 5,
                },
            },
            required=["query"],
        )

    async def execute(self, query: str, top_k: int = 5) -> ToolResult:
        if not self._memory:
            return ToolResult(success=False, output="", error="Memory not available")
        try:
            result = self._memory.rag_query(query, top_k=top_k, rerank=True)
            if result.get("reranked"):
                output_lines = [f"RAG results for: {query}", ""]
                for i, r in enumerate(result["reranked"]):
                    src = r.get("source", "unknown")
                    text = r.get("text", "")[:500]
                    score = r.get("rerank_score", r.get("similarity_score", 0))
                    output_lines.append(f"[{i+1}] Score: {score:.3f} | Source: {src}")
                    output_lines.append(text[:200])
                    output_lines.append("")
                return ToolResult(success=True, output="\n".join(output_lines))
            else:
                return ToolResult(success=True, output=f"No relevant results found for: {query}")
        except Exception as e:
            return ToolResult(success=False, output="", error=f"RAG query failed: {e}")


class BrainSearchTool(BaseTool):
    name = "brain_search"
    description = "Search the Second Brain knowledge base (entities, facts, notes) for stored knowledge about people, projects, concepts, and references."

    def __init__(self, memory_ref: Any = None):
        super().__init__()
        self._memory = memory_ref

    def get_spec(self) -> ToolSpec:
        return ToolSpec(
            name=self.name,
            description=self.description,
            parameters={
                "query": {
                    "type": "string",
                    "description": "Search query to find relevant facts and notes",
                },
                "category": {
                    "type": "string",
                    "description": "Filter by category (projects, people, concepts, meetings, references, tasks)",
                    "default": None,
                },
            },
            required=["query"],
        )

    async def execute(self, query: str, category: str | None = None) -> ToolResult:
        if not self._memory:
            return ToolResult(success=False, output="", error="Memory not available")
        try:
            results = self._memory.sb_search(query, category=category, top_k=10)
            if results:
                output_lines = [f"Second Brain results for: {query}", ""]
                for r in results[:10]:
                    ent = r.get("entity", "unknown")
                    cat = r.get("category", "general")
                    text = r.get("text", "")[:300]
                    score = r.get("score", 0)
                    output_lines.append(f"[{cat}/{ent}] Score: {score:.3f}")
                    output_lines.append(text)
                    output_lines.append("")
                return ToolResult(success=True, output="\n".join(output_lines))
            else:
                return ToolResult(success=True, output=f"No Second Brain results found for: {query}")
        except Exception as e:
            return ToolResult(success=False, output="", error=f"Brain search failed: {e}")