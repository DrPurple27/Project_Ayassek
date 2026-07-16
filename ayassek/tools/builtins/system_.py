from __future__ import annotations

import asyncio
import os
import platform
from typing import Any

from ayassek.tools.base import BaseTool, ToolResult, ToolSpec


class ShellTool(BaseTool):
    name = "run_command"
    description = "Execute a shell command and return its output. Use cautiously."

    def get_spec(self) -> ToolSpec:
        return ToolSpec(
            name=self.name,
            description=self.description,
            parameters={
                "command": {
                    "type": "string",
                    "description": "Shell command to execute",
                },
                "timeout": {
                    "type": "integer",
                    "description": "Timeout in seconds",
                    "default": 30,
                },
            },
            required=["command"],
        )

    async def execute(self, command: str, timeout: int = 30) -> ToolResult:
        try:
            proc = await asyncio.create_subprocess_shell(
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(), timeout=timeout
            )
            output = stdout.decode() if stdout else ""
            err = stderr.decode() if stderr else ""
            return ToolResult(
                success=proc.returncode == 0,
                output=output or err,
                data={"returncode": proc.returncode},
                error=err if proc.returncode != 0 else None,
            )
        except asyncio.TimeoutError:
            proc.kill()
            await proc.wait()
            return ToolResult(success=False, output="", error="Command timed out")
        except Exception as e:
            return ToolResult(success=False, output="", error=str(e))


class SystemInfoTool(BaseTool):
    name = "system_info"
    description = "Get information about the system: OS, CPU, memory, disk, uptime."

    def get_spec(self) -> ToolSpec:
        return ToolSpec(
            name=self.name,
            description=self.description,
            parameters={},
            required=[],
        )

    async def execute(self) -> ToolResult:
        try:
            import shutil

            total, used, free = shutil.disk_usage("/")
            return ToolResult(
                success=True,
                output=(
                    f"OS: {platform.system()} {platform.release()}\n"
                    f"Hostname: {platform.node()}\n"
                    f"Python: {platform.python_version()}\n"
                    f"CPU: {os.cpu_count()} cores\n"
                    f"Disk: {used // (2**30)}GB used / {total // (2**30)}GB total"
                ),
                data={
                    "os": platform.system(),
                    "python_version": platform.python_version(),
                    "cpu_count": os.cpu_count(),
                    "hostname": platform.node(),
                },
            )
        except Exception as e:
            return ToolResult(success=False, output="", error=str(e))