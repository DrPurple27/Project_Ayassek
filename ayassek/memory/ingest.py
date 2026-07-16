import os
import glob
import asyncio
import uuid
import tempfile
import shutil
import base64
import httpx
from pathlib import Path
from typing import Optional
from dataclasses import dataclass, field
from datetime import datetime

from ayassek.config.settings import settings
from ayassek.memory.rag import get_rag_engine
from ayassek.memory.second_brain import get_second_brain
from ayassek.core.bus import get_event_bus
from ayassek.core.events import Event, EventType
from ayassek.utils.logging import get_logger

logger = get_logger(__name__)


@dataclass
class IngestTask:
    task_id: str
    source: str
    file_path: str
    category: str
    tags: list[str]
    metadata: dict
    table_name: str
    status: str = "pending"
    progress: float = 0.0
    current_stage: str = ""
    current_page: int = 0
    total_pages: int = 0
    result: Optional[dict] = None
    error: Optional[str] = None
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat() + "Z")
    updated_at: str = field(default_factory=lambda: datetime.utcnow().isoformat() + "Z")


class IngestionService:
    def __init__(self):
        self.rag = get_rag_engine()
        self.second_brain = get_second_brain()
        self.repo_inspire_path = Path("REPOSTOINSPIRE")

    def ingest_repostoinpire(self, table_name: str = "ayassek_rag") -> dict:
        if not self.repo_inspire_path.exists():
            return {"error": "REPOSTOINSPIRE directory not found", "ingested": 0}

        results = {
            "repos_processed": 0,
            "readmes_found": 0,
            "chunks_created": 0,
            "vectors_stored": 0,
            "errors": [],
        }

        for repo_dir in self.repo_inspire_path.iterdir():
            if not repo_dir.is_dir():
                continue

            readme_path = self._find_readme(repo_dir)
            if not readme_path:
                continue

            results["readmes_found"] += 1

            try:
                with open(readme_path, "r", encoding="utf-8") as f:
                    content = f.read()

                rel_path = readme_path.relative_to(self.repo_inspire_path)
                source = f"REPOSTOINSPIRE/{rel_path}"

                metadata = {
                    "repo": repo_dir.name,
                    "file": str(rel_path),
                    "type": "readme",
                }

                result = self.rag.ingest_text(
                    text=content,
                    source=source,
                    category="reference",
                    tags=["repo", "readme", repo_dir.name],
                    metadata=metadata,
                    table_name=table_name,
                )

                results["repos_processed"] += 1
                results["chunks_created"] += result.chunks_created
                results["vectors_stored"] += result.vectors_stored
                results["errors"].extend(result.errors)

            except Exception as e:
                results["errors"].append(f"Failed to process {repo_dir.name}: {e}")

        logger.info(f"REPOSTOINSPIRE ingestion: {results}")
        return results

    def _find_readme(self, repo_dir: Path) -> Optional[Path]:
        for name in ["README.md", "README.txt", "README.rst", "readme.md", "readme.txt"]:
            readme = repo_dir / name
            if readme.exists():
                return readme
        return None

    def ingest_uploads(self, table_name: str = "ayassek_rag") -> dict:
        uploads_path = Path(settings.storage.upload_dir)
        if not uploads_path.exists():
            return {"error": "Uploads directory not found", "ingested": 0}

        results = {
            "files_processed": 0,
            "chunks_created": 0,
            "vectors_stored": 0,
            "errors": [],
        }

        extensions = (".md", ".txt", ".py", ".json", ".yaml", ".yml", ".pdf")

        for ext in extensions:
            for file_path in uploads_path.rglob(f"*{ext}"):
                if file_path.is_file():
                    try:
                        metadata = {
                            "file_path": str(file_path.relative_to(uploads_path)),
                            "type": "upload",
                        }

                        result = self.rag.ingest_file(
                            file_path=str(file_path),
                            category="upload",
                            tags=["upload", file_path.suffix[1:]],
                            metadata=metadata,
                            table_name=table_name,
                        )

                        results["files_processed"] += 1
                        results["chunks_created"] += result.chunks_created
                        results["vectors_stored"] += result.vectors_stored
                        results["errors"].extend(result.errors)

                    except Exception as e:
                        results["errors"].append(f"Failed to process {file_path}: {e}")

        logger.info(f"Uploads ingestion: {results}")
        return results

    def ingest_all(self, table_name: str = "ayassek_rag") -> dict:
        repo_results = self.ingest_repostoinpire(table_name)
        upload_results = self.ingest_uploads(table_name)

        return {
            "repostoinpire": repo_results,
            "uploads": upload_results,
            "total_chunks": repo_results.get("chunks_created", 0) + upload_results.get("chunks_created", 0),
            "total_vectors": repo_results.get("vectors_stored", 0) + upload_results.get("vectors_stored", 0),
        }

    def build_second_brain_index(self, table_name: str = "ayassek_rag") -> int:
        return self.second_brain.index_to_vectors(table_name)

    def full_reindex(self, table_name: str = "ayassek_rag") -> dict:
        self.rag.delete_category("reference", table_name)
        self.rag.delete_category("upload", table_name)
        for cat in self.second_brain.categories:
            self.rag.delete_category(f"second_brain_{cat}", table_name)

        self.rag.create_index(table_name)

        results = self.ingest_all(table_name)
        results["second_brain_indexed"] = self.build_second_brain_index(table_name)

        return results

    def has_text_layer(self, pdf_path: str, max_pages: int = 3) -> bool:
        """Check if PDF has extractable text layer (digital PDF)."""
        try:
            import pdfplumber
            with pdfplumber.open(pdf_path) as pdf:
                pages_to_check = min(max_pages, len(pdf.pages))
                for i in range(pages_to_check):
                    text = pdf.pages[i].extract_text()
                    if text and text.strip():
                        return True
            return False
        except Exception as e:
            logger.warning(f"Failed to check text layer for {pdf_path}: {e}")
            return False

    def _extract_text_with_qwen_vl(self, image_path: str) -> str:
        """Extract text from image using qwen3-vl via Ollama HTTP API."""
        try:
            ollama_url = settings.providers.get("ollama", {}).get("base_url", "http://localhost:11434")
            
            with open(image_path, "rb") as f:
                img_b64 = base64.b64encode(f.read()).decode()
            
            prompt = (
                "Extract all text from this page as clean Markdown. "
                "Preserve structure: headers, tables, lists, code blocks. "
                "Output only the extracted Markdown."
            )
            
            payload = {
                "model": "qwen3-vl:8b",
                "messages": [
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": prompt},
                            {"type": "image", "image": img_b64}
                        ]
                    }
                ],
                "stream": False,
                "options": {"temperature": 0.1}
            }
            
            with httpx.Client(timeout=120.0) as client:
                response = client.post(f"{ollama_url}/api/chat", json=payload)
                response.raise_for_status()
                data = response.json()
                
            if "message" in data and "content" in data["message"]:
                return data["message"]["content"] or ""
            return ""
        except Exception as e:
            logger.error(f"Qwen VL extraction failed for {image_path}: {e}")
            return ""

    def ingest_scanned_pdf(
        self,
        pdf_path: str,
        category: str = "upload",
        tags: list[str] = None,
        metadata: dict = None,
        table_name: str = "ayassek_rag",
        task: "IngestTask" = None
    ) -> dict:
        """Ingest scanned PDF using OCR with qwen3-vl."""
        tags = tags or ["scanned", "ocr"]
        metadata = metadata or {}
        metadata.update({"original_file": pdf_path, "type": "scanned_pdf"})

        try:
            from pdf2image import convert_from_path
        except ImportError:
            logger.error("pdf2image not installed")
            return {"chunks_created": 0, "vectors_stored": 0, "errors": ["pdf2image not installed"]}

        if task:
            task.current_stage = "ocr"
            task.total_pages = 0

        # Convert PDF to images
        with tempfile.TemporaryDirectory() as tmpdir:
            images = convert_from_path(pdf_path, output_folder=tmpdir, fmt="png", dpi=200)
            
            if task:
                task.total_pages = len(images)
            
            all_text = []
            for i, image in enumerate(images):
                if task:
                    task.current_page = i + 1
                    task.progress = (i / len(images)) * 0.8
                    task.updated_at = datetime.utcnow().isoformat() + "Z"
                
                img_path = os.path.join(tmpdir, f"page_{i+1}.png")
                image.save(img_path, "PNG")
                
                text = self._extract_text_with_qwen_vl(img_path)
                if text:
                    all_text.append(f"--- Page {i+1} ---\n{text}")

        if not all_text:
            return {"chunks_created": 0, "vectors_stored": 0, "errors": ["No text extracted from PDF"]}

        full_text = "\n\n".join(all_text)
        
        if task:
            task.current_stage = "chunking"
            task.progress = 0.85

        result = self.rag.ingest_text(
            text=full_text,
            source=pdf_path,
            category=category,
            tags=tags,
            metadata=metadata,
            table_name=table_name,
        )

        if task:
            task.progress = 1.0
            task.current_stage = "completed"
            task.updated_at = datetime.utcnow().isoformat() + "Z"

        return {
            "chunks_created": result.chunks_created,
            "vectors_stored": result.vectors_stored,
            "errors": result.errors,
        }

    def _convert_with_marker(self, pdf_path: str) -> str:
        """Convert digital PDF to Markdown using marker-pdf."""
        try:
            from marker.converters.pdf import PdfConverter
            from marker.models import create_model_dict
            from marker.output import text_from_rendered

            converter = PdfConverter(
                artifact_dict=create_model_dict(),
            )
            rendered = converter(pdf_path)
            text, _, _ = text_from_rendered(rendered)
            return text
        except Exception as e:
            logger.warning("marker-pdf conversion failed (falling back to basic extraction): %s", e)
            try:
                import pdfplumber
                with pdfplumber.open(pdf_path) as pdf:
                    pages = []
                    for page in pdf.pages:
                        text = page.extract_text()
                        if text:
                            pages.append(text)
                    return "\n\n".join(pages)
            except Exception as e2:
                logger.error("Fallback PDF extraction also failed: %s", e2)
                return ""

    def _ingest_digital_pdf(
        self,
        pdf_path: str,
        category: str = "upload",
        tags: list[str] = None,
        metadata: dict = None,
        table_name: str = "ayassek_rag",
        task: "IngestTask" = None
    ) -> dict:
        """Ingest digital PDF using marker-pdf for structure preservation."""
        if task:
            task.current_stage = "converting"
            task.progress = 0.2

        text = self._convert_with_marker(pdf_path)
        if not text:
            return {"chunks_created": 0, "vectors_stored": 0, "errors": ["No text extracted from PDF"]}

        if task:
            task.current_stage = "chunking"
            task.progress = 0.7

        result = self.rag.ingest_text(
            text=text,
            source=pdf_path,
            category=category,
            tags=tags,
            metadata=metadata,
            table_name=table_name,
        )

        if task:
            task.progress = 1.0
            task.current_stage = "completed"
            task.updated_at = datetime.utcnow().isoformat() + "Z"

        return {
            "chunks_created": result.chunks_created,
            "vectors_stored": result.vectors_stored,
            "errors": result.errors,
        }

    def ingest_file_unified(
        self,
        file_path: str,
        category: str = "upload",
        tags: list[str] = None,
        metadata: dict = None,
        table_name: str = "ayassek_rag",
        task: "IngestTask" = None
    ) -> dict:
        """Auto-detect PDF type and route to appropriate pipeline."""
        if not file_path.lower().endswith(".pdf"):
            return self.rag.ingest_file(
                file_path=file_path,
                category=category,
                tags=tags,
                metadata=metadata,
                table_name=table_name,
            )

        if task:
            task.current_stage = "detecting"
            task.progress = 0.1

        is_digital = self.has_text_layer(file_path)
        
        if is_digital:
            logger.info(f"Digital PDF detected: {file_path}")
            return self._ingest_digital_pdf(
                pdf_path=file_path,
                category=category,
                tags=tags or ["digital", "pdf"],
                metadata=metadata,
                table_name=table_name,
                task=task,
            )
        else:
            logger.info(f"Scanned PDF detected: {file_path}")
            return self.ingest_scanned_pdf(
                pdf_path=file_path,
                category=category,
                tags=tags or ["scanned", "ocr"],
                metadata=metadata,
                table_name=table_name,
                task=task,
            )


_ingestion_service: Optional[IngestionService] = None
_ingestion_queue: asyncio.Queue = asyncio.Queue()
_ingestion_tasks: dict[str, IngestTask] = {}
_queue_worker_started = False


async def _ingestion_worker():
    """Background worker that processes ingestion tasks sequentially."""
    while True:
        task = await _ingestion_queue.get()
        if task is None:
            break
        
        service = get_ingestion_service()
        task.status = "running"
        task.updated_at = datetime.utcnow().isoformat() + "Z"
        
        # Emit started event
        bus = get_event_bus()
        await bus.emit(Event(
            type=EventType.INGEST_STARTED,
            data={
                "task_id": task.task_id,
                "source": task.source,
                "category": task.category,
            },
            session_id="system",
        ))
        
        try:
            result = service.ingest_file_unified(
                file_path=task.file_path,
                category=task.category,
                tags=task.tags,
                metadata=task.metadata,
                table_name=task.table_name,
                task=task,
            )
            task.result = result
            task.status = "completed"
            task.progress = 1.0
            
            # Emit complete event
            await bus.emit(Event(
                type=EventType.INGEST_COMPLETE,
                data={
                    "task_id": task.task_id,
                    "chunks_created": result.get("chunks_created", 0),
                    "vectors_stored": result.get("vectors_stored", 0),
                    "errors": result.get("errors", []),
                },
                session_id="system",
            ))
        except Exception as e:
            logger.error(f"Ingestion task {task.task_id} failed: {e}")
            task.status = "failed"
            task.error = str(e)
            
            # Emit failed event
            await bus.emit(Event(
                type=EventType.INGEST_FAILED,
                data={
                    "task_id": task.task_id,
                    "error": str(e),
                },
                session_id="system",
            ))
        
        task.updated_at = datetime.utcnow().isoformat() + "Z"
        _ingestion_queue.task_done()


async def start_ingestion_worker():
    """Start the background ingestion worker."""
    global _queue_worker_started
    if not _queue_worker_started:
        _queue_worker_started = True
        asyncio.create_task(_ingestion_worker())


def get_ingestion_service() -> IngestionService:
    global _ingestion_service
    if _ingestion_service is None:
        _ingestion_service = IngestionService()
    return _ingestion_service


def queue_ingestion(
    file_path: str,
    category: str = "upload",
    tags: list[str] = None,
    metadata: dict = None,
    table_name: str = "ayassek_rag",
) -> str:
    """Queue a file for async ingestion. Returns task_id."""
    task_id = uuid.uuid4().hex[:12]
    task = IngestTask(
        task_id=task_id,
        source=file_path,
        file_path=file_path,
        category=category,
        tags=tags or [],
        metadata=metadata or {},
        table_name=table_name,
    )
    _ingestion_tasks[task_id] = task
    _ingestion_queue.put_nowait(task)
    return task_id


def get_ingestion_task(task_id: str) -> Optional[IngestTask]:
    return _ingestion_tasks.get(task_id)