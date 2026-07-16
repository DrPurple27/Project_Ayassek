from __future__ import annotations

from enum import Enum
from typing import Any

from ayassek.core.events import Event
from ayassek.utils.logging import get_logger

logger = get_logger("reflection")


class ReflectionDecision(str, Enum):
    CONTINUE = "continue"
    RETRY = "retry"
    REPLAN = "replan"
    ASK_USER = "ask_user"
    DONE = "done"


REFLECTION_PROMPT = """You are a reflection agent. Evaluate progress on the current goal.

Goal: {goal}

Plan progress:
{plan_progress}

Recent results:
{results}

Respond with a JSON object:
{{
  "decision": "continue|retry|replan|ask_user|done",
  "reasoning": "Short explanation",
  "message": "Optional message to user (for ask_user)"
}}

Guidelines:
- continue: Everything is on track
- retry: Something failed, retry the last step
- replan: The plan needs adjustment
- ask_user: Need clarification or input
- done: Goal achieved"""


class ReflectionLoop:
    def __init__(self, provider_manager=None):
        self._provider_manager = provider_manager
        self._logger = logger
        self._history: list[dict[str, Any]] = []

    async def record(self, event: Event):
        entry: dict[str, Any] = {"event": str(event.type), "details": event.data}
        self._history.append(entry)
        if len(self._history) > 100:
            self._history.pop(0)

    def get_history(self) -> list[dict[str, Any]]:
        return self._history

    def get_recent(self, n: int = 5) -> list[dict[str, Any]]:
        return self._history[-n:]

    def clear(self):
        self._history.clear()

    async def reflect(self, goal: str, plan_steps: list[dict], results: list[dict]) -> dict:
        try:
            decision = await self._llm_reflect(goal, plan_steps, results)
        except Exception as e:
            self._logger.debug("LLM reflection failed, using heuristic: %s", e)
            decision = self._heuristic_reflect(plan_steps, results)
        return decision

    async def _llm_reflect(self, goal: str, plan_steps: list[dict], results: list[dict]) -> dict:
        if not self._provider_manager:
            return self._heuristic_reflect(plan_steps, results)

        provider = self._provider_manager.get_active_provider()
        if not provider:
            return self._heuristic_reflect(plan_steps, results)

        from ayassek.providers.base import ChatMessage

        plan_lines = []
        for s in plan_steps:
            status = s.get("status", "pending")
            plan_lines.append(f"  [{status}] {s.get('action', '?')}: {s.get('description', '')}")
        plan_progress = "\n".join(plan_lines)

        result_lines = []
        for r in results[-3:]:
            result_lines.append(f"- {r.get('step', '?')}: {str(r.get('result', ''))[:200]}")
        result_text = "\n".join(result_lines)

        prompt = REFLECTION_PROMPT.format(
            goal=goal, plan_progress=plan_progress, results=result_text,
        )

        response = await provider.chat(
            [ChatMessage(role="user", content=prompt)],
            model=self._provider_manager.get_active_model(),
            stream=False,
            temperature=0.3,
        )

        import json
        content = response.message.content if hasattr(response, "message") else str(response)
        if "```" in content:
            content = content.split("```")[1].split("```")[0]
            if content.startswith("json"):
                content = content[4:]

        try:
            return json.loads(content.strip())
        except json.JSONDecodeError:
            return self._heuristic_reflect(plan_steps, results)

    def _heuristic_reflect(self, plan_steps: list[dict], results: list[dict]) -> dict:
        failed = [s for s in plan_steps if s.get("status") == "failed"]
        completed = [s for s in plan_steps if s.get("status") == "completed"]
        total = len(plan_steps)

        if total > 0 and len(completed) >= total:
            return {"decision": ReflectionDecision.DONE, "reasoning": "All steps completed.", "message": ""}

        if failed:
            return {
                "decision": ReflectionDecision.RETRY,
                "reasoning": f"{len(failed)} step(s) failed. Retrying.",
                "message": "",
            }

        if results and "error" in str(results[-1].get("result", "")).lower():
            return {
                "decision": ReflectionDecision.RETRY,
                "reasoning": "Last step returned an error.",
                "message": "",
            }

        return {"decision": ReflectionDecision.CONTINUE, "reasoning": "Proceeding as planned.", "message": ""}
