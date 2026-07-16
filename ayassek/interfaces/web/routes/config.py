from __future__ import annotations

from fastapi import APIRouter, Request
from pydantic import BaseModel

from ayassek.config.settings import settings as app_settings
from ayassek.core.events import Event, EventType

router = APIRouter(prefix="/config", tags=["config"])


class ConfigUpdateRequest(BaseModel):
    host: str | None = None
    port: int | None = None
    debug: bool | None = None
    default_provider: str | None = None
    default_model: str | None = None


@router.get("")
async def get_config(request: Request):
    return {
        "server": {
            "host": app_settings.server.host,
            "port": app_settings.server.port,
            "debug": app_settings.debug,
        },
        "defaults": {
            "provider": app_settings.defaults.provider,
            "model": app_settings.defaults.model,
        },
        "memory": {
            "short_term_max_messages": app_settings.memory.short_term.max_messages,
        },
    }


@router.put("")
async def update_config(req: ConfigUpdateRequest, request: Request):
    changes = {}
    provider_changed = False
    if req.debug is not None:
        app_settings.debug = req.debug
        changes["debug"] = req.debug
    if req.default_provider:
        app_settings.defaults.provider = req.default_provider
        changes["default_provider"] = req.default_provider
        provider_changed = True
    if req.default_model:
        app_settings.defaults.model = req.default_model
        changes["default_model"] = req.default_model
        provider_changed = True

    if provider_changed:
        pm = request.app.state.provider_manager
        ok = pm.set_active_provider(app_settings.defaults.provider)
        if ok:
            pm.set_active_model(app_settings.defaults.model)
        await request.app.state.event_bus.emit(Event(
            type=EventType.CONFIG_CHANGED,
            data={"provider": app_settings.defaults.provider, "model": app_settings.defaults.model},
        ))

    return {"status": "updated", "changes": changes}