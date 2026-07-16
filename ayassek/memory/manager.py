from __future__ import annotations

import json
import uuid
from typing import Any

from ayassek.core.bus import AsyncEventBus
from ayassek.core.events import Event, EventType
from ayassek.memory.short_term import ShortTermMemory
from ayassek.memory.rag import get_rag_engine
from ayassek.memory.second_brain import get_second_brain
from ayassek.utils.logging import get_logger


class MemoryManager:
    def __init__(self, event_bus: AsyncEventBus | None = None):
        self._logger = get_logger("memory_manager")
        self._bus = event_bus
        self.short_term = ShortTermMemory()
        self._graph_db = None
        self._neural = None
        self._rag_engine = None
        self._second_brain = None

    @property
    def rag_engine(self):
        if self._rag_engine is None:
            self._rag_engine = get_rag_engine()
        return self._rag_engine

    @property
    def second_brain(self):
        if self._second_brain is None:
            self._second_brain = get_second_brain()
        return self._second_brain

    def _get_graph_db(self):
        if self._graph_db is None:
            from ayassek.memory.graph_db import GraphDB
            self._graph_db = GraphDB()
        return self._graph_db

    def _get_neural(self):
        if self._neural is None:
            from ayassek.memory.neural import NeuralMemory
            self._neural = NeuralMemory()
        return self._neural

    def add_message(self, role: str, content: str, session_id: str = "default", **extra: Any):
        self.short_term.add(role, content, session_id=session_id, **extra)
        try:
            self._get_graph_db().add_chat_message(session_id, role, content)
        except Exception as e:
            self._logger.warning("Failed to persist chat message: %s", e)

    def get_context(self, limit: int = 20, session_id: str = "default") -> list[dict[str, Any]]:
        try:
            msgs = self._get_graph_db().get_chat_messages(session_id, limit=limit)
            if msgs:
                return msgs
        except Exception as e:
            self._logger.warning("Failed to load persisted messages: %s", e)
        return self.short_term.get_messages(limit=limit, session_id=session_id)

    def clear_session(self, session_id: str = "default"):
        self.short_term.clear(session_id=session_id)
        try:
            self._get_graph_db().clear_chat_messages(session_id)
        except Exception as e:
            self._logger.warning("Failed to clear persisted messages: %s", e)
        self._emit("clear_session", session_id=session_id)

    def store(self, key: str, value: str):
        self.short_term.store(key, value)
        try:
            self._get_graph_db().store_kv(key, value)
        except Exception as e:
            self._logger.warning("Failed to persist kv: %s", e)
        self._emit("store", key=key)

    def recall(self, key: str) -> str | None:
        try:
            val = self._get_graph_db().recall_kv(key)
            if val is not None:
                return val
        except Exception as e:
            self._logger.warning("Failed to recall persisted kv: %s", e)
        return self.short_term.recall(key)

    def get_sessions(self) -> list[dict[str, Any]]:
        try:
            return self._get_graph_db().get_sessions()
        except Exception as e:
            self._logger.warning("Failed to get sessions: %s", e)
            return [{"id": "default", "name": "Default", "created_at": 0, "updated_at": 0}]

    def create_session(self, session_id: str, name: str) -> dict:
        try:
            return self._get_graph_db().create_session(session_id, name)
        except Exception as e:
            self._logger.warning("Failed to create session: %s", e)
            return {"id": session_id, "name": name, "summary": "", "created_at": 0, "updated_at": 0}

    def delete_session(self, session_id: str):
        try:
            self._get_graph_db().delete_session(session_id)
        except Exception as e:
            self._logger.warning("Failed to delete session: %s", e)
        self._emit("delete_session", session_id=session_id)

    def get_session_message_count(self, session_id: str) -> int:
        try:
            msgs = self._get_graph_db().get_chat_messages(session_id, limit=0)
            return len(msgs)
        except Exception:
            return len(self.short_term.get_messages(session_id=session_id))

    def get_all_session_summaries(self, exclude_session_id: str | None = None) -> list[dict]:
        sessions = self.get_sessions()
        result = []
        for s in sessions:
            if s["id"] == exclude_session_id:
                continue
            if s.get("summary", "").strip():
                result.append({"id": s["id"], "name": s["name"], "summary": s["summary"]})
        return result

    def update_session_summary(self, session_id: str, summary: str):
        try:
            self._get_graph_db().update_session_summary(session_id, summary)
        except Exception as e:
            self._logger.warning("Failed to update session summary: %s", e)

    def get_message_history(self, session_id: str, limit: int = 0) -> list[dict[str, Any]]:
        try:
            return self._get_graph_db().get_chat_messages(session_id, limit=limit)
        except Exception:
            return self.short_term.get_messages(session_id=session_id)

    def get_neuron_count(self) -> int:
        try:
            return len(self._get_graph_db().get_all_nodes())
        except Exception:
            return 0

    def create_neuron(self, title: str, content: str, x: float | None = None, y: float | None = None) -> dict:
        import random
        gdb = self._get_graph_db()
        conn = gdb._get_conn()
        existing_row = conn.execute(
            "SELECT id, title, content FROM nodes WHERE title=? COLLATE NOCASE LIMIT 1",
            (title.strip(),),
        ).fetchone()
        if existing_row:
            n = dict(existing_row)
            if content:
                gdb.update_node(n["id"], content=content)
                self._get_neural().update_in_index(n["id"], f"{title} {content}")
            self._emit("neuron_updated", node_id=n["id"])
            return {**n, "content": content or n.get("content", ""), "auto_edges": gdb.get_edges_for_node(n["id"])}
        if x is None or y is None:
            x = random.uniform(100, 600) if x is None else x
            y = random.uniform(100, 400) if y is None else y
        try:
            node = self._get_graph_db().create_node(title, content, x, y)
            text = f"{title} {content}"
            self._get_neural().add_to_index(node["id"], text)
            auto_edges = self._get_neural().auto_connect(node["id"], text, self._get_graph_db())
            node["auto_edges"] = auto_edges
            self._emit("neuron_created", node_id=node["id"])
            return node
        except Exception as e:
            self._logger.warning("Failed to create neuron: %s", e)
            raise

    def update_neuron(self, node_id: str, **fields) -> dict | None:
        try:
            node = self._get_graph_db().update_node(node_id, **fields)
            if node and ("title" in fields or "content" in fields):
                text = f"{node['title']} {node['content']}"
                self._get_neural().update_in_index(node_id, text)
            self._emit("neuron_updated", node_id=node_id)
            return node
        except Exception as e:
            self._logger.warning("Failed to update neuron: %s", e)
            return None

    def delete_neuron(self, node_id: str) -> bool:
        self._get_neural().remove_from_index(node_id)
        try:
            result = self._get_graph_db().delete_node(node_id)
        except Exception as e:
            self._logger.warning("Failed to delete neuron: %s", e)
            result = False
        self._emit("neuron_deleted", node_id=node_id)
        return result

    def clear_neural_memory(self) -> dict:
        import shutil
        from pathlib import Path

        result: dict = {
            "neurons_deleted": 0,
            "entities_deleted": 0,
            "vectors_deleted": 0,
            "categories_cleared": [],
            "chat_cleared": {},
        }

        from ayassek.config.settings import settings

        # 1 — clear all neurons from GraphDB + ChromaDB
        try:
            self._get_neural().clear_index()
        except Exception as e:
            self._logger.warning("ChromaDB clear failed: %s", e)
        try:
            result["neurons_deleted"] = self._get_graph_db().delete_all_nodes()
        except Exception as e:
            self._logger.warning("GraphDB delete_all_nodes failed: %s", e)

        # 1b — wipe ALL chat sessions, messages, and kv_store (non-migration)
        try:
            result["chat_cleared"] = self._get_graph_db().clear_all_sessions_and_messages()
            self.short_term.clear(session_id="default")
        except Exception as e:
            self._logger.warning("GraphDB clear sessions failed: %s", e)

        # 2 — wipe Second Brain (disk + entities + facts)
        categories = getattr(settings.memory.second_brain, "categories", ["projects", "people", "concepts", "meetings", "references", "tasks"])
        # also wipe any dynamically-added categories (e.g. legacy "general")
        sb_base = Path(settings.memory.second_brain.path)
        if sb_base.exists():
            for cat_dir in list(sb_base.iterdir()):
                if cat_dir.is_dir() and cat_dir.name not in categories:
                    categories.append(cat_dir.name)
        for cat in categories:
            cat_dir = sb_base / cat
            if cat_dir.exists():
                count = sum(1 for _ in cat_dir.iterdir())
                result["entities_deleted"] += count
                shutil.rmtree(cat_dir)
                result["categories_cleared"].append(cat)
        # re-create empty dirs
        self.second_brain._ensure_structure()

        # 3 — soft-delete all second_brain vectors from LanceDB
        try:
            for cat in categories:
                deleted = self.rag_engine.delete_category(f"second_brain_{cat}")
                result["vectors_deleted"] += deleted
        except Exception as e:
            self._logger.warning("LanceDB second_brain vector wipe failed: %s", e)

        return result

    def get_neurons(self) -> list[dict]:
        try:
            return self._get_graph_db().get_all_nodes()
        except Exception:
            return []

    def create_synapse(self, source_id: str, target_id: str, strength: float = 1.0, is_manual: bool = True) -> dict:
        try:
            edge = self._get_graph_db().create_edge(source_id, target_id, strength, is_manual)
            self._emit("synapse_created", edge_id=edge["id"])
            return edge
        except Exception as e:
            self._logger.warning("Failed to create synapse: %s", e)
            raise

    def get_synapses(self) -> list[dict]:
        try:
            return self._get_graph_db().get_all_edges()
        except Exception:
            return []

    def delete_synapse(self, edge_id: str) -> bool:
        try:
            result = self._get_graph_db().delete_edge(edge_id)
        except Exception as e:
            self._logger.warning("Failed to delete synapse: %s", e)
            result = False
        self._emit("synapse_deleted", edge_id=edge_id)
        return result

    def neural_search(self, query: str, n_results: int = 5) -> list[dict]:
        try:
            results = self._get_neural().search_similar(query, n_results=n_results)
            for r in results:
                node = self._get_graph_db().get_node(r["id"])
                if node:
                    r.update(node)
            return results
        except Exception as e:
            self._logger.warning("Neural search failed: %s", e)
            return []

    def get_status(self) -> dict[str, Any]:
        try:
            gdb = self._get_graph_db()
            session_count = gdb.get_session_count()
            msg_count = gdb.get_total_message_count()
            neuron_count = len(gdb.get_all_nodes())
            synapse_count = len(gdb.get_all_edges())
        except Exception:
            session_count = 0
            msg_count = 0
            neuron_count = 0
            synapse_count = 0

        rag_status = {}
        sb_status = {}
        try:
            rag_status = self.rag_engine.get_status()
        except Exception as e:
            self._logger.debug("RAG status failed: %s", e)
        try:
            sb_status = self.second_brain.get_stats()
        except Exception as e:
            self._logger.debug("Second brain status failed: %s", e)

        return {
            "short_term_messages": len(self.short_term.get_messages()),
            "short_term_store_keys": list(self.short_term.get_all_stored().keys()),
            "session_count": session_count,
            "total_messages": msg_count,
            "neuron_count": neuron_count,
            "synapse_count": synapse_count,
            "rag": rag_status,
            "second_brain": sb_status,
        }

    def rag_query(self, query: str, **kwargs) -> dict:
        result = self.rag_engine.query(query, **kwargs)
        return {
            "query": result.query,
            "context": result.context,
            "chunks": result.chunks,
            "reranked": result.reranked,
            "metadata": result.metadata,
        }

    def rag_ingest(self, text: str, source: str, **kwargs):
        return self.rag_engine.ingest_text(text, source, **kwargs)

    def sb_list_entities(self, category: str = None):
        return self.second_brain.list_entities(category)

    def sb_get_entity(self, category: str, name: str):
        entity = self.second_brain.get_entity(category, name)
        if entity:
            return entity.to_dict()
        return None

    def sb_create_entity(self, category: str, name: str, summary: str = ""):
        entity = self.second_brain.create_entity(category, name, summary)
        self._emit_event(EventType.ENTITY_CREATED, name=name, category=category, summary=summary)
        return entity.to_dict()

    def sb_update_summary(self, category: str, name: str, summary: str):
        ok = self.second_brain.update_entity_summary(category, name, summary)
        if ok:
            self._emit_event(EventType.ENTITY_UPDATED, name=name, category=category, summary=summary)
        return ok

    def sb_delete_entity(self, category: str, name: str):
        ok = self.second_brain.delete_entity(category, name)
        if ok:
            self._emit_event(EventType.ENTITY_DELETED, name=name, category=category)
        return ok

    def sb_list_facts(self, category: str, name: str):
        entity = self.second_brain.get_entity(category, name)
        if entity:
            return [f.to_dict() for f in entity.facts]
        return []

    def sb_add_fact(self, category: str, name: str, fact_data: dict):
        from ayassek.memory.second_brain import Fact
        fact = Fact.from_dict(fact_data)
        ok = self.second_brain.add_fact(category, name, fact)
        if ok:
            self._emit_event(EventType.FACT_ADDED, entity_name=name, category=category, text=fact_data.get("text", ""), status=fact_data.get("status", "active"))
        return ok

    def sb_update_fact(self, category: str, name: str, fact_id: str, **kwargs):
        ok = self.second_brain.update_fact(category, name, fact_id, **kwargs)
        if ok:
            self._emit_event(EventType.FACT_UPDATED, entity_name=name, category=category, fact_id=fact_id)
        return ok

    def sb_delete_fact(self, category: str, name: str, fact_id: str):
        ok = self.second_brain.delete_fact(category, name, fact_id)
        if ok:
            self._emit_event(EventType.FACT_DELETED, entity_name=name, category=category, fact_id=fact_id)
        return ok

    def sb_search(self, query: str, **kwargs):
        return self.second_brain.search_facts(query, **kwargs)

    def sb_index_to_vectors(self):
        return self.second_brain.index_to_vectors()

    def _emit(self, action: str, **extra):
        if self._bus is None:
            return
        import asyncio
        try:
            loop = asyncio.get_running_loop()
            data = {"action": action, **extra}
            task = loop.create_task(self._bus.emit(Event(
                type=EventType.MEMORY_UPDATED,
                data=data,
            )))
            task.add_done_callback(lambda t: t.exception() if not t.cancelled() else None)
        except RuntimeError:
            pass

    def _emit_event(self, event_type: EventType, **data):
        """Emit a specific event type with data."""
        if self._bus is None:
            return
        import asyncio
        try:
            loop = asyncio.get_running_loop()
            task = loop.create_task(self._bus.emit(Event(
                type=event_type,
                data=data,
            )))
            task.add_done_callback(lambda t: t.exception() if not t.cancelled() else None)
        except RuntimeError:
            pass

    def get_all_stored(self) -> dict[str, str]:
        return self.short_term.get_all_stored()

    def get_messages(self, **kwargs) -> list[dict[str, Any]]:
        return self.short_term.get_messages(**kwargs)

    # Settings persistence (runtime changes → SQLite kv_store)
    def persist_setting(self, section: str, key: str, value: Any) -> bool:
        """Persist a runtime setting change to kv_store."""
        try:
            k = f"settings.{section}.{key}"
            self._get_graph_db().store_kv(k, json.dumps(value))
            self._logger.debug("Persisted setting: %s = %s", k, value)
            return True
        except Exception as e:
            self._logger.warning("Failed to persist setting %s.%s: %s", section, key, e)
            return False

    def get_setting(self, section: str, key: str, default: Any = None) -> Any:
        """Retrieve a runtime setting from kv_store."""
        try:
            k = f"settings.{section}.{key}"
            val = self._get_graph_db().recall_kv(k)
            if val is not None:
                return json.loads(val)
        except Exception:
            pass
        return default

    def get_section_settings(self, section: str) -> dict[str, Any]:
        """Get all settings for a section."""
        try:
            prefix = f"settings.{section}."
            all_kv = self._get_graph_db().get_all_kv()
            result = {}
            for k, v in all_kv.items():
                if k.startswith(prefix):
                    key = k[len(prefix):]
                    result[key] = json.loads(v)
            return result
        except Exception:
            return {}