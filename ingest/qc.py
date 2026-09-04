"""QC metric computation and config-driven filtering (QC-01, QC-02).

Computes standard single-cell QC metrics (mitochondrial %, doublet score,
gene/count totals) on any AnnData, then filters by an explicit, overridable
`QCConfig` -- never a hard-coded threshold in this module's function bodies.

Every `run()` call writes the resolved config plus a per-reason filtering
breakdown into `adata.uns['qc']`, so a researcher can see exactly what was
filtered and why (per 01-RESEARCH.md Pattern 2 / Pitfall 3: a single fixed
threshold set applied to every dataset silently biases which cell types
survive, e.g. drops legitimate high-mito cardiomyocytes).
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Literal

import scanpy as sc
from anndata import AnnData


@dataclass
class QCConfig:
    """Explicit, overridable QC thresholds -- never hard-coded inline.

    `max_pct_mt=None` means "compute pct_counts_mt but don't filter on it".
    `doublet_action="flag"` (the default) labels predicted doublets in
    `.obs` without removing them; 10x/OSCA guidance treats doublet scores as
    "suspect, inspect with cluster context," not an automatic removal.
    """

    min_genes_per_cell: int = 200
    min_cells_per_gene: int = 3
    max_pct_mt: float | None = 20.0
    doublet_action: Literal["flag", "filter"] = "flag"


def _run_scrublet(adata: AnnData) -> None:
    """Runs Scrublet, shrinking `n_prin_comps` if the default (30) exceeds
    the PCA solver's `min(n_samples, n_features)` bound after Scrublet's
    internal HVG selection -- a real failure mode on small datasets (e.g.
    this project's small synthetic test fixtures), not just tutorial-scale
    real data, since the PCA feature count depends on Scrublet's own
    variable-gene filtering, not directly on `adata.n_vars`.
    """
    scrublet_fn = sc.pp.scrublet if hasattr(sc.pp, "scrublet") else sc.external.pp.scrublet

    n_prin_comps = min(30, adata.n_vars, adata.n_obs)
    while n_prin_comps >= 2:
        try:
            scrublet_fn(adata, n_prin_comps=n_prin_comps, verbose=False)
            break
        except ValueError:
            n_prin_comps //= 2
    else:
        scrublet_fn(adata, n_prin_comps=2, verbose=False)

    # An all-zero cell has no expression signal for Scrublet's kNN/PCA step
    # and comes back as NaN -- treat "no counts at all" as "not a doublet"
    # rather than leaving a null in a column downstream code expects to
    # always be populated.
    adata.obs["doublet_score"] = adata.obs["doublet_score"].fillna(0.0)
    # fillna on a bool column promotes it to object dtype, which silently
    # breaks `~` (bitwise, not logical, negation on plain Python bools) --
    # cast back to a real bool dtype so downstream `~adata.obs["predicted_doublet"]`
    # filtering behaves as logical negation, not bitwise int inversion.
    adata.obs["predicted_doublet"] = adata.obs["predicted_doublet"].fillna(False).astype(bool)


def _compute_metrics(adata: AnnData) -> AnnData:
    """Adds pct_counts_mt/n_genes_by_counts/total_counts (mito %, gene
    counts) and doublet_score/predicted_doublet (Scrublet) to `.obs`.
    """
    adata.var["mt"] = adata.var_names.str.upper().str.startswith("MT-")
    sc.pp.calculate_qc_metrics(
        adata, qc_vars=["mt"], percent_top=None, log1p=False, inplace=True
    )
    # An all-zero cell (total_counts == 0) yields pct_counts_mt = 0/0 = NaN;
    # treat "no counts at all" as 0% mitochondrial rather than leaving a
    # null in a column downstream QC/filtering code expects to always be
    # populated -- such cells are typically dropped by min_genes filtering
    # anyway, but the column itself must never be null.
    adata.obs["pct_counts_mt"] = adata.obs["pct_counts_mt"].fillna(0.0)

    _run_scrublet(adata)

    return adata


def run(adata: AnnData, cfg: QCConfig | None = None) -> AnnData:
    """Computes standard QC metrics, filters by `cfg` thresholds, and writes
    a complete audit log to `adata.uns['qc']`.

    Filtering order: min_genes_per_cell -> min_cells_per_gene -> max_pct_mt
    (if set) -> doublet removal (if doublet_action="filter"). Never crashes
    on an empty result -- an implausibly strict config produces a valid
    0-n_obs AnnData with a complete `removed_by_reason` breakdown instead of
    raising.
    """
    cfg = cfg or QCConfig()
    n_before = adata.n_obs

    adata = _compute_metrics(adata)

    removed_by_reason: dict[str, int] = {}

    n_pre_gene_filter = adata.n_obs
    sc.pp.filter_cells(adata, min_genes=cfg.min_genes_per_cell)
    removed_by_reason["low_gene_count"] = n_pre_gene_filter - adata.n_obs

    sc.pp.filter_genes(adata, min_cells=cfg.min_cells_per_gene)

    removed_by_reason["high_mito"] = 0
    if cfg.max_pct_mt is not None and adata.n_obs > 0:
        n_pre_mito_filter = adata.n_obs
        adata = adata[adata.obs["pct_counts_mt"] <= cfg.max_pct_mt].copy()
        removed_by_reason["high_mito"] = n_pre_mito_filter - adata.n_obs

    removed_by_reason["doublet"] = 0
    if cfg.doublet_action == "filter" and adata.n_obs > 0:
        n_pre_doublet_filter = adata.n_obs
        adata = adata[~adata.obs["predicted_doublet"]].copy()
        removed_by_reason["doublet"] = n_pre_doublet_filter - adata.n_obs

    adata.uns["qc"] = {
        "config": asdict(cfg),
        "n_cells_before": n_before,
        "n_cells_after": adata.n_obs,
        "removed_by_reason": removed_by_reason,
    }
    return adata
