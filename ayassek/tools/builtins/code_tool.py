from __future__ import annotations

import tempfile
import uuid
from pathlib import Path

from ayassek.config.settings import settings
from ayassek.tools.base import BaseTool, ToolResult, ToolSpec
from ayassek.utils.logging import get_logger

logger = get_logger(__name__)


class CodeExecutionTool(BaseTool):
    name: str = "run_code"
    description: str = "Execute shell commands or Python scripts. Use for: running system commands (ls, cat, mkdir, grep, find), executing scripts, or running Python operations."

    def __init__(self):
        self._sandbox_image = settings.sandbox.image
        self._timeout = settings.sandbox.timeout
        self._memory_limit = settings.sandbox.memory_limit
        self._cpu_limit = settings.sandbox.cpu_limit
        self._network = settings.sandbox.network

    def get_spec(self) -> ToolSpec:
        return ToolSpec(
            name=self.name,
            description=self.description,
            parameters={
                "code": {
                    "type": "string",
                    "description": "Code to execute",
                },
                "language": {
                    "type": "string",
                    "description": "Language: 'python' (default), 'sh', 'bash'",
                    "enum": ["python", "sh", "bash"],
                    "default": "python",
                },
                "timeout": {
                    "type": "integer",
                    "description": "Timeout in seconds (default: 30)",
                    "default": 30,
                },
            },
            required=["code"],
        )

    async def execute(self, code: str, language: str = "python", timeout: int = 30) -> ToolResult:
        if not code.strip():
            return ToolResult(success=False, output="No code provided.")

        try:
            import asyncio
            import subprocess

            ext = ".py" if language == "python" else ".sh"
            tmp = Path(tempfile.mkdtemp()) / f"script_{uuid.uuid4().hex[:8]}{ext}"
            tmp.write_text(code)

            cmd = [
                "podman", "run", "--rm",
                "--network", self._network,
                "--memory", self._memory_limit,
                "--cpus", self._cpu_limit,
                "--pids-limit", "50",
                "--volume", f"{tmp}:/tmp/script{ext}:Z",
                self._sandbox_image,
            ]

            if language == "python":
                cmd += ["python", f"/tmp/script{ext}"]
            else:
                cmd += ["sh", f"/tmp/script{ext}"]

            effective_timeout = min(timeout, self._timeout)

            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )

            try:
                stdout, stderr = await asyncio.wait_for(
                    proc.communicate(), timeout=effective_timeout
                )
            except asyncio.TimeoutError:
                proc.kill()
                await proc.wait()
                return ToolResult(
                    success=False,
                    output=f"Execution timed out after {effective_timeout}s.",
                )

            out_text = stdout.decode("utf-8", errors="replace")
            err_text = stderr.decode("utf-8", errors="replace")
            output_parts = [out_text]
            if err_text:
                output_parts.append(f"\n[stderr]\n{err_text}")

            result_text = "".join(output_parts).strip()
            success = proc.returncode == 0

            return ToolResult(
                success=success,
                output=result_text or ("(no output)" if success else f"Exit code: {proc.returncode}"),
                data={"exit_code": proc.returncode, "language": language},
            )

        except Exception as e:
            logger.error("Code execution failed: %s", e)
            return ToolResult(success=False, output=f"Execution error: {e}")
