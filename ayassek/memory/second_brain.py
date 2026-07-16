import json
import os
import shutil
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional

from ayassek.config.settings import settings
from ayassek.memory.chunker import ChunkerFactory
from ayassek.memory.embeddings import get_embedding_service
from ayassek.memory.vector_db import get_lancedb_service, VectorRecord
from ayassek.utils.logging import get_logger

logger = get_logger(__name__)

DEFAULT_CATEGORIES = [
    "projects", "people", "concepts", "meetings", "references", "tasks"
]

@dataclass
class Fact:
    id: str
    text: str
    category: str
    tags: list[str] = field(default_factory=list)
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat() + "Z")
    status: str = "active"
    source: str = "manual"
    importance: int = 50
    version_history: list[dict] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "text": self.text,
            "category": self.category,
            "tags": self.tags,
            "timestamp": self.timestamp,
            "status": self.status,
            "source": self.source,
            "importance": self.importance,
            "version_history": self.version_history,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Fact":
        return cls(
            id=data.get("id", str(uuid.uuid4())[:8]),
            text=data.get("text", ""),
            category=data.get("category", "general"),
            tags=data.get("tags", []),
            timestamp=data.get("timestamp", datetime.utcnow().isoformat() + "Z"),
            status=data.get("status", "active"),
            source=data.get("source", "manual"),
            importance=data.get("importance", 50),
            version_history=data.get("version_history", []),
        )

    def add_version(self, old_text: str, old_status: str):
        self.version_history.append({
            "text": old_text,
            "status": old_status,
            "timestamp": self.timestamp,
        })

    def update_text(self, new_text: str, new_status: str = "active"):
        self.add_version(self.text, self.status)
        self.text = new_text
        self.status = new_status
        self.timestamp = datetime.utcnow().isoformat() + "Z"


@dataclass
class Entity:
    name: str
    category: str
    summary: str = ""
    facts: list[Fact] = field(default_factory=list)
    path: str = ""
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat() + "Z")
    updated_at: str = field(default_factory=lambda: datetime.utcnow().isoformat() + "Z")

    @property
    def items_path(self) -> str:
        return os.path.join(self.path, "items.json")

    @property
    def summary_path(self) -> str:
        return os.path.join(self.path, "summary.md")

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "category": self.category,
            "summary": self.summary,
            "facts": [f.to_dict() for f in self.facts],
            "path": self.path,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }


class SecondBrain:
    def __init__(self, base_path: Optional[str] = None):
        self.base_path = base_path or settings.memory.second_brain.path
        self.categories = getattr(settings.memory.second_brain, "categories", DEFAULT_CATEGORIES)
        self._ensure_structure()

    def _ensure_structure(self):
        Path(self.base_path).mkdir(parents=True, exist_ok=True)
        for cat in self.categories:
            Path(self.base_path, cat).mkdir(parents=True, exist_ok=True)

    def _get_category_path(self, category: str) -> Path:
        return Path(self.base_path) / category

    def _get_entity_path(self, category: str, name: str) -> Path:
        safe_name = "".join(c for c in name if c.isalnum() or c in ("-", "_", " ")).strip()
        return self._get_category_path(category) / safe_name

    def list_entities(self, category: Optional[str] = None) -> list[dict]:
        entities = []
        cats = [category] if category else self.categories

        for cat in cats:
            cat_path = self._get_category_path(cat)
            if not cat_path.exists():
                continue
            for entity_dir in cat_path.iterdir():
                if entity_dir.is_dir():
                    items_path = entity_dir / "items.json"
                    summary_path = entity_dir / "summary.md"
                    pos_path = entity_dir / "position.json"
                    summary = ""
                    facts_count = 0
                    x, y = None, None
                    if summary_path.exists():
                        summary = summary_path.read_text(encoding="utf-8")
                    if items_path.exists():
                        try:
                            with open(items_path) as f:
                                facts = json.load(f)
                                facts_count = len(facts)
                        except Exception:
                            pass
                    if pos_path.exists():
                        try:
                            with open(pos_path) as f:
                                pos = json.load(f)
                                x = pos.get("x")
                                y = pos.get("y")
                        except Exception:
                            pass

                    entities.append({
                        "name": entity_dir.name,
                        "category": cat,
                        "summary_preview": summary[:200] + "..." if len(summary) > 200 else summary,
                        "facts_count": facts_count,
                        "path": str(entity_dir),
                        "x": x,
                        "y": y,
                    })

        return entities

    def get_entity(self, category: str, name: str) -> Optional[Entity]:
        entity_path = self._get_entity_path(category, name)
        if not entity_path.exists():
            return None

        items_path = entity_path / "items.json"
        summary_path = entity_path / "summary.md"

        summary = ""
        if summary_path.exists():
            summary = summary_path.read_text(encoding="utf-8")

        facts = []
        if items_path.exists():
            try:
                with open(items_path) as f:
                    facts_data = json.load(f)
                    facts = [Fact.from_dict(d) for d in facts_data]
            except Exception as e:
                logger.warning(f"Failed to load facts for {category}/{name}: {e}")

        return Entity(
            name=name,
            category=category,
            summary=summary,
            facts=facts,
            path=str(entity_path),
        )

    def create_entity(self, category: str, name: str, summary: str = "", x: float | None = None, y: float | None = None) -> Entity:
        if category not in self.categories:
            self.categories.append(category)

        entity_path = self._get_entity_path(category, name)
        entity_path.mkdir(parents=True, exist_ok=True)

        items_path = entity_path / "items.json"
        summary_path = entity_path / "summary.md"
        pos_path = entity_path / "position.json"

        if not items_path.exists():
            items_path.write_text("[]", encoding="utf-8")

        if summary and not summary_path.exists():
            summary_path.write_text(summary, encoding="utf-8")

        if x is not None and y is not None:
            pos_path.write_text(json.dumps({"x": x, "y": y}), encoding="utf-8")

        return Entity(
            name=name,
            category=category,
            summary=summary,
            path=str(entity_path),
        )

    def update_entity_summary(self, category: str, name: str, summary: str) -> bool:
        entity_path = self._get_entity_path(category, name)
        if not entity_path.exists():
            return False

        summary_path = entity_path / "summary.md"
        summary_path.write_text(summary, encoding="utf-8")
        return True

    def delete_entity(self, category: str, name: str) -> bool:
        entity_path = self._get_entity_path(category, name)
        if entity_path.exists():
            shutil.rmtree(entity_path)
            return True
        return False

    def add_fact(self, category: str, name: str, fact: Fact) -> bool:
        entity = self.get_entity(category, name)
        if entity is None:
            entity = self.create_entity(category, name)

        # Deduplication: skip if a fact with the same text already exists (case-insensitive)
        new_text_lower = fact.text.strip().lower()
        for existing in entity.facts:
            if existing.text.strip().lower() == new_text_lower:
                return False

        entity.facts.append(fact)
        return self._save_facts(entity)

    def set_entity_position(self, category: str, name: str, x: float, y: float) -> bool:
        entity_path = self._get_entity_path(category, name)
        if not entity_path.exists():
            return False
        import json as _json
        pos_path = entity_path / "position.json"
        pos_path.write_text(_json.dumps({"x": x, "y": y}), encoding="utf-8")
        return True

    def update_fact(self, category: str, name: str, fact_id: str, text: Optional[str] = None,
                    status: Optional[str] = None, tags: Optional[list[str]] = None,
                    importance: Optional[int] = None) -> bool:
        entity = self.get_entity(category, name)
        if entity is None:
            return False

        for fact in entity.facts:
            if fact.id == fact_id:
                if text is not None:
                    fact.update_text(text, status or fact.status)
                if status is not None and text is None:
                    fact.status = status
                    fact.timestamp = datetime.utcnow().isoformat() + "Z"
                if tags is not None:
                    fact.tags = tags
                if importance is not None:
                    fact.importance = importance
                return self._save_facts(entity)

        return False

    def delete_fact(self, category: str, name: str, fact_id: str) -> bool:
        entity = self.get_entity(category, name)
        if entity is None:
            return False

        entity.facts = [f for f in entity.facts if f.id != fact_id]
        return self._save_facts(entity)

    def _save_facts(self, entity: Entity) -> bool:
        try:
            items_path = Path(entity.path) / "items.json"
            data = [f.to_dict() for f in entity.facts]
            items_path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
            return True
        except Exception as e:
            logger.error(f"Failed to save facts for {entity.category}/{entity.name}: {e}")
            return False

    def search_facts(self, query: str, category: Optional[str] = None, top_k: int = 10) -> list[dict]:
        embedding_service = get_embedding_service()
        lancedb = get_lancedb_service()

        query_emb = embedding_service.embed_single(query)
        if category:
            safe_cat = category.replace("'", "''")
            filter_expr = f"category = '{safe_cat}'"
        else:
            filter_expr = "category LIKE 'second_brain_%'"

        try:
            results = lancedb.search_with_score(
                query_vector=query_emb,
                top_k=top_k,
                table_name="ayassek_rag",
                filter_expr=filter_expr,
                score_threshold=0.5,
            )
        except Exception as e:
            logger.warning(f"Second brain vector search failed: {e}")
            return self._search_facts_local(query, category, top_k)

        found = []
        for r, score in results:
            source_path = r.get("source", "")
            entity_name = source_path.split("/")[-2] if "/" in source_path else source_path
            category_raw = r.get("category", "")
            category = category_raw.replace("second_brain_", "", 1)
            found.append({
                "entity": entity_name,
                "category": category,
                "fact_id": r.get("id"),
                "text": r.get("text"),
                "tags": r.get("tags", []),
                "timestamp": r.get("timestamp"),
                "score": float(1.0 - score) if score <= 1.0 else float(score),
            })

        return found

    def _search_facts_local(self, query: str, category: Optional[str], top_k: int) -> list[dict]:
        query_lower = query.lower()
        found = []

        for cat in ([category] if category else self.categories):
            cat_path = self._get_category_path(cat)
            if not cat_path.exists():
                continue

            for entity_dir in cat_path.iterdir():
                if not entity_dir.is_dir():
                    continue
                items_path = entity_dir / "items.json"
                if not items_path.exists():
                    continue

                try:
                    with open(items_path) as f:
                        facts_data = json.load(f)

                    for fact_data in facts_data:
                        if fact_data.get("status") != "active":
                            continue
                        text = fact_data.get("text", "").lower()
                        if query_lower in text or any(tag in text for tag in query_lower.split()):
                            found.append({
                                "entity": entity_dir.name,
                                "category": cat,
                                "fact_id": fact_data.get("id"),
                                "text": fact_data.get("text"),
                                "tags": fact_data.get("tags", []),
                                "timestamp": fact_data.get("timestamp"),
                                "score": 1.0,
                            })
                except Exception:
                    continue

        return found[:top_k]

    def index_to_vectors(self, table_name: str = "ayassek_rag") -> int:
        lancedb = get_lancedb_service()
        embedding_service = get_embedding_service()
        total_indexed = 0

        for cat in self.categories:
            cat_path = self._get_category_path(cat)
            if not cat_path.exists():
                continue

            for entity_dir in cat_path.iterdir():
                if not entity_dir.is_dir():
                    continue

                items_path = entity_dir / "items.json"
                summary_path = entity_dir / "summary.md"

                records = []
                timestamp = datetime.utcnow().isoformat() + "Z"

                if summary_path.exists():
                    summary = summary_path.read_text(encoding="utf-8")
                    if summary.strip():
                        chunks = ChunkerFactory.chunk_text(summary, f"{cat}/{entity_dir.name}/summary.md", f"second_brain_{cat}")
                        if chunks:
                            texts = [c.text for c in chunks]
                            embeddings = embedding_service.embed(texts)
                            for chunk, emb in zip(chunks, embeddings):
                                records.append(VectorRecord(
                                    id=chunk.id,
                                    text=chunk.text,
                                    vector=emb,
                                    source=f"{cat}/{entity_dir.name}/summary.md",
                                    chunk_index=chunk.chunk_index,
                                    category=f"second_brain_{cat}",
                                    tags=["summary", cat],
                                    metadata={"entity": entity_dir.name, "type": "summary"},
                                    timestamp=timestamp,
                                ))

                if items_path.exists():
                    try:
                        with open(items_path) as f:
                            facts_data = json.load(f)

                        active_facts = [f for f in facts_data if f.get("status") == "active"]
                        if active_facts:
                            fact_texts = []
                            for fact in active_facts:
                                tag_str = f" [tags: {', '.join(fact.get('tags', []))}]" if fact.get('tags') else ""
                                fact_texts.append(f"{fact.get('text')}{tag_str}")

                            embeddings = embedding_service.embed(fact_texts)
                            for fact, emb in zip(active_facts, embeddings):
                                records.append(VectorRecord(
                                    id=fact.get("id", str(uuid.uuid4())[:8]),
                                    text=fact.get("text", ""),
                                    vector=emb,
                                    source=f"{cat}/{entity_dir.name}/items.json",
                                    chunk_index=0,
                                    category=f"second_brain_{cat}",
                                    tags=fact.get("tags", []) + ["fact", cat],
                                    metadata={
                                        "entity": entity_dir.name,
                                        "type": "fact",
                                        "status": fact.get("status", "active"),
                                        "source_type": fact.get("source", "manual"),
                                    },
                                    timestamp=fact.get("timestamp", timestamp),
                                ))
                    except Exception as e:
                        logger.warning(f"Failed to index facts for {cat}/{entity_dir.name}: {e}")

                if records:
                    lancedb.add_records(records, table_name)
                    total_indexed += len(records)

        logger.info(f"Indexed {total_indexed} second brain records to vectors")
        return total_indexed

    def get_stats(self) -> dict:
        total_entities = 0
        total_facts = 0
        total_summaries = 0

        for cat in self.categories:
            cat_path = self._get_category_path(cat)
            if not cat_path.exists():
                continue

            for entity_dir in cat_path.iterdir():
                if not entity_dir.is_dir():
                    continue
                total_entities += 1

                items_path = entity_dir / "items.json"
                summary_path = entity_dir / "summary.md"

                if items_path.exists():
                    try:
                        with open(items_path) as f:
                            facts = json.load(f)
                            total_facts += len([f for f in facts if f.get("status") == "active"])
                    except Exception:
                        pass

                if summary_path.exists() and summary_path.read_text().strip():
                    total_summaries += 1

        return {
            "base_path": self.base_path,
            "categories": self.categories,
            "total_entities": total_entities,
            "total_active_facts": total_facts,
            "total_summaries": total_summaries,
        }


_second_brain: Optional[SecondBrain] = None


def get_second_brain() -> SecondBrain:
    global _second_brain
    if _second_brain is None:
        _second_brain = SecondBrain()
    return _second_brain