from __future__ import annotations

from pathlib import Path
from typing import Any

from ayassek.tools.base import BaseTool, ToolResult, ToolSpec
from ayassek.utils.logging import get_logger

logger = get_logger(__name__)


PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent


def _safe_path(path: str) -> Path | None:
    resolved = (PROJECT_ROOT / path).resolve()
    if not str(resolved).startswith(str(PROJECT_ROOT)):
        return None
    return resolved


class FileReadTool(BaseTool):
    name: str = "file_read"
    description: str = "Read the contents of a file"

    def get_spec(self) -> ToolSpec:
        return ToolSpec(
            name=self.name,
            description=self.description,
            parameters={
                "path": {
                    "type": "string",
                    "description": "Relative or absolute path to the file",
                },
                "max_size": {
                    "type": "integer",
                    "description": "Maximum bytes to read (default: 1MB)",
                    "default": 1048576,
                },
            },
            required=["path"],
        )

    async def execute(self, path: str, max_size: int = 1048576) -> ToolResult:
        safe = _safe_path(path)
        if safe is None:
            return ToolResult(success=False, output=f"Access denied: path '{path}' is outside workspace.")
        if not safe.exists():
            return ToolResult(success=False, output=f"File not found: {path}")
        if not safe.is_file():
            return ToolResult(success=False, output=f"Not a file: {path}")
        try:
            content = safe.read_text(encoding="utf-8", errors="replace")
            if len(content) > max_size:
                content = content[:max_size] + f"\n... (truncated at {max_size} bytes)"
            return ToolResult(success=True, output=content, data={"size": len(content), "path": str(safe)})
        except Exception as e:
            return ToolResult(success=False, output=f"Failed to read file: {e}")


class FileWriteTool(BaseTool):
    name: str = "file_write"
    description: str = "Write content to a file"

    def get_spec(self) -> ToolSpec:
        return ToolSpec(
            name=self.name,
            description=self.description,
            parameters={
                "path": {
                    "type": "string",
                    "description": "Relative path to write to",
                },
                "content": {
                    "type": "string",
                    "description": "Content to write",
                },
            },
            required=["path", "content"],
        )

    async def execute(self, path: str, content: str) -> ToolResult:
        safe = _safe_path(path)
        if safe is None:
            return ToolResult(success=False, output=f"Access denied: path '{path}' is outside workspace.")
        try:
            safe.parent.mkdir(parents=True, exist_ok=True)
            safe.write_text(content, encoding="utf-8")
            return ToolResult(success=True, output=f"Written {len(content)} bytes to {path}")
        except Exception as e:
            return ToolResult(success=False, output=f"Failed to write file: {e}")


class FileListTool(BaseTool):
    name: str = "file_list"
    description: str = "List files and directories in a path"

    def get_spec(self) -> ToolSpec:
        return ToolSpec(
            name=self.name,
            description=self.description,
            parameters={
                "path": {
                    "type": "string",
                    "description": "Directory path to list (default: '.')",
                    "default": ".",
                },
                "pattern": {
                    "type": "string",
                    "description": "Optional glob pattern to filter (e.g., '*.py')",
                    "default": "",
                },
            },
            required=[],
        )

    async def execute(self, path: str = ".", pattern: str = "") -> ToolResult:
        safe = _safe_path(path)
        if safe is None:
            return ToolResult(success=False, output=f"Access denied: path '{path}' is outside workspace.")
        if not safe.exists():
            return ToolResult(success=False, output=f"Path not found: {path}")
        if not safe.is_dir():
            return ToolResult(success=False, output=f"Not a directory: {path}")
        try:
            if pattern:
                items = list(safe.glob(pattern))
            else:
                items = list(safe.iterdir())

            lines = []
            for item in sorted(items):
                suffix = "/" if item.is_dir() else ""
                size = item.stat().st_size if item.is_file() else 0
                lines.append(f"{item.name}{suffix}  ({size} bytes)" if size else item.name + suffix)

            return ToolResult(
                success=True,
                output="\n".join(lines) if lines else "(empty directory)",
                data={"count": len(lines), "path": str(safe)},
            )
        except Exception as e:
            return ToolResult(success=False, output=f"Failed to list directory: {e}")


class FileGlobTool(BaseTool):
    name: str = "file_glob"
    description: str = "Search for files matching a glob pattern"

    def get_spec(self) -> ToolSpec:
        return ToolSpec(
            name=self.name,
            description=self.description,
            parameters={
                "pattern": {
                    "type": "string",
                    "description": "Glob pattern (e.g., '**/*.py', 'src/**/*.ts')",
                },
                "root": {
                    "type": "string",
                    "description": "Root directory (default: '.')",
                    "default": ".",
                },
                "max_results": {
                    "type": "integer",
                    "description": "Maximum results (default: 100)",
                    "default": 100,
                },
            },
            required=["pattern"],
        )

    async def execute(self, pattern: str, root: str = ".", max_results: int = 100) -> ToolResult:
        safe_root = _safe_path(root)
        if safe_root is None:
            return ToolResult(success=False, output=f"Access denied: root '{root}' is outside workspace.")
        try:
            matches = list(safe_root.glob(pattern))
            if len(matches) > max_results:
                matches = matches[:max_results]
            lines = [str(m.relative_to(PROJECT_ROOT)) for m in sorted(matches)]
            return ToolResult(
                success=True,
                output="\n".join(lines) if lines else "(no matches)",
                data={"count": len(lines), "pattern": pattern, "truncated": len(matches) > max_results},
            )
        except Exception as e:
            return ToolResult(success=False, output=f"Glob failed: {e}")


class FileGrepTool(BaseTool):
    name: str = "file_grep"
    description: str = "Search file contents using a regex pattern"

    def get_spec(self) -> ToolSpec:
        return ToolSpec(
            name=self.name,
            description=self.description,
            parameters={
                "pattern": {
                    "type": "string",
                    "description": "Regex pattern to search for",
                },
                "glob": {
                    "type": "string",
                    "description": "File glob pattern (default: '*')",
                    "default": "*",
                },
                "root": {
                    "type": "string",
                    "description": "Root directory (default: '.')",
                    "default": ".",
                },
                "max_results": {
                    "type": "integer",
                    "description": "Maximum results (default: 50)",
                    "default": 50,
                },
            },
            required=["pattern"],
        )

    async def execute(self, pattern: str, glob: str = "*", root: str = ".", max_results: int = 50) -> ToolResult:
        safe_root = _safe_path(root)
        if safe_root is None:
            return ToolResult(success=False, output=f"Access denied: root '{root}' is outside workspace.")
        try:
            import re
            matches = []
            for p in safe_root.rglob(glob):
                if not p.is_file():
                    continue
                try:
                    text = p.read_text(encoding="utf-8", errors="replace")
                    for i, line in enumerate(text.splitlines(), 1):
                        if re.search(pattern, line):
                            rel = str(p.relative_to(PROJECT_ROOT))
                            matches.append(f"{rel}:{i}: {line[:200]}")
                            if len(matches) >= max_results:
                                break
                except Exception:
                    continue
                if len(matches) >= max_results:
                    break
            return ToolResult(
                success=True,
                output="\n".join(matches) if matches else "(no matches)",
                data={"count": len(matches), "pattern": pattern},
            )
        except Exception as e:
            return ToolResult(success=False, output=f"Grep failed: {e}")
