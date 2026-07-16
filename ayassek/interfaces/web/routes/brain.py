from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel
from typing import Optional

from ayassek.utils.logging import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/api/brain")


class EntityCreateRequest(BaseModel):
    category: str
    name: str
    summary: str = ""


class EntityUpdateRequest(BaseModel):
    summary: str


class FactCreateRequest(BaseModel):
    text: str
    category: str = "general"
    tags: list[str] = []
    status: str = "active"
    source: str = "manual"
    importance: int = 50


class FactUpdateRequest(BaseModel):
    text: Optional[str] = None
    status: Optional[str] = None
    tags: Optional[list[str]] = None
    importance: Optional[int] = None


class SearchRequest(BaseModel):
    query: str
    category: Optional[str] = None
    top_k: int = 10


@router.get("/entities")
async def list_entities(category: Optional[str] = None, request: Request = None):
    try:
        memory = request.app.state.memory_manager
        entities = memory.sb_list_entities(category)
        return {"status": "ok", "data": entities}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/entities/{category}/{name}")
async def get_entity(category: str, name: str, request: Request):
    try:
        memory = request.app.state.memory_manager
        entity = memory.sb_get_entity(category, name)
        if entity is None:
            raise HTTPException(status_code=404, detail="Entity not found")
        return {"status": "ok", "data": entity}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/entities")
async def create_entity(req: EntityCreateRequest, request: Request):
    try:
        memory = request.app.state.memory_manager
        entity = memory.sb_create_entity(req.category, req.name, req.summary)
        return {"status": "ok", "data": entity}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/entities/{category}/{name}")
async def update_entity_summary(category: str, name: str, req: EntityUpdateRequest, request: Request):
    try:
        memory = request.app.state.memory_manager
        success = memory.sb_update_summary(category, name, req.summary)
        if not success:
            raise HTTPException(status_code=404, detail="Entity not found")
        return {"status": "ok"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/entities/{category}/{name}")
async def delete_entity(category: str, name: str, request: Request):
    try:
        memory = request.app.state.memory_manager
        success = memory.sb_delete_entity(category, name)
        if not success:
            raise HTTPException(status_code=404, detail="Entity not found")
        return {"status": "ok", "deleted": True}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/entities/{category}/{name}/facts")
async def add_fact(category: str, name: str, req: FactCreateRequest, request: Request):
    try:
        memory = request.app.state.memory_manager
        fact_data = req.model_dump()
        fact_data["id"] = __import__("uuid").uuid4().hex[:8]
        from datetime import datetime
        fact_data["timestamp"] = datetime.utcnow().isoformat() + "Z"
        success = memory.sb_add_fact(category, name, fact_data)
        if not success:
            raise HTTPException(status_code=500, detail="Failed to add fact")
        return {"status": "ok", "fact_id": fact_data["id"]}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/entities/{category}/{name}/facts/{fact_id}")
async def update_fact(category: str, name: str, fact_id: str, req: FactUpdateRequest, request: Request):
    try:
        memory = request.app.state.memory_manager
        kwargs = {k: v for k, v in req.model_dump().items() if v is not None}
        success = memory.sb_update_fact(category, name, fact_id, **kwargs)
        if not success:
            raise HTTPException(status_code=404, detail="Fact not found")
        return {"status": "ok"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/entities/{category}/{name}/facts/{fact_id}")
async def delete_fact(category: str, name: str, fact_id: str, request: Request):
    try:
        memory = request.app.state.memory_manager
        success = memory.sb_delete_fact(category, name, fact_id)
        if not success:
            raise HTTPException(status_code=404, detail="Fact not found")
        return {"status": "ok", "deleted": True}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


class PositionUpdateRequest(BaseModel):
    x: float
    y: float


@router.put("/entities/{category}/{name}/position")
async def update_entity_position(category: str, name: str, req: PositionUpdateRequest, request: Request):
    try:
        memory = request.app.state.memory_manager
        success = memory.second_brain.set_entity_position(category, name, req.x, req.y)
        if not success:
            raise HTTPException(status_code=404, detail="Entity not found")
        return {"status": "ok", "x": req.x, "y": req.y}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/search")
async def search_brain(req: SearchRequest, request: Request):
    try:
        memory = request.app.state.memory_manager
        results = memory.sb_search(req.query, category=req.category, top_k=req.top_k)
        return {"status": "ok", "data": results}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/index")
async def index_to_vectors(request: Request):
    try:
        memory = request.app.state.memory_manager
        count = memory.sb_index_to_vectors()
        return {"status": "ok", "indexed": count}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/stats")
async def brain_stats(request: Request):
    try:
        memory = request.app.state.memory_manager
        return {"status": "ok", "data": memory.second_brain.get_stats()}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/graph")
async def unified_graph(request: Request):
    try:
        memory = request.app.state.memory_manager
        entities = memory.sb_list_entities() or []
        neurons = memory.get_neurons() or []
        synapses = memory.get_synapses() or []

        nodes = []
        edges = []

        seen = set()
        for e in entities:
            eid = f"entity:{e['category']}:{e['name']}"
            seen.add(eid)
            nodes.append({
                "id": eid,
                "type": "entity",
                "title": e["name"],
                "category": e["category"],
                "summary": e.get("summary_preview", ""),
                "facts_count": e.get("facts_count", 0),
                "x": e.get("x"),
                "y": e.get("y"),
                "source": "second_brain",
            })
            facts = memory.sb_list_facts(e["category"], e["name"]) or []
            for f in facts:
                fid = f"fact:{eid}:{f['id']}"
                if fid not in seen:
                    seen.add(fid)
                    nodes.append({
                        "id": fid,
                        "type": "fact",
                        "title": f.get("text", "")[:80],
                        "category": f.get("category", "general"),
                        "status": f.get("status", "active"),
                        "x": None,
                        "y": None,
                        "source": "second_brain",
                    })
                edges.append({
                    "id": f"has_fact:{eid}:{f['id']}",
                    "source": eid,
                    "target": fid,
                    "strength": f.get("importance", 50) / 50.0,
                    "is_manual": True,
                    "label": "has_fact",
                })

        for n in neurons:
            nid = f"neuron:{n['id']}"
            if nid not in seen:
                seen.add(nid)
                nodes.append({
                    "id": nid,
                    "type": "neuron",
                    "title": n.get("title", ""),
                    "content": n.get("content", ""),
                    "x": n.get("x"),
                    "y": n.get("y"),
                    "source": "graph_db",
                })

        for s in synapses:
            edges.append({
                "id": f"synapse:{s['id']}",
                "source": f"neuron:{s['source_node_id']}",
                "target": f"neuron:{s['target_node_id']}",
                "strength": s.get("strength", 1.0),
                "is_manual": s.get("is_manual", False),
                "label": "synapse",
            })

        return {"status": "ok", "nodes": nodes, "edges": edges}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/reset")
async def reset_nrs(request: Request):
    try:
        memory = request.app.state.memory_manager
        result = memory.clear_neural_memory()
        logger.info("NRS reset complete: %s", result)
        return {"status": "ok", "message": "All NRS data wiped", "details": result}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))