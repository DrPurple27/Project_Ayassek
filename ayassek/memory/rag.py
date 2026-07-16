import json
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

from ayassek.config.settings import settings
from ayassek.memory.chunker import ChunkerFactory, Chunk
from ayassek.memory.embeddings import get_embedding_service
from ayassek.memory.reranker import get_reranker_service
from ayassek.memory.vector_db import get_lancedb_service, VectorRecord
from ayassek.utils.logging import get_logger

logger = get_logger(__name__)


@dataclass
class IngestionResult:
    source: str
    chunks_created: int
    vectors_stored: int
    duration_ms: float
    errors: list[str] = field(default_factory=list)


@dataclass
class RAGQueryResult:
    query: str
    chunks: list[dict] = field(default_factory=list)
    reranked: list[dict] = field(default_factory=list)
    context: str = ""
    metadata: dict = field(default_factory=dict)


class RAGEngine:
    def __init__(self):
        self._enabled = settings.memory.rag.enabled
        self._top_k_initial = settings.memory.rag.retrieval.top_k_initial
        self._top_k_final = settings.memory.rag.retrieval.top_k_final
        self._similarity_threshold = settings.memory.rag.retrieval.similarity_threshold
        self._reranker = get_reranker_service()
        self._embedding_service = get_embedding_service()
        self._lancedb = get_lancedb_service()
        self._chunker = ChunkerFactory()

    def ingest_text(
        self,
        text: str,
        source: str,
        category: str = "general",
        tags: list[str] = None,
        metadata: dict = None,
        table_name: str = "ayassek_rag",
    ) -> IngestionResult:
        start_time = time.time()
        tags = tags or []
        metadata = metadata or {}

        if not text.strip():
            return IngestionResult(
                source=source,
                chunks_created=0,
                vectors_stored=0,
                duration_ms=0,
                errors=["Empty text"],
            )

        errors = []
        chunks = []
        try:
            chunks = self._chunker.chunk_text(text, source, category)
        except Exception as e:
            errors.append(f"Chunking failed: {e}")

        if not chunks:
            return IngestionResult(
                source=source,
                chunks_created=0,
                vectors_stored=0,
                duration_ms=(time.time() - start_time) * 1000,
                errors=errors + ["No chunks created"],
            )

        chunk_texts = [c.text for c in chunks]
        try:
            embeddings = self._embedding_service.embed(chunk_texts)
        except Exception as e:
            errors.append(f"Embedding failed: {e}")
            return IngestionResult(
                source=source,
                chunks_created=len(chunks),
                vectors_stored=0,
                duration_ms=(time.time() - start_time) * 1000,
                errors=errors,
            )

        timestamp = datetime.utcnow().isoformat() + "Z"
        records = []
        for chunk, emb in zip(chunks, embeddings):
            chunk_metadata = metadata.copy()
            chunk_metadata.update(chunk.metadata)
            if chunk.tags:
                chunk_metadata["chunk_tags"] = chunk.tags

            records.append(VectorRecord(
                id=chunk.id,
                text=chunk.text,
                vector=emb,
                source=source,
                chunk_index=chunk.chunk_index,
                category=category,
                tags=tags + chunk.tags,
                metadata=chunk_metadata,
                timestamp=timestamp,
            ))

        vectors_stored = 0
        if records:
            try:
                vectors_stored = self._lancedb.add_records(records, table_name)
            except Exception as e:
                errors.append(f"Vector storage failed: {e}")

        duration_ms = (time.time() - start_time) * 1000
        return IngestionResult(
            source=source,
            chunks_created=len(chunks),
            vectors_stored=vectors_stored,
            duration_ms=duration_ms,
            errors=errors,
        )

    def ingest_file(
        self,
        file_path: str,
        category: str = "general",
        tags: list[str] = None,
        metadata: dict = None,
        table_name: str = "ayassek_rag",
    ) -> IngestionResult:
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                text = f.read()
        except UnicodeDecodeError:
            try:
                with open(file_path, "r", encoding="latin-1") as f:
                    text = f.read()
            except Exception as e:
                return IngestionResult(
                    source=file_path,
                    chunks_created=0,
                    vectors_stored=0,
                    duration_ms=0,
                    errors=[f"Failed to read file: {e}"],
                )

        source_meta = metadata or {}
        source_meta["original_file"] = file_path

        return self.ingest_text(
            text=text,
            source=file_path,
            category=category,
            tags=tags,
            metadata=source_meta,
            table_name=table_name,
        )

    def query(
        self,
        query_text: str,
        top_k: int = None,
        rerank: bool = None,
        table_name: str = "ayassek_rag",
        category: str = None,
        include_context: bool = True,
    ) -> RAGQueryResult:
        top_k = top_k or self._top_k_initial
        rerank = rerank if rerank is not None else self._reranker.is_enabled

        query_emb = self._embedding_service.embed_single(query_text)

        filter_expr = None
        if category:
            safe_cat = category.replace("'", "''")
            filter_expr = f"category = '{safe_cat}'"

        # Add soft delete filter
        delete_filter = "deleted != true"
        if filter_expr:
            filter_expr = f"({filter_expr}) AND {delete_filter}"
        else:
            filter_expr = delete_filter

        try:
            initial_results = self._lancedb.search_with_score(
                query_vector=query_emb,
                top_k=top_k,
                table_name=table_name,
                filter_expr=filter_expr,
                score_threshold=self._similarity_threshold,
            )
        except Exception as e:
            logger.error(f"Vector search failed: {e}")
            return RAGQueryResult(query=query_text, metadata={"chunks": [], "reranked": [], "context": "", "metadata": {"error": str(e)}})

        chunks = []
        for r, score in initial_results:
            chunks.append({
                "id": r.get("id"),
                "text": r.get("text"),
                "source": r.get("source"),
                "chunk_index": r.get("chunk_index"),
                "category": r.get("category"),
                "tags": r.get("tags", []),
                "metadata": r.get("metadata"),
                "timestamp": r.get("timestamp"),
                "similarity_score": float(1.0 - score) if score <= 1.0 else float(score),
            })

        reranked = []
        if chunks and rerank and self._reranker.is_enabled:
            doc_texts = [c["text"] for c in chunks]
            reranked_results = self._reranker.rerank(
                query=query_text,
                documents=doc_texts,
                top_k=self._top_k_final,
            )
            reranked = [
                {**chunks[r["index"]], "rerank_score": r["score"]}
                for r in reranked_results
            ]
        elif chunks:
            reranked = chunks[:self._top_k_final]

        context = ""
        if include_context and reranked:
            context_parts = []
            for i, c in enumerate(reranked):
                src = c.get("source", "unknown")
                txt = c.get("text", "")
                context_parts.append(f"[{i+1}] Source: {src}\n{txt}")
            context = "\n\n---\n\n".join(context_parts)

        return RAGQueryResult(
            query=query_text,
            chunks=chunks,
            reranked=reranked,
            context=context,
            metadata={
                "total_initial": len(chunks),
                "total_reranked": len(reranked),
                "reranker_used": rerank and self._reranker.is_enabled,
                "reranker_model": self._reranker.model_name if self._reranker.is_enabled else None,
            },
        )

    def query_formatted_context(
        self,
        query_text: str,
        top_k: int = None,
        table_name: str = "ayassek_rag",
    ) -> str:
        result = self.query(query_text, top_k=top_k, table_name=table_name, include_context=True)
        if not result.context:
            return ""
        return f"\n--- Retrieved Context (RAG) ---\n{result.context}\n--- End Context ---\n"

    def delete_by_source(self, source: str, table_name: str = "ayassek_rag") -> int:
        return self._lancedb.delete_by_source(source, table_name)

    def delete_category(self, category: str, table_name: str = "ayassek_rag") -> int:
        return self._lancedb.delete_by_category(category, table_name)

    def get_status(self, table_name: str = "ayassek_rag") -> dict:
        stats = self._lancedb.get_table_stats(table_name)
        return {
            "enabled": self._enabled,
            "table": table_name,
            "vector_count": stats.get("count", 0),
            "embedding_model": self._embedding_service.model_name,
            "embedding_dimension": self._embedding_service.dimension,
            "reranker_enabled": self._reranker.is_enabled,
            "reranker_model": self._reranker.model_name if self._reranker.is_enabled else None,
            "chunking_strategy": settings.memory.rag.chunking.strategy,
            "chunk_size": settings.memory.rag.chunking.chunk_size,
            "chunk_overlap": settings.memory.rag.chunking.chunk_overlap,
        }

    def create_index(self, table_name: str = "ayassek_rag"):
        self._lancedb.create_index(
            table_name=table_name,
            metric=settings.memory.rag.vector_db.index.metric,
            num_partitions=settings.memory.rag.vector_db.index.num_partitions,
            num_sub_vectors=settings.memory.rag.vector_db.index.num_sub_vectors,
        )

    def optimize(self, table_name: str = "ayassek_rag"):
        self._lancedb.optimize(table_name)

    def list_tables(self) -> list[str]:
        return self._lancedb.list_tables()


_rag_engine: Optional[RAGEngine] = None


def get_rag_engine() -> RAGEngine:
    global _rag_engine
    if _rag_engine is None:
        _rag_engine = RAGEngine()
    return _rag_engine