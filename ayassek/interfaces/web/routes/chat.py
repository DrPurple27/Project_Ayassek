from __future__ import annotations

import asyncio
import json
import uuid
from typing import Any

from fastapi import APIRouter, Request
from pydantic import BaseModel

from ayassek.core.events import Event, EventType
from ayassek.utils.logging import get_logger

router = APIRouter(prefix="/chat", tags=["chat"])
_logger = get_logger("chat_routes")


class ChatRequest(BaseModel):
    message: str
    session_id: str = "default"
    images: list[str] | None = None


class ChatResponse(BaseModel):
    status: str
    session_id: str


def _make_error_callback(session_id: str, event_bus):
    async def _on_error(task: asyncio.Task):
        try:
            await task
        except Exception as e:
            _logger.exception("Chat task failed for session %s", session_id)
            await event_bus.emit(Event(
                type=EventType.BRAIN_ERROR,
                data={"error": str(e)},
                session_id=session_id,
            ))
    return _on_error


@router.post("", response_model=ChatResponse)
async def chat(req: ChatRequest, request: Request):
    brain = request.app.state.brain
    event_bus = request.app.state.event_bus

    task = asyncio.create_task(
        brain.process_message(
            content=req.message,
            session_id=req.session_id,
            images=req.images,
        )
    )
    task.add_done_callback(lambda t: asyncio.ensure_future(_make_error_callback(req.session_id, event_bus)(t)))

    return ChatResponse(status="processing", session_id=req.session_id)


@router.post("/send")
async def chat_send(req: ChatRequest, request: Request):
    brain = request.app.state.brain
    event_bus = request.app.state.event_bus

    task = asyncio.create_task(
        brain.process_message(
            content=req.message,
            session_id=req.session_id,
            images=req.images,
        )
    )
    task.add_done_callback(lambda t: asyncio.ensure_future(_make_error_callback(req.session_id, event_bus)(t)))

    return {"status": "processing", "session_id": req.session_id}


@router.post("/session/clear")
async def clear_session(request: Request, session_id: str = "default"):
    memory = request.app.state.memory_manager
    memory.clear_session(session_id=session_id)
    event_bus = request.app.state.event_bus
    await event_bus.emit(Event(
        type=EventType.MEMORY_UPDATED,
        data={"action": "clear", "session_id": session_id},
        session_id=session_id,
    ))
    return {"status": "cleared", "session_id": session_id}


@router.get("/session/context")
async def get_context(request: Request, session_id: str = "default", limit: int = 20):
    memory = request.app.state.memory_manager
    context = memory.get_context(limit=limit, session_id=session_id)
    return {"context": context, "session_id": session_id}


@router.get("/sessions")
async def list_sessions(request: Request):
    memory = request.app.state.memory_manager
    sessions = memory.get_sessions()
    return {"sessions": sessions}


@router.get("/sessions/{session_id}/messages")
async def get_session_messages(request: Request, session_id: str, limit: int = 50):
    memory = request.app.state.memory_manager
    messages = memory.get_context(limit=limit, session_id=session_id)
    return {"session_id": session_id, "messages": messages}


@router.post("/sessions")
async def create_session(request: Request):
    body = await request.body()
    try:
        data = json.loads(body) if body else {}
    except Exception:
        data = {}
    name = data.get("name", "New Session")
    memory = request.app.state.memory_manager
    sid = uuid.uuid4().hex[:12]
    memory.create_session(sid, name)
    event_bus = request.app.state.event_bus
    await event_bus.emit(Event(
        type=EventType.MEMORY_UPDATED,
        data={"action": "session_created", "session_id": sid, "name": name},
        session_id=sid,
    ))
    return {"session_id": sid, "name": name}

@router.delete("/sessions/{session_id}")
async def delete_session(request: Request, session_id: str):
    memory = request.app.state.memory_manager
    memory.delete_session(session_id)
    return {"status": "deleted", "session_id": session_id}


@router.patch("/sessions/{session_id}")
async def rename_session(request: Request, session_id: str):
    body = await request.json()
    name = body.get("name")
    if not name:
        return {"status": "error", "error": "name required"}
    memory = request.app.state.memory_manager
    gdb = memory._get_graph_db()
    gdb.update_session_name(session_id, name)
    return {"status": "renamed", "session_id": session_id, "name": name}