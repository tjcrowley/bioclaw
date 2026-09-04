"""Neighbor graph -> Leiden (igraph flavor) -> UMAP clustering pipeline
(ANLYS-02).

Per 02-RESEARCH.md Pitfall 2, `sc.tl.leiden(..., flavor="igraph")` raises
`ValueError: Cannot use igraph's leiden implementation with a directed
graph.` if `directed=True` is ever passed -- `directed=False` is always
passed explicitly here, never omitted, so this never happens.

Per Pitfall 5, UMAP's own coordinate reproducibility has a known upstream
nondeterminism issue (umap-learn GitHub #1080/#1108) even with a fixed
seed -- only Leiden label determinism is a contract of this module, not
UMAP coordinate exactness.
"""

from __future__ import annotations

import scanpy as sc
from anndata import AnnData

from analysis.summary import ClusterSummary


def cluster(
    adata: AnnData,
    *,
    resolution: float = 1.0,
    n_neighbors: int = 15,
    n_pcs: int | None = None,
    random_state: int = 0,
) -> tuple[AnnData, ClusterSummary]:
    """Runs sc.pp.neighbors -> sc.tl.leiden (flavor="igraph") -> sc.tl.umap
    on a copy of `adata` (never mutates the caller's input). `n_neighbors`
    is clamped to the input's actual size so small test-fixture-sized
    inputs don't crash the neighbor search.

    Returns the mutated copy plus a bounded `ClusterSummary` whose
    `config` reflects the post-clamping values actually used.
    """
    adata = adata.copy()  # tool-call boundary: never mutate caller's object

    resolved_n_neighbors = min(n_neighbors, adata.n_obs - 1)
    sc.pp.neighbors(
        adata,
        n_neighbors=resolved_n_neighbors,
        n_pcs=n_pcs,
        random_state=random_state,
    )
    sc.tl.leiden(
        adata,
        resolution=resolution,
        flavor="igraph",
        n_iterations=2,  # official recommendation paired with flavor="igraph"
        directed=False,  # REQUIRED: flavor="igraph" raises ValueError if directed=True
        random_state=random_state,
    )
    sc.tl.umap(adata, random_state=random_state)

    cluster_sizes = {
        str(k): int(v) for k, v in adata.obs["leiden"].value_counts().items()
    }

    summary = ClusterSummary(
        dataset_id=None,
        n_clusters=len(cluster_sizes),
        cluster_sizes=cluster_sizes,
        resolution=resolution,
        umap_computed="X_umap" in adata.obsm,
        config={
            "resolution": resolution,
            "n_neighbors": resolved_n_neighbors,
            "random_state": random_state,
        },
    )

    return adata, summary
