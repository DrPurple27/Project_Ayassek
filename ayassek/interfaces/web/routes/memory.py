from __future__ import annotations

import json

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from ayassek.core.events import Event, EventType

router = APIRouter(prefix="/memory", tags=["memory"])


class MemoryStoreRequest(BaseModel):
    key: str
    value: str


class MemoryAddRequest(BaseModel):
    role: str
    content: str


# ─── Legacy Short-Term Endpoints ──────

@router.get("")
async def get_memory(request: Request, limit: int = 50):
    memory = request.app.state.memory_manager
    context = memory.get_context(limit=limit)
    stored = memory.get_all_stored() if hasattr(memory, "get_all_stored") else {}
    return {"messages": context, "stored": stored, "message_count": len(context)}


@router.post("/store")
async def store_memory(req: MemoryStoreRequest, request: Request):
    memory = request.app.state.memory_manager
    memory.store(req.key, req.value)
    return {"status": "stored", "key": req.key}


@router.get("/recall/{key}")
async def recall_memory(key: str, request: Request):
    memory = request.app.state.memory_manager
    value = memory.recall(key)
    return {"key": key, "value": value}


@router.post("/add")
async def add_message(req: MemoryAddRequest, request: Request):
    memory = request.app.state.memory_manager
    memory.add_message(req.role, req.content)
    return {"status": "added", "role": req.role}


@router.post("/clear")
async def clear_memory(request: Request):
    memory = request.app.state.memory_manager
    memory.clear_session()
    return {"status": "cleared"}


@router.get("/status")
async def memory_status(request: Request):
    memory = request.app.state.memory_manager
    return memory.get_status()


# ─── Neural Graph Endpoints ────────────

class NodeCreateRequest(BaseModel):
    title: str
    content: str = ""
    x: float | None = None
    y: float | None = None


class NodeUpdateRequest(BaseModel):
    title: str | None = None
    content: str | None = None
    x: float | None = None
    y: float | None = None


class EdgeCreateRequest(BaseModel):
    source_id: str
    target_id: str
    strength: float = 1.0


@router.post("/nodes")
async def create_node(req: NodeCreateRequest, request: Request):
    memory = request.app.state.memory_manager
    node = memory.create_neuron(
        title=req.title,
        content=req.content,
        x=req.x,
        y=req.y,
    )
    return node


@router.get("/nodes")
async def get_nodes(request: Request):
    memory = request.app.state.memory_manager
    return {"nodes": memory.get_neurons()}


@router.put("/nodes/{node_id}")
async def update_node(node_id: str, req: NodeUpdateRequest, request: Request):
    memory = request.app.state.memory_manager
    fields = {}
    if req.title is not None:
        fields["title"] = req.title
    if req.content is not None:
        fields["content"] = req.content
    if req.x is not None:
        fields["x"] = req.x
    if req.y is not None:
        fields["y"] = req.y
    node = memory.update_neuron(node_id, **fields)
    if not node:
        raise HTTPException(status_code=404, detail="Node not found")
    return node


@router.delete("/nodes/{node_id}")
async def delete_node(node_id: str, request: Request):
    memory = request.app.state.memory_manager
    success = memory.delete_neuron(node_id)
    if not success:
        raise HTTPException(status_code=404, detail="Node not found")
    return {"status": "deleted", "node_id": node_id}


@router.get("/edges")
async def get_edges(request: Request):
    memory = request.app.state.memory_manager
    return {"edges": memory.get_synapses()}


@router.post("/edges")
async def create_edge(req: EdgeCreateRequest, request: Request):
    memory = request.app.state.memory_manager
    edge = memory.create_synapse(
        source_id=req.source_id,
        target_id=req.target_id,
        strength=req.strength,
        is_manual=True,
    )
    return edge


@router.delete("/edges/{edge_id}")
async def delete_edge(edge_id: str, request: Request):
    memory = request.app.state.memory_manager
    success = memory.delete_synapse(edge_id)
    if not success:
        raise HTTPException(status_code=404, detail="Edge not found")
    return {"status": "deleted", "edge_id": edge_id}