"""Bounded-summary dataclass contracts for Phase 2 (analysis) modules.

These dataclasses are the single source of truth for every Wave 1/2
module's return shape (`preprocess.py`, `cluster.py`, `diffexp.py`,
`pipeline.py`). Each is O(1) or O(top_n): no field's size may scale with
`n_cells` or total `n_genes` -- only aggregates and top-N tables are ever
returned. Full per-cell/per-gene arrays stay inside AnnData, never in these
summaries.

`dataset_id` fields are `None` when a dataclass is built by a low-level
module function (`preprocess()`, `cluster()`, `differential_expression()`),
and are filled in by `analysis/pipeline.py` (Wave 2) once `store.save()`
returns the new version -- mirrors how `ingest/qc.py`'s `QCConfig` is
resolved independently of the store, then logged by `ingest/pipeline.py`.
"""

from dataclasses import dataclass


@dataclass
class PreprocessSummary:
    """Bounding invariant: `variance_ratio_top10` is capped at the first
    <=10 PCA components only -- never the full explained-variance array.
    All other fields are scalars or a `config` dict, never per-cell or
    per-gene arrays.
    """

    dataset_id: str | None
    n_cells: int
    n_genes_total: int
    n_hvg: int
    n_pcs_computed: int
    variance_ratio_top10: list[float]
    config: dict


@dataclass
class ClusterSummary:
    """Bounding invariant: `cluster_sizes` is O(n_clusters), never
    O(n_cells) -- it is a mapping of cluster label to cell count, not a
    per-cell cluster assignment array.
    """

    dataset_id: str | None
    n_clusters: int
    cluster_sizes: dict[str, int]
    resolution: float
    umap_computed: bool
    config: dict


@dataclass
class DEGeneResult:
    """A single gene's differential-expression result row. Only ever
    appears capped inside `DESummary.top_genes`, never as a full
    per-gene array.
    """

    gene: str
    score: float
    pval: float
    pval_adj: float
    logfoldchange: float
    pct_group: float | None
    pct_rest: float | None


@dataclass
class DESummary:
    """Bounding invariant: `top_genes` is capped (e.g. top 25 by
    `pval_adj`) -- never the full ranked per-gene array. `n_genes_tested`
    and `n_significant` are scalar aggregates computed over the full
    ranking, but the ranking itself is not retained here.
    """

    dataset_id: str | None
    groupby: str
    group1: str
    group2: str | None
    method: str
    n_genes_tested: int
    n_significant: int
    top_genes: list[DEGeneResult]
