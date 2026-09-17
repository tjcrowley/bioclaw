"""Census-source helpers for Phase 12 (DATA-01, EXPORT-02).

This module provides:

- `format_census_source()`: builds the provenance string stored in
  DatasetStore.source_path so EXPORT-02 can reconstruct the census query.
  Pure string function — no network I/O, no cellxgene_census import.
- `ingest_from_anndata()`: in-memory equivalent of `ingest_10x()` for a
  pre-built AnnData (the census fetch result that plan 02 materialises).
  Accepts a source_path string that a caller built via `format_census_source()`.
- `_census_fetch_blocking()`: synchronous closure that opens the cellxgene
  census and calls get_anndata; designed to run inside asyncio.to_thread()
  so TileDB-SOMA's synchronous network I/O never blocks the event loop.
- `fetch_census_dataset()`: async orchestration layer that offloads the
  blocking census fetch via asyncio.to_thread, guards against oversize
  results, and hands the AnnData to ingest_from_anndata.

Design rationale (per 12-RESEARCH.md Open Question 2): keeping the already-
materialised census AnnData in memory avoids a write + read round-trip,
matches "call through the pipeline, not around it", and is the right-sized
approach for a single-developer MVP.

Per RESEARCH Pattern 2 / Pitfall 1: the cellxgene_census context manager
(open_soma) and get_anndata must both run in the SAME thread — hence the
entire with-block lives inside _census_fetch_blocking(), which is passed
wholesale to asyncio.to_thread(). Never open the census outside the thread
and pass the handle in.

Per RESEARCH Pitfall 2: obs_coords (e.g. slice(0, N) on soma_joinid) is
unreliable for cell-count limiting; instead we limit via max_cells check
after the fetch and raise a descriptive error asking the user to tighten
the obs_value_filter.
"""

from __future__ import annotations

import asyncio
from dataclasses import asdict
from typing import Sequence

import anndata
import cellxgene_census

from ingest import contract, qc
from ingest.store import DatasetStore

# Obs columns fetched from the census for every query.  These cover all
# common downstream QC / annotation use-cases without pulling the full
# metadata table.
_CENSUS_OBS_COLUMNS: list[str] = [
    "tissue",
    "tissue_general",
    "assay",
    "cell_type",
    "disease",
    "is_primary_data",
    "sex",
    "suspension_type",
]

_MAX_CELLS_DEFAULT: int = 50_000


def format_census_source(
    census_version: str,
    organism: str,
    obs_value_filter: str,
) -> str:
    """Return the colon-delimited provenance string stored in
    DatasetStore.source_path so EXPORT-02 can reconstruct the census query.

    Format: ``cellxgene-census:{census_version}:{organism}:{obs_value_filter}``

    This is a pure string function — no I/O, no network access.

    Example::

        format_census_source(
            "stable",
            "Homo sapiens",
            "tissue_general == 'lung'",
        )
        # -> "cellxgene-census:stable:Homo sapiens:tissue_general == 'lung'"
    """
    return f"cellxgene-census:{census_version}:{organism}:{obs_value_filter}"


def ingest_from_anndata(
    adata,
    name: str,
    source_path: str,
    qc_config: qc.QCConfig | None = None,
    store_root: str = "data",
) -> str:
    """In-memory equivalent of ``ingest_10x()`` for a PRE-BUILT AnnData.

    Runs the same pipeline as ``ingest_10x()`` but skips ``loaders.load()``
    because the AnnData is already in memory (e.g. materialised by the census
    fetch that plan 02 performs):

    1. ``contract.set_counts_layer(adata)``  — freeze raw counts before QC
    2. ``qc.run(adata, qc_config)``           — QC-01 + QC-02
    3. ``contract.set_counts_layer(adata)``  — re-freeze against filtered shape
    4. ``store.save(name, adata, source_path=source_path, qc_config=...)``

    Returns ``"{name}@{version}"``.

    Parameters
    ----------
    adata:
        Pre-built AnnData with raw integer counts in ``.X``.
    name:
        Dataset name to store under (same semantics as ``ingest_10x``).
    source_path:
        Provenance string, typically built via ``format_census_source()``.
        Stored verbatim in DatasetStore so EXPORT-02 can read it back.
    qc_config:
        QC thresholds; defaults to ``QCConfig()`` if ``None``.
    store_root:
        Root directory for the DatasetStore.
    """
    contract.set_counts_layer(adata)  # INGEST-02, before anything else touches .X

    qc_config = qc_config or qc.QCConfig()
    adata = qc.run(adata, qc_config)  # QC-01 + QC-02

    # Re-freeze against the final, filtered shape (mirrors ingest_10x rationale).
    contract.set_counts_layer(adata)

    store = DatasetStore(root=store_root)
    version = store.save(
        name, adata, source_path=source_path, qc_config=asdict(qc_config)
    )

    return f"{name}@{version}"


# ─── Census fetch (DATA-01) ───────────────────────────────────────────────────


def _census_fetch_blocking(
    organism: str,
    obs_value_filter: str,
    obs_column_names: Sequence[str],
    census_version: str = "stable",
) -> anndata.AnnData:
    """Synchronous census fetch — intended to run inside asyncio.to_thread().

    The ENTIRE ``with cellxgene_census.open_soma(...) as census:`` block and
    the ``cellxgene_census.get_anndata(...)`` call are inside this function so
    that both run in the same worker thread (RESEARCH Pattern 2 / Pitfall 1).

    Parameters
    ----------
    organism:
        E.g. ``"Homo sapiens"`` or ``"Mus musculus"``.
    obs_value_filter:
        TileDB-SOMA filter expression, e.g.
        ``"tissue_general == 'lung' and is_primary_data == True"``.
    obs_column_names:
        Obs metadata columns to include (typically ``_CENSUS_OBS_COLUMNS``).
    census_version:
        Census snapshot version; ``"stable"`` (default) uses the current
        LTS release.

    Returns
    -------
    anndata.AnnData
        The fetched dataset with raw integer counts in ``.X``.
    """
    with cellxgene_census.open_soma(census_version=census_version) as census:
        adata = cellxgene_census.get_anndata(
            census=census,
            organism=organism,
            obs_value_filter=obs_value_filter,
            obs_column_names=list(obs_column_names),
        )
    return adata


async def fetch_census_dataset(
    organism: str,
    obs_value_filter: str,
    name: str,
    census_version: str = "stable",
    max_cells: int = _MAX_CELLS_DEFAULT,
    store_root: str = "data",
) -> str:
    """Fetch a public single-cell dataset from cellxgene-census and ingest it.

    Offloads the blocking TileDB-SOMA I/O to a worker thread via
    ``asyncio.to_thread()`` so the event loop is never stalled.

    Parameters
    ----------
    organism:
        ``"Homo sapiens"`` or ``"Mus musculus"``.
    obs_value_filter:
        TileDB-SOMA filter expression; **must** include
        ``is_primary_data == True`` and a specific tissue to keep the result
        small (e.g. ``"tissue_general == 'lung' and is_primary_data == True"``).
    name:
        Dataset name to store under (same semantics as ``ingest_10x``).
    census_version:
        Census snapshot version; defaults to ``"stable"``.
    max_cells:
        Hard ceiling on ``n_obs``; raises ``ValueError`` if exceeded, asking
        the caller to tighten the filter.
    store_root:
        Root directory for the DatasetStore.

    Returns
    -------
    str
        ``"{name}@{version}"`` handle — identical format to ``ingest_10x``.

    Raises
    ------
    ValueError
        If the fetched AnnData exceeds ``max_cells`` rows.
    """
    adata: anndata.AnnData = await asyncio.to_thread(
        _census_fetch_blocking,
        organism,
        obs_value_filter,
        _CENSUS_OBS_COLUMNS,
        census_version,
    )

    if adata.n_obs > max_cells:
        raise ValueError(
            f"Census query returned {adata.n_obs:,} cells, which exceeds the "
            f"{max_cells:,}-cell limit. Tighten obs_value_filter — add "
            f"'is_primary_data == True' and a specific tissue "
            f"(e.g. \"tissue_general == 'lung'\") to reduce the result set."
        )

    source = format_census_source(census_version, organism, obs_value_filter)
    return ingest_from_anndata(adata, name, source_path=source, store_root=store_root)
