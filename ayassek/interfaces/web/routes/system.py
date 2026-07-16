from __future__ import annotations

import os
import platform
import time
from typing import Any

from fastapi import APIRouter, Request

router = APIRouter(prefix="/system", tags=["system"])

_start_time = time.time()


@router.get("/health")
async def health():
    return {"status": "ok", "timestamp": time.time()}


@router.get("/models/status")
async def models_status():
    embedding_loaded = False
    reranker_loaded = False
    try:
        from ayassek.memory.embeddings import get_embedding_service
        svc = get_embedding_service()
        embedding_loaded = svc._model is not None
    except Exception:
        pass
    try:
        from ayassek.memory.reranker import get_reranker_service
        svc = get_reranker_service()
        reranker_loaded = svc._model is not None
    except Exception:
        pass
    return {
        "embedding_loaded": embedding_loaded,
        "embedding_model": svc.model_name if embedding_loaded else None,
        "reranker_loaded": reranker_loaded,
        "reranker_model": svc.model_name if reranker_loaded else None,
    }


@router.get("/status")
async def get_system_status(request: Request):
    try:
        import psutil
        cpu = psutil.cpu_percent(interval=0.1)
        mem = psutil.virtual_memory()
        disk = psutil.disk_usage("/")
        proc = psutil.Process()
        process_mem = proc.memory_info().rss / (1024 * 1024)
    except ImportError:
        cpu = 0
        mem = type("mem", (), {"percent": 0, "used": 0, "total": 0})()
        disk = type("disk", (), {"used": 0, "total": 0})()
        process_mem = 0

    pm = request.app.state.provider_manager
    brain = request.app.state.brain
    memory = request.app.state.memory_manager

    return {
        "uptime": time.time() - _start_time,
        "system": {
            "os": platform.system(),
            "release": platform.release(),
            "python": platform.python_version(),
            "hostname": platform.node(),
            "cpu_count": os.cpu_count(),
        },
        "resources": {
            "cpu_percent": cpu,
            "memory_percent": mem.percent,
            "memory_used_gb": round(mem.used / (1024**3), 2),
            "memory_total_gb": round(mem.total / (1024**3), 2),
            "disk_used_gb": round(disk.used / (1024**3), 2),
            "disk_total_gb": round(disk.total / (1024**3), 2),
            "process_memory_mb": round(process_mem, 1),
        },
        "ayassek": {
            "active_provider": pm._active_provider_id,
            "active_model": pm.get_active_model(),
            "provider_status": pm.get_status(),
            "memory_messages": len(memory.get_context()),
        },
    }


@router.get("/tools")
async def list_tools(request: Request):
    registry = request.app.state.tool_registry
    return {"tools": registry.list_tools()}


@router.get("/ready")
async def system_ready(request: Request):
    pm = request.app.state.provider_manager
    memory = request.app.state.memory_manager
    steps = []
    ready = True

    active = pm.get_active_provider()
    provider_status = pm.get_status()
    provider_connected = False
    if active:
        pid = active.provider_id
        ps = provider_status.get(pid, {})
        provider_connected = ps.get("connected", False)
    steps.append({
        "name": "provider",
        "label": "Connecting to providers",
        "status": "ok" if provider_connected else "pending",
        "detail": f"Provider: {active.provider_id if active else 'none'}" if provider_connected else "No active provider connected",
    })
    if not provider_connected:
        ready = False

    active_model = pm.get_active_model()
    model_available = active_model and any(
        m.id == active_model for m in pm.get_models()
    )
    steps.append({
        "name": "model",
        "label": "Checking active model",
        "status": "ok" if model_available else "pending",
        "detail": f"Model: {active_model}" if model_available else f"Model '{active_model}' not available",
    })
    if not model_available:
        ready = False

    try:
        nrs = request.app.state.brain._nrs if hasattr(request.app.state.brain, '_nrs') else None
        if nrs and hasattr(nrs, 'check_nrs_model_available'):
            nrs_check = await nrs.check_nrs_model_available()
        else:
            nrs_check = {"available": False, "model": "qwen2.5:1.5b", "pull_command": "ollama pull qwen2.5:1.5b"}
    except Exception:
        nrs_check = {"available": False, "model": "qwen2.5:1.5b", "pull_command": "ollama pull qwen2.5:1.5b"}
    steps.append({
        "name": "nrs_model",
        "label": "Verifying NRS model",
        "status": "ok" if nrs_check["available"] else "warning",
        "detail": f"qwen2.5:1.5b ready" if nrs_check["available"] else f"Run: {nrs_check['pull_command']}",
    })

    try:
        neural_count = memory.get_neuron_count()
        neural_ok = neural_count >= 0
    except Exception:
        neural_ok = True
    steps.append({
        "name": "neural_memory",
        "label": "Loading neural memory",
        "status": "ok" if neural_ok else "pending",
        "detail": f"Found {memory.get_neuron_count()} neurons" if neural_ok else "Unavailable",
    })

    try:
        rag_status = memory.rag_engine.get_status()
        rag_ok = rag_status["vector_count"] > 0
    except Exception:
        rag_status = {}
        rag_ok = True
    steps.append({
        "name": "rag",
        "label": "Checking RAG pipeline",
        "status": "ok" if rag_ok else "pending",
        "detail": f"{rag_status.get('vector_count', 0)} vectors indexed" if rag_ok else "No vectors yet (ingest documents)",
    })

    try:
        sb_stats = memory.second_brain.get_stats()
        sb_ok = sb_stats["total_entities"] > 0
    except Exception:
        sb_stats = {}
        sb_ok = True
    steps.append({
        "name": "second_brain",
        "label": "Checking Second Brain",
        "status": "ok" if sb_ok else "pending",
        "detail": f"{sb_stats.get('total_entities', 0)} entities, {sb_stats.get('total_active_facts', 0)} active facts" if sb_ok else "No entities yet",
    })

    try:
        sessions = memory.get_sessions()
        session_ok = len(sessions) > 0
    except Exception:
        session_ok = False
    steps.append({
        "name": "sessions",
        "label": "Loading sessions",
        "status": "ok" if session_ok else "pending",
        "detail": f"{len(sessions)} active sessions" if session_ok else "No sessions",
    })

    steps.append({
        "name": "done",
        "label": "Ready",
        "status": "ok" if ready else "warning",
        "detail": "Ayassek is ready" if ready else "Some components unavailable",
    })

    return {"ready": ready, "steps": steps}