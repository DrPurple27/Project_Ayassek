from fastapi import APIRouter, HTTPException, Request, UploadFile, File, Form
from pydantic import BaseModel
from typing import Optional
from pathlib import Path

from ayassek.utils.logging import get_logger
from ayassek.memory.ingest import queue_ingestion, get_ingestion_task

logger = get_logger(__name__)

router = APIRouter(prefix="/api/rag")


class IngestTextRequest(BaseModel):
    text: str
    source: str
    category: str = "general"
    tags: list[str] = []
    metadata: dict = {}


class QueryRequest(BaseModel):
    query: str
    top_k: int = 10
    rerank: bool = True
    category: Optional[str] = None


@router.post("/ingest")
async def ingest_text(req: IngestTextRequest, request: Request):
    try:
        memory = request.app.state.memory_manager
        result = memory.rag_ingest(
            text=req.text,
            source=req.source,
            category=req.category,
            tags=req.tags,
            metadata=req.metadata,
        )
        return {
            "status": "ok",
            "chunks_created": result.chunks_created,
            "vectors_stored": result.vectors_stored,
            "duration_ms": result.duration_ms,
            "errors": result.errors,
        }
    except Exception as e:
        logger.error(f"RAG ingest failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/ingest/file")
async def ingest_file(
    request: Request,
    file: UploadFile = File(...),
    category: str = Form("upload"),
    tags: str = Form(""),
    metadata: str = Form("{}"),
):
    """Upload a file and queue for async ingestion."""
    import json
    tmp_path = None
    try:
        import tempfile
        
        # Save uploaded file to temp location
        suffix = Path(file.filename).suffix if file.filename else ""
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            content = await file.read()
            tmp.write(content)
            tmp_path = tmp.name
        
        # Parse tags and metadata
        tag_list = [t.strip() for t in tags.split(",") if t.strip()] if tags else []
        meta = json.loads(metadata) if metadata else {}
        
        # Queue for async processing
        task_id = queue_ingestion(
            file_path=tmp_path,
            category=category,
            tags=tag_list,
            metadata=meta,
        )
        
        return {"status": "ok", "task_id": task_id, "message": "File queued for ingestion"}
    except Exception as e:
        logger.error(f"File ingest failed: {e}")
        # Clean up temp file on error
        if tmp_path:
            try:
                import os
                os.unlink(tmp_path)
            except Exception:
                pass
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/ingest/status/{task_id}")
async def ingest_status(task_id: str):
    """Get status of an ingestion task."""
    task = get_ingestion_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    return {
        "status": "ok",
        "data": {
            "task_id": task.task_id,
            "status": task.status,
            "progress": task.progress,
            "current_stage": task.current_stage,
            "current_page": task.current_page,
            "total_pages": task.total_pages,
            "result": task.result,
            "error": task.error,
            "created_at": task.created_at,
            "updated_at": task.updated_at,
        }
    }


@router.post("/query")
async def query_rag(req: QueryRequest, request: Request):
    try:
        memory = request.app.state.memory_manager
        result = memory.rag_query(
            query=req.query,
            top_k=req.top_k,
            rerank=req.rerank,
            category=req.category,
        )
        return {
            "status": "ok",
            "context": result["context"],
            "chunks": result["chunks"],
            "reranked": result["reranked"],
            "metadata": result["metadata"],
        }
    except Exception as e:
        logger.error(f"RAG query failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/status")
async def rag_status(request: Request):
    try:
        memory = request.app.state.memory_manager
        return {"status": "ok", "data": memory.rag_engine.get_status()}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/category/{category}")
async def delete_category(category: str, request: Request):
    """Soft delete all vectors for a category."""
    try:
        memory = request.app.state.memory_manager
        deleted = memory.rag_engine.delete_category(category)
        return {"status": "ok", "deleted": deleted}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/ingest/repostoinpire")
async def ingest_repos(request: Request):
    try:
        from ayassek.memory.ingest import get_ingestion_service
        svc = get_ingestion_service()
        result = svc.ingest_repostoinpire()
        return {"status": "ok", "data": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/index/create")
async def create_index(request: Request):
    try:
        memory = request.app.state.memory_manager
        memory.rag_engine.create_index()
        return {"status": "ok"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/reindex")
async def full_reindex(request: Request):
    try:
        from ayassek.memory.ingest import get_ingestion_service
        svc = get_ingestion_service()
        result = svc.full_reindex()
        return {"status": "ok", "data": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/source/{source:path}")
async def delete_source(source: str, request: Request):
    try:
        memory = request.app.state.memory_manager
        deleted = memory.rag_engine.delete_by_source(source)
        return {"status": "ok", "deleted": deleted}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/wipe")
async def wipe_rag(request: Request):
    try:
        import lancedb
        from ayassek.memory.vector_db import get_lancedb_service

        lancedb_svc = get_lancedb_service()
        db = lancedb_svc._get_db()
        table_name = "ayassek_rag"

        tables = db.table_names() if hasattr(db, 'table_names') else db.list_tables()
        if table_name in tables:
            db.drop_table(table_name)

        lancedb_svc._tables.pop(table_name, None)
        lancedb_svc._get_table(table_name)

        logger.info("RAG wiped — table dropped and recreated empty")
        return {"status": "ok", "message": "All RAG data wiped", "table": table_name}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))