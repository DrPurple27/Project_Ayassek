from __future__ import annotations

import hashlib
import hmac
import re
import uuid
import yaml
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

from ayassek.utils.logging import get_logger

logger = get_logger("workflow")

CRON_PATTERN = re.compile(r"^cron:(.+)$")
WEBHOOK_PATTERN = re.compile(r"^webhook:(.+)$")


@dataclass
class WorkflowStep:
    id: str
    action: str
    description: str = ""
    tool: str | None = None
    args: dict[str, Any] = field(default_factory=dict)
    dependencies: list[str] = field(default_factory=list)
    checkpoint: bool = False


@dataclass
class Workflow:
    name: str
    description: str = ""
    trigger: str = "manual"
    steps: list[WorkflowStep] = field(default_factory=list)


@dataclass
class WorkflowRun:
    id: str
    workflow_name: str
    status: str = "pending"
    current_step: int = 0
    step_results: list[dict] = field(default_factory=list)
    error: str | None = None
    started_at: str = ""
    updated_at: str = ""


def _parse_cron_trigger(trigger: str) -> str | None:
    """Extract cron expression from trigger string like 'cron:*/30 * * * *'."""
    m = CRON_PATTERN.match(trigger)
    if m:
        return m.group(1).strip()
    return None


class WorkflowEngine:
    def __init__(self, tool_executor=None):
        self._executor = tool_executor
        self._runs: dict[str, WorkflowRun] = {}
        self._workflows: dict[str, Workflow] = {}
        self._webhook_secrets: dict[str, str] = {}
        self._workflows_dir = Path("data/workflows")
        self._workflows_dir.mkdir(parents=True, exist_ok=True)
        self._scheduler = None
        self._scheduler_jobs: dict[str, Any] = {}
        self._on_run_complete: Callable | None = None
        self._load_workflows()

    def set_on_run_complete(self, callback: Callable):
        self._on_run_complete = callback

    def _load_workflows(self):
        for f in self._workflows_dir.glob("*.yaml"):
            try:
                with open(f) as fh:
                    data = yaml.safe_load(fh)
                if data:
                    wf = self._parse_workflow(data)
                    self._workflows[wf.name] = wf
                    logger.info("Loaded workflow: %s (trigger=%s)", wf.name, wf.trigger)
            except Exception as e:
                logger.warning("Failed to load workflow %s: %s", f.name, e)

    def _parse_workflow(self, data: dict) -> Workflow:
        steps = []
        for i, sd in enumerate(data.get("steps", [])):
            steps.append(WorkflowStep(
                id=f"step_{i}",
                action=sd.get("action", "step"),
                description=sd.get("description", ""),
                tool=sd.get("tool"),
                args=sd.get("args", {}),
                dependencies=sd.get("dependencies", []),
                checkpoint=sd.get("checkpoint", False),
            ))
        return Workflow(
            name=data.get("name", "unnamed"),
            description=data.get("description", ""),
            trigger=data.get("trigger", "manual"),
            steps=steps,
        )

    def list_workflows(self) -> list[dict]:
        return [
            {"name": w.name, "description": w.description, "trigger": w.trigger, "steps": len(w.steps)}
            for w in self._workflows.values()
        ]

    def get_workflow(self, name: str) -> Workflow | None:
        return self._workflows.get(name)

    def create_workflow(self, name: str, description: str, steps: list[dict], trigger: str = "manual") -> Workflow:
        parsed_steps = []
        for i, sd in enumerate(steps):
            parsed_steps.append(WorkflowStep(
                id=sd.get("id", f"step_{i}"),
                action=sd.get("action", "step"),
                description=sd.get("description", ""),
                tool=sd.get("tool"),
                args=sd.get("args", {}),
                dependencies=sd.get("dependencies", []),
                checkpoint=sd.get("checkpoint", False),
            ))
        wf = Workflow(name=name, description=description, trigger=trigger, steps=parsed_steps)
        self._workflows[name] = wf
        self._save_workflow(wf)
        if CRON_PATTERN.match(trigger):
            self._schedule_workflow(wf)
        return wf

    def _save_workflow(self, wf: Workflow):
        data = {
            "name": wf.name,
            "description": wf.description,
            "trigger": wf.trigger,
            "steps": [
                {
                    "action": s.action,
                    "description": s.description,
                    "tool": s.tool,
                    "args": s.args,
                    "dependencies": s.dependencies,
                    "checkpoint": s.checkpoint,
                }
                for s in wf.steps
            ],
        }
        path = self._workflows_dir / f"{wf.name}.yaml"
        with open(path, "w") as f:
            yaml.dump(data, f, default_flow_style=False)

    def start_scheduler(self):
        if self._scheduler is not None:
            return
        try:
            from apscheduler.schedulers.asyncio import AsyncIOScheduler
            self._scheduler = AsyncIOScheduler()
            for wf in self._workflows.values():
                self._schedule_workflow(wf)
            self._scheduler.start()
            logger.info("Workflow scheduler started")
        except Exception as e:
            logger.warning("Failed to start workflow scheduler: %s", e)

    def stop_scheduler(self):
        if self._scheduler is None:
            return
        try:
            self._scheduler.shutdown(wait=False)
            self._scheduler = None
            self._scheduler_jobs.clear()
            logger.info("Workflow scheduler stopped")
        except Exception as e:
            logger.warning("Failed to stop scheduler: %s", e)

    def _schedule_workflow(self, wf: Workflow):
        if self._scheduler is None:
            return
        cron_expr = _parse_cron_trigger(wf.trigger)
        if not cron_expr:
            return

        try:
            parts = cron_expr.split()
            if len(parts) != 5:
                logger.warning("Invalid cron expression for workflow '%s': %s", wf.name, cron_expr)
                return

            job = self._scheduler.add_job(
                self._run_workflow_async,
                "cron",
                minute=parts[0],
                hour=parts[1],
                day=parts[2],
                month=parts[3],
                day_of_week=parts[4],
                args=[wf.name],
                id=f"workflow_{wf.name}",
                replace_existing=True,
                misfire_grace_time=60,
            )
            self._scheduler_jobs[wf.name] = job
            logger.info("Scheduled workflow '%s' with cron: %s", wf.name, cron_expr)
        except Exception as e:
            logger.warning("Failed to schedule workflow '%s': %s", wf.name, e)

    def _run_workflow_async(self, name: str):
        """Run workflow from scheduler - creates an asyncio task."""
        try:
            import asyncio
            loop = asyncio.get_event_loop()
            if loop.is_running():
                asyncio.ensure_future(self._run_and_notify(name))
            else:
                loop.run_until_complete(self._run_and_notify(name))
        except Exception as e:
            logger.error("Scheduled workflow run failed: %s", e)

    async def _run_and_notify(self, name: str):
        try:
            run = await self.run_workflow(name)
            logger.info("Scheduled workflow '%s' completed: status=%s", name, run.status)
            if self._on_run_complete:
                await self._on_run_complete(name, run)
        except Exception as e:
            logger.error("Scheduled workflow '%s' failed: %s", name, e)

    async def run_workflow(self, name: str, context: dict | None = None) -> WorkflowRun:
        wf = self._workflows.get(name)
        if not wf:
            raise ValueError(f"Workflow '{name}' not found")

        from datetime import datetime
        run = WorkflowRun(
            id=uuid.uuid4().hex[:12],
            workflow_name=name,
            status="running",
            started_at=datetime.utcnow().isoformat(),
            updated_at=datetime.utcnow().isoformat(),
        )
        self._runs[run.id] = run

        for i, step in enumerate(wf.steps):
            run.current_step = i
            step_result = {"step_id": step.id, "action": step.action, "status": "running", "result": "", "error": None}

            try:
                if step.checkpoint:
                    run.status = "paused"
                    run.updated_at = datetime.utcnow().isoformat()
                    step_result["status"] = "paused"
                    run.step_results.append(step_result)
                    return run

                if step.tool and self._executor:
                    result = await self._executor.execute_tool(step.tool, step.args)
                    step_result["result"] = result
                    step_result["status"] = "completed"
                else:
                    step_result["result"] = f"Completed: {step.description}"
                    step_result["status"] = "completed"

            except Exception as e:
                step_result["status"] = "failed"
                step_result["error"] = str(e)
                run.status = "failed"
                run.error = str(e)
                run.step_results.append(step_result)
                run.updated_at = datetime.utcnow().isoformat()
                return run

            run.step_results.append(step_result)
            run.updated_at = datetime.utcnow().isoformat()

        run.status = "completed"
        run.updated_at = datetime.utcnow().isoformat()
        return run

    def get_run(self, run_id: str) -> WorkflowRun | None:
        return self._runs.get(run_id)

    def resume_run(self, run_id: str) -> bool:
        run = self._runs.get(run_id)
        if not run or run.status != "paused":
            return False
        run.status = "running"
        return True

    def delete_run(self, run_id: str):
        self._runs.pop(run_id, None)

    def get_webhook_workflows(self) -> list[dict]:
        result = []
        for wf in self._workflows.values():
            wh_match = WEBHOOK_PATTERN.match(wf.trigger)
            if wh_match:
                result.append({
                    "name": wf.name,
                    "webhook_path": wh_match.group(1),
                    "has_secret": wf.name in self._webhook_secrets,
                })
        return result

    def register_webhook_secret(self, workflow_name: str, secret: str):
        self._webhook_secrets[workflow_name] = secret

    def verify_webhook(self, workflow_name: str, signature: str, payload: bytes) -> bool:
        secret = self._webhook_secrets.get(workflow_name)
        if not secret:
            return True
        expected = hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()
        return hmac.compare_digest(f"sha256={expected}", signature)

    async def trigger_webhook(self, webhook_path: str, payload: dict | None = None) -> WorkflowRun | None:
        for wf in self._workflows.values():
            wh_match = WEBHOOK_PATTERN.match(wf.trigger)
            if wh_match and wh_match.group(1) == webhook_path:
                try:
                    return await self.run_workflow(wf.name, context=payload)
                except Exception as e:
                    logger.error("Webhook trigger failed for workflow '%s': %s", wf.name, e)
        return None
