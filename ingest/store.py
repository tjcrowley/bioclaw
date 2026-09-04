"""Versioned dataset store (INGEST-03).

A filesystem + SQLite registry that saves an AnnData under a name,
auto-incrementing a version each time, and loads it back by name (latest or
a specific version). This is the mechanism later phases (agent, analysis)
use to reference canonical datasets without re-running ingest.

Per 01-RESEARCH.md's build-vs-buy analysis, a hand-rolled filesystem+SQLite
registry is the right-sized solution for a single-developer MVP (vs.
adopting LaminDB now) -- simple, zero new dependencies, trivially testable,
and narrow enough to swap backends later if needed.

Layout:
    {root}/{name}/v{N}.h5ad   -- one .h5ad file per (name, version)
    {root}/registry.sqlite    -- SQLite index of all (name, version) records
"""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

import anndata as ad
from anndata import AnnData

_CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS datasets (
    name TEXT NOT NULL,
    version INTEGER NOT NULL,
    path TEXT NOT NULL,
    created_at TEXT NOT NULL,
    source_path TEXT,
    qc_config TEXT,
    PRIMARY KEY (name, version)
)
"""


class DatasetStore:
    """Filesystem + SQLite-backed versioned store for AnnData datasets."""

    def __init__(self, root: str | Path = "data"):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self.db_path = self.root / "registry.sqlite"
        with self._connect() as conn:
            conn.execute(_CREATE_TABLE_SQL)

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def save(
        self,
        name: str,
        adata: AnnData,
        source_path: str | None = None,
        qc_config: dict | None = None,
    ) -> int:
        """Writes `adata` as the next version for `name` and records it in
        the registry. Returns the new version number."""
        with self._connect() as conn:
            row = conn.execute(
                "SELECT MAX(version) AS max_version FROM datasets WHERE name = ?",
                (name,),
            ).fetchone()
            latest = row["max_version"] if row and row["max_version"] is not None else 0
            version = latest + 1

            dataset_dir = self.root / name
            dataset_dir.mkdir(parents=True, exist_ok=True)
            path = dataset_dir / f"v{version}.h5ad"
            adata.write_h5ad(path)

            created_at = datetime.now(timezone.utc).isoformat()
            qc_config_json = json.dumps(qc_config) if qc_config is not None else None

            conn.execute(
                """
                INSERT INTO datasets
                    (name, version, path, created_at, source_path, qc_config)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (name, version, str(path), created_at, source_path, qc_config_json),
            )
            conn.commit()

        return version

    def load(
        self,
        name: str,
        version: int | None = None,
        backed: str | None = None,
    ) -> AnnData:
        """Loads `name` -- latest version by default, or a specific
        `version`. Raises KeyError if `name` (or that version) doesn't
        exist."""
        with self._connect() as conn:
            if version is None:
                row = conn.execute(
                    """
                    SELECT path FROM datasets
                    WHERE name = ?
                    ORDER BY version DESC
                    LIMIT 1
                    """,
                    (name,),
                ).fetchone()
            else:
                row = conn.execute(
                    "SELECT path FROM datasets WHERE name = ? AND version = ?",
                    (name, version),
                ).fetchone()

        if row is None:
            if version is None:
                raise KeyError(f"No dataset named {name!r} in store at {self.root}")
            raise KeyError(
                f"No dataset named {name!r} at version {version} in store at {self.root}"
            )

        return ad.read_h5ad(row["path"], backed=backed)
