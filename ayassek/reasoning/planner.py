from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from ayassek.utils.logging import get_logger

logger = get_logger("planner")


class StepStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass
class PlanStep:
    id: str
    action: str
    description: str
    tool: str | None = None
    args: dict[str, Any] = field(default_factory=dict)
    dependencies: list[str] = field(default_factory=list)
    status: StepStatus = StepStatus.PENDING
    result: str | None = None


@dataclass
class Plan:
    id: str
    goal: str
    steps: list[PlanStep]
    context: dict[str, Any] = field(default_factory=dict)
    created_at: float = 0.0


DECOMPOSITION_PROMPT = """You are a task planning assistant. Break down the following goal into a sequence of steps.

Goal: {goal}

Available tools: {tools}

For each step, specify:
- action: short action name
- description: what this step does
- tool: tool name to use (or null if reasoning-only)
- args: arguments for the tool (JSON object, empty for reasoning-only steps)
- dependencies: step IDs this step depends on (use step index numbers, 0-based)

Tool selection guide:
- "web_search": for internet research, finding information online
- "run_code": for executing shell commands (ls, cat, mkdir, grep, find, pip install, etc.) or Python scripts
- "file_read" / "file_write" / "file_list" / "file_glob" / "file_grep": for file operations
- "remember" / "recall" / "brain_search" / "rag_query": for storing/retrieving knowledge
- "system_info": for checking system resources, uptime, processes
- "voice_speak" / "voice_transcribe": for TTS speech and STT transcription
- "browser": for opening URLs, screenshots, web page analysis

Respond with a JSON array of steps. Each step is an object with fields: action, description, tool (or null), args (object), dependencies (array of ints).

Example:
[
  {{"action": "analyze", "description": "Analyze the user's request...", "tool": null, "args": {{}}, "dependencies": []}},
  {{"action": "search", "description": "Search for relevant information", "tool": "web_search", "args": {{"query": "..."}}, "dependencies": [0]}}
]"""


class AdvancedPlanner:
    def __init__(self, provider_manager=None):
        self._provider_manager = provider_manager
        self._logger = logger

    async def plan(self, goal: str, context: dict[str, Any] | None = None, tools: list[str] | None = None) -> Plan:
        plan_id = uuid.uuid4().hex[:12]
        import time

        try:
            plan = await self._llm_decompose(goal, tools or [])
            plan.id = plan_id
            plan.goal = goal
            plan.context = context or {}
            plan.created_at = time.time()
            return plan
        except Exception as e:
            self._logger.warning("LLM decomposition failed, using fallback: %s", e)
            steps = [
                PlanStep(id=f"step_{uuid.uuid4().hex[:8]}", action="analyze", description=f"Analyze: {goal}"),
                PlanStep(id=f"step_{uuid.uuid4().hex[:8]}", action="execute", description="Execute plan", dependencies=[f"step_0"]),
                PlanStep(id=f"step_{uuid.uuid4().hex[:8]}", action="reflect", description="Reflect on results", dependencies=[f"step_1"]),
            ]
            for i, s in enumerate(steps):
                s.id = f"step_{i}"
            return Plan(
                id=plan_id, goal=goal, steps=steps,
                context=context or {}, created_at=time.time(),
            )

    async def _llm_decompose(self, goal: str, tools: list[str]) -> Plan:
        if not self._provider_manager:
            raise ValueError("No provider manager available for LLM decomposition")

        provider = self._provider_manager.get_active_provider()
        if not provider:
            raise ValueError("No active provider")

        from ayassek.providers.base import ChatMessage

        tools_str = ", ".join(tools) if tools else "No tools specified"
        prompt_text = DECOMPOSITION_PROMPT.format(goal=goal, tools=tools_str)

        response = await provider.chat(
            [ChatMessage(role="user", content=prompt_text)],
            model=self._provider_manager.get_active_model(),
            stream=False,
            temperature=0.3,
        )

        content = response.message.content if hasattr(response, "message") else str(response)
        content = content.strip()

        if content.startswith("```"):
            content = content.split("\n", 1)[1]
            content = content.rsplit("\n", 1)[0] if content.endswith("```") else content
            content = content.rstrip("`")

        steps_data = json.loads(content)
        steps = []
        for sd in steps_data:
            step = PlanStep(
                id=f"step_{len(steps)}",
                action=sd.get("action", "unknown"),
                description=sd.get("description", ""),
                tool=sd.get("tool"),
                args=sd.get("args", {}),
                dependencies=[f"step_{d}" for d in sd.get("dependencies", [])],
            )
            steps.append(step)

        return Plan(id="", goal=goal, steps=steps)

    def to_prompt(self, plan: Plan) -> str:
        lines = ["## Current Plan:"]
        lines.append(f"Goal: {plan.goal}")
        lines.append("")
        for s in plan.steps:
            dep_str = f" (after: {', '.join(s.dependencies)})" if s.dependencies else ""
            status_mark = {
                StepStatus.COMPLETED: "✓",
                StepStatus.RUNNING: "▶",
                StepStatus.FAILED: "✗",
                StepStatus.SKIPPED: "○",
                StepStatus.PENDING: "·",
            }.get(s.status, "·")
            tool_str = f" [{s.tool}]" if s.tool else ""
            lines.append(f"  {status_mark} {s.action}: {s.description}{tool_str}{dep_str}")
        return "\n".join(lines)
