"""Census-source helpers for Phase 12 (DATA-01, EXPORT-02).

This module is intentionally census-source-agnostic: it does NOT import
`cellxgene_census` and performs no network I/O. It provides:

- `format_census_source()`: builds the provenance string stored in
  DatasetStore.source_path so EXPORT-02 can reconstruct the census query.
- `ingest_from_anndata()`: in-memory equivalent of `ingest_10x()` for a
  pre-built AnnData (the census fetch result that plan 02 materialises).
  Accepts a source_path string that a caller built via `format_census_source()`.

Design rationale (per 12-RESEARCH.md Open Question 2): keeping the already-
materialised census AnnData in memory avoids a write + read round-trip,
matches "call through the pipeline, not around it", and is the right-sized
approach for a single-developer MVP.
"""

from __future__ import annotations

from dataclasses import asdict

from ingest import contract, qc
from ingest.store import DatasetStore


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
