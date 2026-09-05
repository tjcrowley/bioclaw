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


class SessionMemory:
    """SQLite-backed dataset-reference/finding store, keyed by session_id.
    Mirrors ingest/store.py::DatasetStore's connection/table pattern."""

    def __init__(self, root: str | Path = "agent/memory.sqlite"):
        self.path = Path(root)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as conn:
            conn.execute(_CREATE_TABLE_SQL)

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self.path)

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
