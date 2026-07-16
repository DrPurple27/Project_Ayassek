from __future__ import annotations

import json
import sqlite3
import threading
import time
import uuid
from pathlib import Path
from typing import Any

from ayassek.config.settings import settings


class GraphDB:
    def __init__(self, db_path: str | None = None):
        self._path = db_path or settings.memory.neural.db_path
        Path(self._path).parent.mkdir(parents=True, exist_ok=True)
        self._local = threading.local()
        self._init_db()

    def _get_conn(self) -> sqlite3.Connection:
        if not hasattr(self._local, "conn") or self._local.conn is None:
            self._local.conn = sqlite3.connect(self._path, timeout=30)
            self._local.conn.execute("PRAGMA journal_mode=WAL")
            self._local.conn.execute("PRAGMA foreign_keys=ON")
            self._local.conn.row_factory = sqlite3.Row
        return self._local.conn

    def _init_db(self):
        conn = self._get_conn()
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS sessions (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                summary TEXT DEFAULT '',
                created_at REAL NOT NULL,
                updated_at REAL NOT NULL
            );
            CREATE TABLE IF NOT EXISTS chat_messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                created_at REAL NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_messages_session ON chat_messages(session_id, created_at);
            CREATE TABLE IF NOT EXISTS kv_store (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL,
                updated_at REAL NOT NULL
            );
            CREATE TABLE IF NOT EXISTS nodes (
                id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                content TEXT NOT NULL DEFAULT '',
                x_position REAL NOT NULL DEFAULT 0,
                y_position REAL NOT NULL DEFAULT 0,
                created_at REAL NOT NULL,
                updated_at REAL NOT NULL
            );
            CREATE TABLE IF NOT EXISTS edges (
                id TEXT PRIMARY KEY,
                source_node_id TEXT NOT NULL REFERENCES nodes(id) ON DELETE CASCADE,
                target_node_id TEXT NOT NULL REFERENCES nodes(id) ON DELETE CASCADE,
                strength REAL NOT NULL DEFAULT 1.0,
                is_manual INTEGER NOT NULL DEFAULT 0,
                created_at REAL NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_edges_source ON edges(source_node_id);
            CREATE INDEX IF NOT EXISTS idx_edges_target ON edges(target_node_id);
        """)
        conn.commit()
        self._run_migrations(conn)

    def _run_migrations(self, conn: sqlite3.Connection):
        migrations = conn.execute(
            "SELECT key FROM kv_store WHERE key LIKE 'migration_%'"
        ).fetchall()
        applied = {r["key"] for r in migrations}

        if "migration_edges_unique" not in applied:
            conn.execute("""
                DELETE FROM edges WHERE id NOT IN (
                    SELECT MIN(id) FROM edges GROUP BY source_node_id, target_node_id
                )
            """)
            conn.execute("""
                CREATE UNIQUE INDEX IF NOT EXISTS idx_edges_unique
                ON edges(source_node_id, target_node_id)
            """)
            conn.execute(
                "INSERT OR REPLACE INTO kv_store (key, value, updated_at) VALUES (?, ?, ?)",
                ("migration_edges_unique", "1", time.time()),
            )
            conn.commit()

        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_nodes_title_lower ON nodes(title)
        """)
        conn.commit()

    # ─── Sessions ────────────────────────

    def create_session(self, session_id: str, name: str) -> dict:
        now = time.time()
        conn = self._get_conn()
        conn.execute(
            "INSERT OR IGNORE INTO sessions (id, name, summary, created_at, updated_at) VALUES (?, ?, '', ?, ?)",
            (session_id, name, now, now),
        )
        conn.commit()
        return {"id": session_id, "name": name, "summary": "", "created_at": now, "updated_at": now}

    def get_sessions(self) -> list[dict]:
        conn = self._get_conn()
        rows = conn.execute("SELECT id, name, summary, created_at, updated_at FROM sessions ORDER BY updated_at DESC").fetchall()
        return [dict(r) for r in rows]

    def get_session(self, session_id: str) -> dict | None:
        conn = self._get_conn()
        row = conn.execute("SELECT id, name, summary, created_at, updated_at FROM sessions WHERE id=?", (session_id,)).fetchone()
        return dict(row) if row else None

    def delete_session(self, session_id: str) -> bool:
        conn = self._get_conn()
        conn.execute("DELETE FROM chat_messages WHERE session_id=?", (session_id,))
        conn.execute("DELETE FROM sessions WHERE id=?", (session_id,))
        conn.commit()
        return True

    def update_session_name(self, session_id: str, name: str) -> bool:
        conn = self._get_conn()
        conn.execute("UPDATE sessions SET name=?, updated_at=? WHERE id=?", (name, time.time(), session_id))
        conn.commit()
        return True

    def update_session_summary(self, session_id: str, summary: str) -> bool:
        conn = self._get_conn()
        conn.execute("UPDATE sessions SET summary=?, updated_at=? WHERE id=?", (summary, time.time(), session_id))
        conn.commit()
        return True

    def get_session_count(self) -> int:
        conn = self._get_conn()
        row = conn.execute("SELECT COUNT(*) as c FROM sessions").fetchone()
        return row["c"] if row else 0

    def get_total_message_count(self) -> int:
        conn = self._get_conn()
        row = conn.execute("SELECT COUNT(*) as c FROM chat_messages").fetchone()
        return row["c"] if row else 0

    # ─── Chat Messages ───────────────────

    def add_chat_message(self, session_id: str, role: str, content: str) -> dict:
        conn = self._get_conn()
        now = time.time()
        conn.execute(
            "INSERT OR IGNORE INTO sessions (id, name, summary, created_at, updated_at) VALUES (?, ?, '', ?, ?)",
            (session_id, session_id, now, now),
        )
        conn.execute(
            "INSERT INTO chat_messages (session_id, role, content, created_at) VALUES (?, ?, ?, ?)",
            (session_id, role, content, now),
        )
        conn.execute("UPDATE sessions SET updated_at=? WHERE id=?", (now, session_id))
        conn.commit()
        return {"session_id": session_id, "role": role, "content": content, "created_at": now}

    def get_chat_messages(self, session_id: str, limit: int = 50) -> list[dict]:
        conn = self._get_conn()
        rows = conn.execute(
            "SELECT id, session_id, role, content, created_at FROM chat_messages WHERE session_id=? ORDER BY created_at ASC",
            (session_id,),
        ).fetchall()
        result = [dict(r) for r in rows]
        if limit and len(result) > limit:
            result = result[-limit:]
        return result

    def clear_chat_messages(self, session_id: str) -> bool:
        conn = self._get_conn()
        conn.execute("DELETE FROM chat_messages WHERE session_id=?", (session_id,))
        conn.commit()
        return True

    # ─── KV Store ────────────────────────

    def store_kv(self, key: str, value: str):
        conn = self._get_conn()
        conn.execute(
            "INSERT OR REPLACE INTO kv_store (key, value, updated_at) VALUES (?, ?, ?)",
            (key, value, time.time()),
        )
        conn.commit()

    def recall_kv(self, key: str) -> str | None:
        conn = self._get_conn()
        row = conn.execute("SELECT value FROM kv_store WHERE key=?", (key,)).fetchone()
        return row["value"] if row else None

    def get_all_kv(self) -> dict[str, str]:
        conn = self._get_conn()
        rows = conn.execute("SELECT key, value FROM kv_store").fetchall()
        return {r["key"]: r["value"] for r in rows}

    def clear_kv(self):
        conn = self._get_conn()
        conn.execute("DELETE FROM kv_store")
        conn.commit()

    # ─── Nodes ───────────────────────────

    def create_node(self, title: str, content: str, x: float = 0, y: float = 0) -> dict:
        now = time.time()
        node_id = uuid.uuid4().hex[:12]
        conn = self._get_conn()
        conn.execute(
            "INSERT INTO nodes (id, title, content, x_position, y_position, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (node_id, title, content, x, y, now, now),
        )
        conn.commit()
        return {"id": node_id, "title": title, "content": content, "x": x, "y": y, "created_at": now, "updated_at": now}

    def get_all_nodes(self) -> list[dict]:
        conn = self._get_conn()
        rows = conn.execute("SELECT id, title, content, x_position, y_position, created_at, updated_at FROM nodes ORDER BY created_at ASC").fetchall()
        result = []
        for r in rows:
            d = dict(r)
            d["x"] = d.pop("x_position")
            d["y"] = d.pop("y_position")
            result.append(d)
        return result

    def get_node(self, node_id: str) -> dict | None:
        conn = self._get_conn()
        row = conn.execute("SELECT id, title, content, x_position, y_position, created_at, updated_at FROM nodes WHERE id=?", (node_id,)).fetchone()
        if not row:
            return None
        d = dict(row)
        d["x"] = d.pop("x_position")
        d["y"] = d.pop("y_position")
        return d

    def update_node(self, node_id: str, **fields) -> dict | None:
        allowed = {"title": "title", "content": "content", "x": "x_position", "y": "y_position"}
        updates = []
        values = []
        for k, v in fields.items():
            col = allowed.get(k)
            if col:
                updates.append(f"{col}=?")
                values.append(v)
        if not updates:
            return self.get_node(node_id)
        values.append(time.time())
        values.append(node_id)
        conn = self._get_conn()
        conn.execute(f"UPDATE nodes SET {', '.join(updates)}, updated_at=? WHERE id=?", values)
        conn.commit()
        return self.get_node(node_id)

    def delete_node(self, node_id: str) -> bool:
        conn = self._get_conn()
        conn.execute("DELETE FROM edges WHERE source_node_id=? OR target_node_id=?", (node_id, node_id))
        conn.execute("DELETE FROM nodes WHERE id=?", (node_id,))
        conn.commit()
        return True

    def delete_all_nodes(self) -> int:
        conn = self._get_conn()
        count = conn.execute("SELECT COUNT(*) FROM nodes").fetchone()[0]
        conn.execute("DELETE FROM edges")
        conn.execute("DELETE FROM nodes")
        conn.commit()
        conn.isolation_level = None
        conn.execute("VACUUM")
        conn.isolation_level = ""
        return count

    def clear_all_sessions_and_messages(self) -> dict:
        """Wipe ALL sessions, chat_messages, and kv_store — full chat history reset."""
        conn = self._get_conn()
        msg_count = conn.execute("SELECT COUNT(*) FROM chat_messages").fetchone()[0]
        sess_count = conn.execute("SELECT COUNT(*) FROM sessions").fetchone()[0]
        kv_count = conn.execute("SELECT COUNT(*) FROM kv_store WHERE key NOT LIKE 'migration_%'").fetchone()[0]
        conn.execute("DELETE FROM chat_messages")
        conn.execute("DELETE FROM sessions")
        conn.execute("DELETE FROM kv_store WHERE key NOT LIKE 'migration_%'")
        conn.commit()
        # VACUUM must run outside any transaction
        conn.isolation_level = None
        conn.execute("VACUUM")
        conn.isolation_level = ""
        return {"messages_deleted": msg_count, "sessions_deleted": sess_count, "kv_deleted": kv_count}

    # ─── Edges ────────────────────────────

    def create_edge(self, source_id: str, target_id: str, strength: float = 1.0, is_manual: bool = False) -> dict:
        now = time.time()
        conn = self._get_conn()
        existing = conn.execute(
            "SELECT id, strength, is_manual, created_at FROM edges WHERE source_node_id=? AND target_node_id=?",
            (source_id, target_id),
        ).fetchone()
        if existing:
            return {
                "id": existing["id"],
                "source_node_id": source_id,
                "target_node_id": target_id,
                "strength": existing["strength"],
                "is_manual": bool(existing["is_manual"]),
                "created_at": existing["created_at"],
            }
        edge_id = uuid.uuid4().hex[:12]
        conn.execute(
            "INSERT OR IGNORE INTO edges (id, source_node_id, target_node_id, strength, is_manual, created_at) VALUES (?, ?, ?, ?, ?, ?)",
            (edge_id, source_id, target_id, strength, 1 if is_manual else 0, now),
        )
        conn.commit()
        row = conn.execute("SELECT id, strength, is_manual, created_at FROM edges WHERE source_node_id=? AND target_node_id=?", (source_id, target_id)).fetchone()
        return {
            "id": row["id"] if row else edge_id,
            "source_node_id": source_id,
            "target_node_id": target_id,
            "strength": row["strength"] if row else strength,
            "is_manual": bool(row["is_manual"]) if row else is_manual,
            "created_at": row["created_at"] if row else now,
        }

    def get_all_edges(self) -> list[dict]:
        conn = self._get_conn()
        rows = conn.execute("SELECT id, source_node_id, target_node_id, strength, is_manual, created_at FROM edges ORDER BY created_at ASC").fetchall()
        result = []
        for r in rows:
            d = dict(r)
            d["is_manual"] = bool(d["is_manual"])
            result.append(d)
        return result

    def get_edges_for_node(self, node_id: str) -> list[dict]:
        conn = self._get_conn()
        rows = conn.execute(
            "SELECT id, source_node_id, target_node_id, strength, is_manual, created_at FROM edges WHERE source_node_id=? OR target_node_id=? ORDER BY created_at ASC",
            (node_id, node_id),
        ).fetchall()
        return [dict(r) for r in rows]

    def delete_edge(self, edge_id: str) -> bool:
        conn = self._get_conn()
        conn.execute("DELETE FROM edges WHERE id=?", (edge_id,))
        conn.commit()
        return True

    def ensure_default_session(self):
        conn = self._get_conn()
        row = conn.execute("SELECT COUNT(*) as c FROM sessions").fetchone()
        if row and row["c"] == 0:
            self.create_session("default", "Default")

    def close(self):
        if hasattr(self._local, "conn") and self._local.conn:
            self._local.conn.close()
            self._local.conn = None