"""Session-scoped dataset-reference/finding memory (AGENT-03).

A small SQLite-backed store recording `(session_id, dataset_id, note,
created_at)` rows -- an explicit, versioned pointer to "which dataset are
we discussing" layered on top of (not replacing) the SDK's own transcript
retention.

Per 03-RESEARCH.md Pattern 3 and this repo's own PITFALLS.md Performance
Traps finding, relying solely on the SDK's automatic transcript retention
breaks the moment context compaction summarizes older turns or a second
processing run of the same source data exists. Mirrors
ingest/store.py::DatasetStore's already-proven connection/table pattern.
"""

from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path

_CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS session_memory (
    session_id TEXT NOT NULL,
    dataset_id TEXT NOT NULL,
    note TEXT,
    created_at TEXT NOT NULL
)
"""

_CREATE_SESSIONS_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS sessions (
    session_id TEXT PRIMARY KEY,
    created_at TEXT NOT NULL,
    last_active_at TEXT NOT NULL
)
"""

_CREATE_MESSAGES_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS messages (
    session_id TEXT NOT NULL,
    role TEXT NOT NULL,
    content TEXT NOT NULL,
    created_at TEXT NOT NULL
)
"""

_CONTENT_CAP = 64 * 1024  # character cap (Python string length, not bytes)


class SessionMemory:
    """SQLite-backed dataset-reference/finding store, keyed by session_id.
    Mirrors ingest/store.py::DatasetStore's connection/table pattern."""

    def __init__(self, root: str | Path = "agent/memory.sqlite"):
        self.path = Path(root)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as conn:
            conn.execute(_CREATE_TABLE_SQL)
            conn.execute(_CREATE_SESSIONS_TABLE_SQL)
            conn.execute(_CREATE_MESSAGES_TABLE_SQL)

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.path)
        conn.execute("PRAGMA journal_mode=WAL")
        return conn

    def record(self, session_id: str, dataset_id: str, note: str | None = None) -> None:
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO session_memory VALUES (?, ?, ?, ?)",
                (session_id, dataset_id, note, datetime.now(timezone.utc).isoformat()),
            )
            conn.commit()

    def recent_datasets(self, session_id: str, limit: int = 5) -> list[str]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT dataset_id FROM session_memory WHERE session_id = ? "
                "ORDER BY created_at DESC, rowid DESC LIMIT ?",
                (session_id, limit),
            ).fetchall()
        return [r[0] for r in rows]

    def touch(self, session_id: str) -> None:
        """Marks `session_id` as started/active, making it listable via
        `list_sessions()` even if no dataset-producing tool call ever
        happens in this session (API-03). Idempotent: a second call on the
        same `session_id` upserts `last_active_at` without creating a
        duplicate row."""
        now = datetime.now(timezone.utc).isoformat()
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO sessions (session_id, created_at, last_active_at) "
                "VALUES (?, ?, ?) "
                "ON CONFLICT(session_id) DO UPDATE SET last_active_at = excluded.last_active_at",
                (session_id, now, now),
            )
            conn.commit()

    def list_sessions(self, limit: int = 50) -> list[dict]:
        """Returns every touched session, most-recently-active first, each
        entry including `session_id`, `created_at`, `last_active_at`, and
        `recent_datasets` (via `recent_datasets()`)."""
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT session_id, created_at, last_active_at FROM sessions "
                "ORDER BY last_active_at DESC, rowid DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [
            {
                "session_id": r[0],
                "created_at": r[1],
                "last_active_at": r[2],
                "recent_datasets": self.recent_datasets(r[0]),
            }
            for r in rows
        ]

    def session_exists(self, session_id: str) -> bool:
        """True only after `touch()` (or any write to the `sessions`
        table) has been called for `session_id`, False otherwise."""
        with self._connect() as conn:
            row = conn.execute(
                "SELECT 1 FROM sessions WHERE session_id = ?", (session_id,)
            ).fetchone()
        return row is not None

    def add_message(self, session_id: str, role: str, content: str) -> None:
        """Stores one message turn. Content capped at 64 KB (character count)
        to prevent database blowup (HIST-01 success criteria)."""
        capped = content[:_CONTENT_CAP]
        now = datetime.now(timezone.utc).isoformat()
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO messages (session_id, role, content, created_at) VALUES (?, ?, ?, ?)",
                (session_id, role, capped, now),
            )
            conn.commit()

    def get_messages(self, session_id: str) -> list[dict]:
        """Returns all messages for session_id, oldest first (rowid order)."""
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT role, content, created_at FROM messages "
                "WHERE session_id = ? ORDER BY rowid ASC",
                (session_id,),
            ).fetchall()
        return [{"role": r[0], "content": r[1], "created_at": r[2]} for r in rows]
