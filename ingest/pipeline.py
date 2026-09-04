"""Single coarse-grained Phase 1 entrypoint (INGEST-01/02/03, QC-01/02).

Wires ingest/loaders.py -> ingest/contract.py -> ingest/qc.py ->
ingest/store.py into one call: point at a 10x `.mtx` directory or `.h5`
file, get back a versioned, QC'd, contract-enforced dataset id.

Per 01-RESEARCH.md Pattern 1, this is the only function a future agent
tool wrapper (Phase 3) needs to call.
"""

from __future__ import annotations

from dataclasses import asdict
from pathlib import Path

from anndata import AnnData

from ingest import contract, loaders, qc
from ingest.store import DatasetStore


def ingest_10x(
    path: str | Path,
    name: str,
    qc_config: qc.QCConfig | None = None,
    store_root: str | Path = "data",
) -> str:
    """Loads a 10x `.mtx` directory or `.h5` file, sets the immutable
    `layers['counts']` contract (INGEST-02), runs QC (QC-01/QC-02), and
    saves the result to the versioned dataset store (INGEST-03).

    Returns the dataset id string `"{name}@{version}"`.
    """
    adata: AnnData = loaders.load(path)
    contract.set_counts_layer(adata)  # INGEST-02, before anything else touches .X

    qc_config = qc_config or qc.QCConfig()
    adata = qc.run(adata, qc_config)  # QC-01 + QC-02

    # qc.run() subsets adata (filter_cells/filter_genes, boolean-mask
    # .copy() slices) whenever any filtering removes cells/genes. Slicing a
    # sparse matrix allocates a new underlying `.data` array that is
    # writeable again and no longer matches the pre-filter checksum -- the
    # write-lock/checksum protects the counts *values* from silent
    # corruption (e.g. an accidental normalize_total on the layer), not the
    # cell/gene *count*, which QC filtering is expected to change. Re-freeze
    # against the final, stored shape so verify_counts_integrity() reflects
    # what's actually persisted.
    contract.set_counts_layer(adata)

    store = DatasetStore(root=store_root)
    version = store.save(
        name, adata, source_path=str(path), qc_config=asdict(qc_config)
    )

    return f"{name}@{version}"
