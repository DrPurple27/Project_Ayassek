import os
import threading
from dataclasses import dataclass
from typing import Optional

from ayassek.config.settings import settings
from ayassek.utils.logging import get_logger

logger = get_logger(__name__)

_VECTOR_DIM = 1024


@dataclass
class VectorRecord:
    id: str
    text: str
    vector: list[float]
    source: str
    chunk_index: int
    category: str
    tags: list[str]
    metadata: dict
    timestamp: str


class LanceDBService:
    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._initialized = True

        self._db = None
        self._tables = {}
        self._path = settings.memory.rag.vector_db.path
        os.makedirs(self._path, exist_ok=True)

    def _get_db(self):
        if self._db is None:
            try:
                import lancedb
            except ImportError:
                logger.error("lancedb not installed. Run: pip install lancedb>=0.6.0")
                raise

            self._db = lancedb.connect(self._path)
            logger.info(f"Connected to LanceDB at {self._path}")

        return self._db

    def _get_table(self, table_name: str = "ayassek_rag"):
        if table_name not in self._tables:
            db = self._get_db()
            if table_name in db.table_names():
                self._tables[table_name] = db.open_table(table_name)
            else:
                self._tables[table_name] = self._create_table(table_name)
        return self._tables[table_name]

    def _create_table(self, table_name: str):
        db = self._get_db()
        import pyarrow as pa

        schema = pa.schema([
            pa.field("id", pa.string()),
            pa.field("text", pa.string()),
            pa.field("vector", pa.list_(pa.float32(), _VECTOR_DIM)),
            pa.field("source", pa.string()),
            pa.field("chunk_index", pa.int32()),
            pa.field("category", pa.string()),
            pa.field("tags", pa.list_(pa.string())),
            pa.field("metadata", pa.string()),
            pa.field("timestamp", pa.string()),
            pa.field("deleted", pa.bool_()),
        ])

        table = db.create_table(table_name, schema=schema)
        logger.info(f"Created LanceDB table: {table_name}")
        return table

    def add_records(self, records: list[VectorRecord], table_name: str = "ayassek_rag") -> int:
        if not records:
            return 0

        table = self._get_table(table_name)

        data = []
        for r in records:
            data.append({
                "id": r.id,
                "text": r.text,
                "vector": r.vector,
                "source": r.source,
                "chunk_index": r.chunk_index,
                "category": r.category,
                "tags": r.tags,
                "metadata": str(r.metadata),
                "timestamp": r.timestamp,
                "deleted": False,
            })

        table.add(data)
        logger.info(f"Added {len(records)} records to {table_name}")
        return len(records)

    def search(
        self,
        query_vector: list[float],
        top_k: int = 10,
        table_name: str = "ayassek_rag",
        filter_expr: Optional[str] = None,
    ) -> list[dict]:
        table = self._get_table(table_name)

        query = table.search(query_vector, vector_column_name="vector").limit(top_k)

        deleted_filter = "deleted != true"
        if filter_expr:
            query = query.where(f"({filter_expr}) AND {deleted_filter}")
        else:
            query = query.where(deleted_filter)

        return query.to_list()

    def search_with_score(
        self,
        query_vector: list[float],
        top_k: int = 10,
        table_name: str = "ayassek_rag",
        filter_expr: Optional[str] = None,
        score_threshold: float = 0.0,
    ) -> list[tuple[dict, float]]:
        table = self._get_table(table_name)

        query = table.search(query_vector, vector_column_name="vector").limit(top_k)

        deleted_filter = "deleted != true"
        if filter_expr:
            query = query.where(f"({filter_expr}) AND {deleted_filter}")
        else:
            query = query.where(deleted_filter)

        results = query.to_list()

        scored = []
        for r in results:
            score = r.get("_distance", 1.0)
            if score <= score_threshold:
                scored.append((r, score))

        return scored

    def delete_by_source(self, source: str, table_name: str = "ayassek_rag") -> int:
        table = self._get_table(table_name)
        safe_source = source.replace("'", "''")
        result = table.update(where=f"source = '{safe_source}'", values={"deleted": True})
        logger.info(f"Soft deleted records from {table_name} for source: {source}")
        return result

    def delete_by_category(self, category: str, table_name: str = "ayassek_rag") -> int:
        table = self._get_table(table_name)
        safe_cat = category.replace("'", "''")
        result = table.update(where=f"category = '{safe_cat}'", values={"deleted": True})
        logger.info(f"Soft deleted records from {table_name} for category: {category}")
        return result

    def get_table_stats(self, table_name: str = "ayassek_rag") -> dict:
        table = self._get_table(table_name)
        count = table.count_rows()
        return {"table": table_name, "count": count}

    def list_tables(self) -> list[str]:
        db = self._get_db()
        return db.table_names()

    def create_index(
        self,
        table_name: str = "ayassek_rag",
        metric: str = "cosine",
        num_partitions: int = 256,
        num_sub_vectors: int = 128,
    ):
        table = self._get_table(table_name)
        try:
            table.create_index(
                metric=metric,
                num_partitions=num_partitions,
                num_sub_vectors=num_sub_vectors,
            )
            logger.info(f"Created index on {table_name}")
        except Exception as e:
            logger.warning(f"Index creation failed (may already exist): {e}")

    def optimize(self, table_name: str = "ayassek_rag"):
        table = self._get_table(table_name)
        try:
            table.optimize()
            logger.info(f"Optimized table {table_name}")
        except Exception as e:
            logger.warning(f"Optimize failed: {e}")


_lancedb_service: Optional[LanceDBService] = None


def get_lancedb_service() -> LanceDBService:
    global _lancedb_service
    if _lancedb_service is None:
        _lancedb_service = LanceDBService()
    return _lancedb_service