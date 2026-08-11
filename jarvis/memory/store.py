"""SQLite-backed conversation log (Phase 0 memory)."""

from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class MemoryStore:
    """Persist chat turns and (later) semantic facts."""

    def __init__(self, db_path: Path | str) -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_schema(self) -> None:
        conn = self._connect()
        try:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS conversations (
                    id TEXT PRIMARY KEY,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL,
                    role TEXT NOT NULL,
                    content TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY (session_id) REFERENCES conversations(id)
                );

                CREATE INDEX IF NOT EXISTS idx_messages_session
                    ON messages(session_id, id);

                CREATE TABLE IF NOT EXISTS facts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    key TEXT,
                    content TEXT NOT NULL,
                    source_session TEXT,
                    created_at TEXT NOT NULL
                );
                """
            )
            conn.commit()
        finally:
            conn.close()

    def ensure_session(self, session_id: str) -> None:
        now = _utc_now()
        conn = self._connect()
        try:
            row = conn.execute(
                "SELECT id FROM conversations WHERE id = ?", (session_id,)
            ).fetchone()
            if row is None:
                conn.execute(
                    "INSERT INTO conversations (id, created_at, updated_at) VALUES (?, ?, ?)",
                    (session_id, now, now),
                )
            else:
                conn.execute(
                    "UPDATE conversations SET updated_at = ? WHERE id = ?",
                    (now, session_id),
                )
            conn.commit()
        finally:
            conn.close()

    def append_turn(self, session_id: str, role: str, content: str) -> None:
        self.ensure_session(session_id)
        conn = self._connect()
        try:
            conn.execute(
                "INSERT INTO messages (session_id, role, content, created_at) VALUES (?, ?, ?, ?)",
                (session_id, role, content, _utc_now()),
            )
            conn.execute(
                "UPDATE conversations SET updated_at = ? WHERE id = ?",
                (_utc_now(), session_id),
            )
            conn.commit()
        finally:
            conn.close()

    def load_messages(self, session_id: str, *, limit: int = 40) -> list[dict[str, Any]]:
        """Return the last ``limit`` messages as Anthropic-style role/content dicts."""
        conn = self._connect()
        try:
            rows = conn.execute(
                """
                SELECT role, content FROM messages
                WHERE session_id = ?
                ORDER BY id DESC
                LIMIT ?
                """,
                (session_id, limit),
            ).fetchall()
            messages = [{"role": r["role"], "content": r["content"]} for r in reversed(rows)]
            return messages
        finally:
            conn.close()

    def add_fact(self, content: str, *, key: str | None = None, session_id: str | None = None) -> None:
        conn = self._connect()
        try:
            conn.execute(
                "INSERT INTO facts (key, content, source_session, created_at) VALUES (?, ?, ?, ?)",
                (key, content, session_id, _utc_now()),
            )
            conn.commit()
        finally:
            conn.close()
