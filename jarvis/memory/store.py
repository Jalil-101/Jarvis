"""SQLite memory: conversations, semantic/episodic facts, people, projects, preferences."""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from jarvis.memory.embeddings import cosine, embed


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class MemoryStore:
    """Persist chat turns and long-term personal knowledge."""

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
                    created_at TEXT NOT NULL,
                    kind TEXT DEFAULT 'semantic',
                    embedding TEXT
                );

                CREATE TABLE IF NOT EXISTS people (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL UNIQUE,
                    relation TEXT,
                    notes TEXT,
                    embedding TEXT,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS projects (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL UNIQUE,
                    path TEXT,
                    stack TEXT,
                    notes TEXT,
                    embedding TEXT,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS preferences (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS episodes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    summary TEXT NOT NULL,
                    occurred_at TEXT NOT NULL,
                    embedding TEXT,
                    created_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS local_mail (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    sender TEXT NOT NULL,
                    subject TEXT NOT NULL,
                    body TEXT NOT NULL,
                    important INTEGER NOT NULL DEFAULT 0,
                    read INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS calendar_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    title TEXT NOT NULL,
                    start TEXT NOT NULL,
                    end TEXT,
                    location TEXT,
                    notes TEXT
                );

                CREATE TABLE IF NOT EXISTS jobs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    cron_expr TEXT,
                    run_at TEXT,
                    action TEXT NOT NULL,
                    payload TEXT,
                    enabled INTEGER NOT NULL DEFAULT 1,
                    last_run TEXT
                );

                CREATE TABLE IF NOT EXISTS event_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    kind TEXT NOT NULL,
                    payload TEXT NOT NULL,
                    importance REAL NOT NULL DEFAULT 0.5,
                    disposition TEXT NOT NULL DEFAULT 'logged',
                    created_at TEXT NOT NULL
                );
                """
            )
            self._ensure_column(conn, "facts", "kind", "TEXT DEFAULT 'semantic'")
            self._ensure_column(conn, "facts", "embedding", "TEXT")
            conn.commit()
        finally:
            conn.close()

    def _ensure_column(self, conn: sqlite3.Connection, table: str, column: str, decl: str) -> None:
        cols = {row[1] for row in conn.execute(f"PRAGMA table_info({table})")}
        if column not in cols:
            conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {decl}")

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
            return [{"role": r["role"], "content": r["content"]} for r in reversed(rows)]
        finally:
            conn.close()

    def add_fact(
        self,
        content: str,
        *,
        key: str | None = None,
        session_id: str | None = None,
        kind: str = "semantic",
    ) -> int:
        conn = self._connect()
        try:
            cur = conn.execute(
                """
                INSERT INTO facts (key, content, source_session, created_at, kind, embedding)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    key,
                    content,
                    session_id,
                    _utc_now(),
                    kind,
                    json.dumps(embed(content)),
                ),
            )
            conn.commit()
            return int(cur.lastrowid)
        finally:
            conn.close()

    def add_semantic(self, content: str, *, key: str | None = None, session_id: str | None = None) -> int:
        return self.add_fact(content, key=key, session_id=session_id, kind="semantic")

    def add_episode(self, summary: str, *, occurred_at: str | None = None) -> int:
        conn = self._connect()
        try:
            when = occurred_at or _utc_now()
            cur = conn.execute(
                """
                INSERT INTO episodes (summary, occurred_at, embedding, created_at)
                VALUES (?, ?, ?, ?)
                """,
                (summary, when, json.dumps(embed(summary)), _utc_now()),
            )
            conn.commit()
            return int(cur.lastrowid)
        finally:
            conn.close()

    def upsert_person(self, name: str, *, relation: str = "", notes: str = "") -> None:
        now = _utc_now()
        blob = json.dumps(embed(f"{name} {relation} {notes}"))
        conn = self._connect()
        try:
            conn.execute(
                """
                INSERT INTO people (name, relation, notes, embedding, updated_at)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(name) DO UPDATE SET
                    relation = excluded.relation,
                    notes = excluded.notes,
                    embedding = excluded.embedding,
                    updated_at = excluded.updated_at
                """,
                (name.strip(), relation, notes, blob, now),
            )
            conn.commit()
        finally:
            conn.close()

    def upsert_project(
        self,
        name: str,
        *,
        path: str = "",
        stack: str = "",
        notes: str = "",
    ) -> None:
        now = _utc_now()
        blob = json.dumps(embed(f"{name} {stack} {notes}"))
        conn = self._connect()
        try:
            conn.execute(
                """
                INSERT INTO projects (name, path, stack, notes, embedding, updated_at)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(name) DO UPDATE SET
                    path = excluded.path,
                    stack = excluded.stack,
                    notes = excluded.notes,
                    embedding = excluded.embedding,
                    updated_at = excluded.updated_at
                """,
                (name.strip(), path, stack, notes, blob, now),
            )
            conn.commit()
        finally:
            conn.close()

    def set_preference(self, key: str, value: str) -> None:
        conn = self._connect()
        try:
            conn.execute(
                """
                INSERT INTO preferences (key, value, updated_at) VALUES (?, ?, ?)
                ON CONFLICT(key) DO UPDATE SET value = excluded.value, updated_at = excluded.updated_at
                """,
                (key.strip(), value, _utc_now()),
            )
            conn.commit()
        finally:
            conn.close()

    def list_preferences(self) -> list[dict[str, str]]:
        conn = self._connect()
        try:
            rows = conn.execute("SELECT key, value FROM preferences ORDER BY key").fetchall()
            return [{"key": r["key"], "value": r["value"]} for r in rows]
        finally:
            conn.close()

    def get_person(self, name: str) -> dict[str, Any] | None:
        conn = self._connect()
        try:
            row = conn.execute(
                "SELECT name, relation, notes, updated_at FROM people WHERE name LIKE ?",
                (name,),
            ).fetchone()
            return dict(row) if row else None
        finally:
            conn.close()

    def forget(self, *, kind: str, query: str) -> int:
        """Delete matching memory rows. kind: fact|person|project|preference|episode."""
        conn = self._connect()
        try:
            deleted = 0
            if kind == "fact":
                cur = conn.execute(
                    "DELETE FROM facts WHERE content LIKE ? OR IFNULL(key,'') LIKE ?",
                    (f"%{query}%", f"%{query}%"),
                )
                deleted = cur.rowcount
            elif kind == "person":
                cur = conn.execute("DELETE FROM people WHERE name LIKE ?", (f"%{query}%",))
                deleted = cur.rowcount
            elif kind == "project":
                cur = conn.execute("DELETE FROM projects WHERE name LIKE ?", (f"%{query}%",))
                deleted = cur.rowcount
            elif kind == "preference":
                cur = conn.execute("DELETE FROM preferences WHERE key LIKE ?", (f"%{query}%",))
                deleted = cur.rowcount
            elif kind == "episode":
                cur = conn.execute("DELETE FROM episodes WHERE summary LIKE ?", (f"%{query}%",))
                deleted = cur.rowcount
            else:
                raise ValueError(f"Unknown kind: {kind}")
            conn.commit()
            return int(deleted)
        finally:
            conn.close()

    def export_all(self) -> dict[str, Any]:
        conn = self._connect()
        try:
            def dump(sql: str) -> list[dict[str, Any]]:
                return [dict(r) for r in conn.execute(sql).fetchall()]

            return {
                "exported_at": _utc_now(),
                "facts": dump("SELECT id, key, kind, content, created_at FROM facts"),
                "people": dump("SELECT name, relation, notes, updated_at FROM people"),
                "projects": dump("SELECT name, path, stack, notes, updated_at FROM projects"),
                "preferences": dump("SELECT key, value, updated_at FROM preferences"),
                "episodes": dump("SELECT id, summary, occurred_at FROM episodes"),
            }
        finally:
            conn.close()

    def recall(self, query: str, *, limit: int = 8) -> str:
        """Return a short markdown brief of the most relevant memories."""
        qvec = embed(query)
        scored: list[tuple[float, str]] = []

        conn = self._connect()
        try:
            for row in conn.execute("SELECT kind, content, embedding FROM facts"):
                score = _score(qvec, row["embedding"], query, row["content"])
                scored.append((score, f"- [{row['kind']}] {row['content']}"))
            for row in conn.execute("SELECT name, relation, notes, embedding FROM people"):
                text = f"{row['name']} ({row['relation'] or 'person'}): {row['notes'] or ''}"
                score = _score(qvec, row["embedding"], query, text) + (
                    0.25 if query.lower() in (row["name"] or "").lower() else 0
                )
                scored.append((score, f"- [person] {text.strip()}"))
            for row in conn.execute("SELECT name, path, stack, notes, embedding FROM projects"):
                text = f"{row['name']} @ {row['path'] or '?'} | {row['stack'] or ''} | {row['notes'] or ''}"
                score = _score(qvec, row["embedding"], query, text)
                scored.append((score, f"- [project] {text.strip()}"))
            for row in conn.execute("SELECT summary, occurred_at, embedding FROM episodes"):
                text = f"{row['occurred_at']}: {row['summary']}"
                score = _score(qvec, row["embedding"], query, text)
                scored.append((score, f"- [episode] {text}"))
            for row in conn.execute("SELECT key, value FROM preferences"):
                text = f"{row['key']} = {row['value']}"
                score = 0.4 if any(w in text.lower() for w in query.lower().split()) else 0.05
                scored.append((score, f"- [preference] {text}"))
        finally:
            conn.close()

        scored.sort(key=lambda x: x[0], reverse=True)
        top = [line for score, line in scored if score >= 0.12][:limit]
        return "\n".join(top)

    def add_mail(self, sender: str, subject: str, body: str, *, important: bool = False) -> int:
        conn = self._connect()
        try:
            cur = conn.execute(
                """
                INSERT INTO local_mail (sender, subject, body, important, read, created_at)
                VALUES (?, ?, ?, ?, 0, ?)
                """,
                (sender, subject, body, int(important), _utc_now()),
            )
            conn.commit()
            return int(cur.lastrowid)
        finally:
            conn.close()

    def list_mail(self, *, unread_only: bool = False, limit: int = 20) -> list[dict[str, Any]]:
        conn = self._connect()
        try:
            sql = "SELECT id, sender, subject, important, read, created_at FROM local_mail"
            if unread_only:
                sql += " WHERE read = 0"
            sql += " ORDER BY id DESC LIMIT ?"
            return [dict(r) for r in conn.execute(sql, (limit,)).fetchall()]
        finally:
            conn.close()

    def get_mail(self, mail_id: int) -> dict[str, Any] | None:
        conn = self._connect()
        try:
            row = conn.execute("SELECT * FROM local_mail WHERE id = ?", (mail_id,)).fetchone()
            if not row:
                return None
            conn.execute("UPDATE local_mail SET read = 1 WHERE id = ?", (mail_id,))
            conn.commit()
            return dict(row)
        finally:
            conn.close()

    def add_calendar_event(
        self,
        title: str,
        start: str,
        *,
        end: str | None = None,
        location: str = "",
        notes: str = "",
    ) -> int:
        conn = self._connect()
        try:
            cur = conn.execute(
                """
                INSERT INTO calendar_events (title, start, end, location, notes)
                VALUES (?, ?, ?, ?, ?)
                """,
                (title, start, end, location, notes),
            )
            conn.commit()
            return int(cur.lastrowid)
        finally:
            conn.close()

    def list_calendar(self, *, limit: int = 20) -> list[dict[str, Any]]:
        conn = self._connect()
        try:
            return [
                dict(r)
                for r in conn.execute(
                    "SELECT * FROM calendar_events ORDER BY start LIMIT ?",
                    (limit,),
                ).fetchall()
            ]
        finally:
            conn.close()

    def add_job(self, name: str, action: str, *, cron_expr: str | None = None, run_at: str | None = None, payload: str = "") -> int:
        conn = self._connect()
        try:
            cur = conn.execute(
                """
                INSERT INTO jobs (name, cron_expr, run_at, action, payload, enabled)
                VALUES (?, ?, ?, ?, ?, 1)
                """,
                (name, cron_expr, run_at, action, payload),
            )
            conn.commit()
            return int(cur.lastrowid)
        finally:
            conn.close()

    def list_jobs(self) -> list[dict[str, Any]]:
        conn = self._connect()
        try:
            return [dict(r) for r in conn.execute("SELECT * FROM jobs ORDER BY id").fetchall()]
        finally:
            conn.close()

    def log_event(self, kind: str, payload: dict[str, Any], *, importance: float = 0.5, disposition: str = "logged") -> int:
        conn = self._connect()
        try:
            cur = conn.execute(
                """
                INSERT INTO event_log (kind, payload, importance, disposition, created_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (kind, json.dumps(payload), importance, disposition, _utc_now()),
            )
            conn.commit()
            return int(cur.lastrowid)
        finally:
            conn.close()

    def recent_events(self, *, limit: int = 20) -> list[dict[str, Any]]:
        conn = self._connect()
        try:
            return [
                dict(r)
                for r in conn.execute(
                    "SELECT * FROM event_log ORDER BY id DESC LIMIT ?",
                    (limit,),
                ).fetchall()
            ]
        finally:
            conn.close()

    def count_recent_dispositions(self, disposition: str, *, since_iso: str) -> int:
        conn = self._connect()
        try:
            row = conn.execute(
                "SELECT COUNT(*) AS n FROM event_log WHERE disposition = ? AND created_at >= ?",
                (disposition, since_iso),
            ).fetchone()
            return int(row["n"] if row else 0)
        finally:
            conn.close()


def _score(query_vec: list[float], embedding_json: str | None, query: str, text: str) -> float:
    vec_score = 0.0
    if embedding_json:
        try:
            vec_score = cosine(query_vec, json.loads(embedding_json))
        except (json.JSONDecodeError, TypeError, ValueError):
            vec_score = 0.0
    q = query.lower()
    t = (text or "").lower()
    overlap = 0.0
    words = [w for w in q.split() if len(w) > 2]
    if words:
        hits = sum(1 for w in words if w in t)
        overlap = hits / len(words)
    return (0.7 * vec_score) + (0.3 * overlap)
