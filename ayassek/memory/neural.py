from __future__ import annotations

import time
from typing import Any

from ayassek.config.settings import settings
from ayassek.utils.logging import get_logger


class NeuralMemory:
    def __init__(self, chroma_path: str = "", threshold: float | None = None):
        self._client = None
        self._collection = None
        self._chroma_path = chroma_path or settings.memory.neural.chroma_path
        if threshold is not None:
            self._threshold = threshold
        else:
            self._threshold = settings.memory.neural.auto_connect_threshold
        self._logger = get_logger("neural_memory")
        self._initialized = False

    def _ensure_collection(self):
        if self._collection is not None:
            return
        try:
            import chromadb
            from chromadb.config import Settings as ChromaSettings
            chroma_settings = ChromaSettings(
                anonymized_telemetry=False,
                allow_reset=False,
            )
            self._client = chromadb.PersistentClient(
                path=self._chroma_path,
                settings=chroma_settings,
            )
            self._collection = self._client.get_or_create_collection(
                "neural_memory",
                metadata={"hnsw:space": "cosine"},
            )
            self._initialized = True
            self._logger.info("NeuralMemory ready at %s", self._chroma_path)
        except Exception as e:
            self._logger.warning("ChromaDB not available: %s. Neural memory disabled.", e)
            self._initialized = False

    def _is_available(self) -> bool:
        self._ensure_collection()
        return self._initialized

    def add_to_index(self, node_id: str, text: str):
        if not self._is_available():
            return
        try:
            self._collection.upsert(ids=[node_id], documents=[text], metadatas=[{"node_id": node_id, "added_at": time.time()}])
        except Exception as e:
            self._logger.warning("Failed to add to index: %s", e)

    def remove_from_index(self, node_id: str):
        if not self._is_available():
            return
        try:
            self._collection.delete(ids=[node_id])
        except Exception as e:
            self._logger.warning("Failed to remove from index: %s", e)

    def clear_index(self):
        """Drop and recreate the neural_memory collection — full reset, nothing survives."""
        if not self._is_available():
            return
        try:
            self._client.delete_collection("neural_memory")
            self._collection = None
            self._initialized = False
            self._ensure_collection()
            self._logger.info("NeuralMemory index cleared (collection recreated)")
        except Exception as e:
            self._logger.warning("Failed to clear index: %s", e)

    def update_in_index(self, node_id: str, text: str):
        if not self._is_available():
            return
        try:
            self._collection.upsert(ids=[node_id], documents=[text], metadatas=[{"node_id": node_id, "updated_at": time.time()}])
        except Exception as e:
            self._logger.warning("Failed to update index: %s", e)

    def auto_connect(self, node_id: str, text: str, graph_db) -> list[dict]:
        if not self._is_available():
            return []
        try:
            count = self._collection.count()
            if count == 0:
                return []

            n_results = min(10, count)
            results = self._collection.query(
                query_texts=[text],
                n_results=n_results,
            )

            auto_edges = []
            if results and results.get("distances") and results["distances"]:
                distances = results["distances"][0]
                match_ids = results["ids"][0] if results.get("ids") else []
                for i, dist in enumerate(distances):
                    similarity = 1.0 - dist
                    if similarity >= self._threshold:
                        match_id = match_ids[i] if i < len(match_ids) else None
                        if match_id and match_id != node_id:
                            # Skip if a reverse edge already exists (A→B when B→A present)
                            existing_reverse = graph_db._get_conn().execute(
                                "SELECT id FROM edges WHERE source_node_id=? AND target_node_id=?",
                                (match_id, node_id),
                            ).fetchone()
                            if existing_reverse:
                                continue
                            edge = graph_db.create_edge(
                                source_id=node_id,
                                target_id=match_id,
                                strength=round(similarity, 3),
                                is_manual=False,
                            )
                            auto_edges.append(edge)
                            self._logger.info("Auto-connected %s -> %s (similarity=%.3f)", node_id, match_id, similarity)

            return auto_edges
        except Exception as e:
            self._logger.warning("Auto-connect failed: %s", e)
            return []

    def search_similar(self, query: str, n_results: int = 5) -> list[dict]:
        if not self._is_available():
            return []
        try:
            count = self._collection.count()
            if count == 0:
                return []

            results = self._collection.query(query_texts=[query], n_results=min(n_results, count))
            nodes = []
            if results and results.get("ids") and results["ids"]:
                for i, node_id in enumerate(results["ids"][0]):
                    distance = results["distances"][0][i] if results.get("distances") else 0
                    doc = results["documents"][0][i] if results.get("documents") else ""
                    nodes.append({
                        "id": node_id,
                        "distance": distance,
                        "similarity": round(1.0 - distance, 3),
                        "document": doc,
                    })
            return nodes
        except Exception as e:
            self._logger.warning("Search failed: %s", e)
            return []

    def get_index_count(self) -> int:
        if not self._is_available():
            return 0
        try:
            return self._collection.count()
        except Exception:
            return 0