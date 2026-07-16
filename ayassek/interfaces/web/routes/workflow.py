from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from ayassek.reasoning.workflow import WorkflowEngine

router = APIRouter(prefix="/api/workflows")


class CreateWorkflowRequest(BaseModel):
    name: str
    description: str = ""
    trigger: str = "manual"
    steps: list[dict] = []


@router.get("")
async def list_workflows(request: Request):
    engine: WorkflowEngine = request.app.state.workflow_engine
    return {"workflows": engine.list_workflows()}


@router.post("")
async def create_workflow(req: CreateWorkflowRequest, request: Request):
    engine: WorkflowEngine = request.app.state.workflow_engine
    wf = engine.create_workflow(req.name, req.description, req.steps, trigger=req.trigger)
    return {"status": "created", "name": wf.name, "trigger": wf.trigger}


@router.get("/{name}")
async def get_workflow(name: str, request: Request):
    engine: WorkflowEngine = request.app.state.workflow_engine
    wf = engine.get_workflow(name)
    if not wf:
        raise HTTPException(status_code=404, detail="Workflow not found")
    return {
        "name": wf.name,
        "description": wf.description,
        "trigger": wf.trigger,
        "steps": [
            {
                "id": s.id,
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


@router.post("/{name}/run")
async def run_workflow(name: str, request: Request):
    engine: WorkflowEngine = request.app.state.workflow_engine
    try:
        run = await engine.run_workflow(name)
        return {
            "status": "started",
            "run_id": run.id,
            "workflow": name,
            "run_status": run.status,
        }
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/runs/{run_id}")
async def get_run(run_id: str, request: Request):
    engine: WorkflowEngine = request.app.state.workflow_engine
    run = engine.get_run(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    return {
        "id": run.id,
        "workflow": run.workflow_name,
        "status": run.status,
        "current_step": run.current_step,
        "step_results": run.step_results,
        "error": run.error,
    }


@router.post("/runs/{run_id}/resume")
async def resume_run(run_id: str, request: Request):
    engine: WorkflowEngine = request.app.state.workflow_engine
    success = engine.resume_run(run_id)
    if not success:
        raise HTTPException(status_code=400, detail="Run not found or not paused")
    return {"status": "resumed", "run_id": run_id}


@router.post("/scheduler/start")
async def start_scheduler(request: Request):
    engine: WorkflowEngine = request.app.state.workflow_engine
    engine.start_scheduler()
    return {"status": "scheduler_started"}


@router.post("/scheduler/stop")
async def stop_scheduler(request: Request):
    engine: WorkflowEngine = request.app.state.workflow_engine
    engine.stop_scheduler()
    return {"status": "scheduler_stopped"}


@router.get("/scheduler/status")
async def scheduler_status(request: Request):
    engine: WorkflowEngine = request.app.state.workflow_engine
    return {
        "running": engine._scheduler is not None and getattr(engine._scheduler, "running", False),
        "jobs": list(engine._scheduler_jobs.keys()),
    }


@router.get("/webhooks")
async def list_webhooks(request: Request):
    engine: WorkflowEngine = request.app.state.workflow_engine
    return {"webhooks": engine.get_webhook_workflows()}


class WebhookSecretRequest(BaseModel):
    secret: str = ""


@router.post("/{name}/webhook/secret")
async def set_webhook_secret(name: str, req: WebhookSecretRequest, request: Request):
    engine: WorkflowEngine = request.app.state.workflow_engine
    wf = engine.get_workflow(name)
    if not wf:
        raise HTTPException(status_code=404, detail="Workflow not found")
    engine.register_webhook_secret(name, req.secret)
    return {"status": "secret_set", "workflow": name}


@router.post("/webhook/{webhook_path:path}")
async def trigger_webhook(webhook_path: str, request: Request):
    engine: WorkflowEngine = request.app.state.workflow_engine
    body = await request.body()
    sig = request.headers.get("X-Hub-Signature-256", "")
    payload = {}
    try:
        if body:
            payload = await request.json()
    except Exception:
        pass

    wf_name = None
    for wh in engine.get_webhook_workflows():
        if wh["webhook_path"] == webhook_path:
            wf_name = wh["name"]
            break

    if not wf_name:
        raise HTTPException(status_code=404, detail=f"No workflow with webhook path: {webhook_path}")

    if not engine.verify_webhook(wf_name, sig, body):
        raise HTTPException(status_code=403, detail="Invalid webhook signature")

    run = await engine.trigger_webhook(webhook_path, payload=payload)
    return {"status": "triggered", "webhook_path": webhook_path, "workflow": wf_name, "run_id": run.id if run else None}
