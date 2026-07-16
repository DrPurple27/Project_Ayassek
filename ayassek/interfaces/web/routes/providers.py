from __future__ import annotations

from fastapi import APIRouter, Request
from pydantic import BaseModel

router = APIRouter(prefix="/providers", tags=["providers"])


class SelectRequest(BaseModel):
    provider_id: str
    model: str


@router.get("")
async def list_providers(request: Request):
    pm = request.app.state.provider_manager
    providers = pm.get_provider_info()
    status = pm.get_status()
    result = []
    for p in providers:
        pid = p["id"]
        provider_status = status.get(pid, {})
        models = pm.get_models(pid)
        p["status"] = provider_status
        p["models"] = [{"id": m.id, "name": m.name, "streaming": m.supports_streaming, "tools": m.supports_tools}
                        for m in models]
        p["active"] = pid == pm._active_provider_id
        # Add error info if disconnected
        if not provider_status.get("connected", False):
            p["error"] = provider_status.get("error", "Provider not connected")
        result.append(p)
    result.sort(key=lambda x: 0 if x["active"] else 1)
    return {"providers": result, "active_provider": pm._active_provider_id, "active_model": pm.get_active_model()}


@router.get("/models")
async def list_models(request: Request, provider_id: str | None = None):
    pm = request.app.state.provider_manager
    await pm.refresh_models(provider_id)
    pid = provider_id or pm._active_provider_id
    models = pm.get_models(pid)
    return {
        "provider_id": pid,
        "models": [{"id": m.id, "name": m.name, "streaming": m.supports_streaming, "tools": m.supports_tools, "vision": m.supports_vision}
                    for m in models],
    }


@router.post("/select")
async def select_provider(req: SelectRequest, request: Request):
    pm = request.app.state.provider_manager
    success = pm.set_active_provider(req.provider_id)
    if success:
        pm.set_active_model(req.model)
        await pm.refresh_models(req.provider_id)
        from ayassek.core.events import Event, EventType
        await request.app.state.event_bus.emit(Event(
            type=EventType.PROVIDER_CHANGED,
            data={"provider": req.provider_id, "model": req.model},
        ))
        return {"status": "ok", "provider": req.provider_id, "model": req.model}
    return {"status": "error", "message": f"Provider '{req.provider_id}' not found"}


@router.get("/health/{provider_id}")
async def health_check(provider_id: str, request: Request):
    pm = request.app.state.provider_manager
    healthy = await pm.health_check(provider_id)
    return {"provider_id": provider_id, "healthy": healthy}


@router.get("/status")
async def get_status(request: Request):
    pm = request.app.state.provider_manager
    return {"providers": pm.get_status(), "active_provider": pm._active_provider_id, "active_model": pm.get_active_model()}