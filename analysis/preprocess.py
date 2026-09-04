"""Deterministic normalize -> log1p -> HVG -> PCA prerequisite pipeline
(ANLYS-01).

Per 02-RESEARCH.md Pattern 1 and Pitfall 3, HVG selection under the default
`flavor="seurat"` silently produces a numerically wrong (not erroring)
selection if run before normalize_total/log1p -- the call order is
enforced here, not left to caller discipline. Per Pitfall 4, `n_top_genes`/
`n_pcs` defaults (2000/50) raise solver errors on small fixtures unless
clamped to the input's actual size.
"""

from __future__ import annotations

import scanpy as sc
from anndata import AnnData

from analysis.summary import PreprocessSummary


def preprocess(
    adata: AnnData,
    *,
    target_sum: float | None = None,
    n_top_genes: int = 2000,
    n_pcs: int = 50,
    random_state: int = 0,
) -> tuple[AnnData, PreprocessSummary]:
    """Runs normalize_total -> log1p -> highly_variable_genes -> pca, in
    that exact order, on a copy of `adata` (never mutates the caller's
    input). Size-sensitive params are clamped to the input's actual
    dimensions so small test-fixture-sized inputs don't crash the HVG/PCA
    solvers.

    Returns the mutated copy plus a bounded `PreprocessSummary` whose
    `config` reflects the post-clamping values actually used.
    """
    adata = adata.copy()  # tool-call boundary: never mutate caller's object

    sc.pp.normalize_total(adata, target_sum=target_sum)
    sc.pp.log1p(adata)

    resolved_n_top_genes = min(n_top_genes, adata.n_vars)
    sc.pp.highly_variable_genes(adata, n_top_genes=resolved_n_top_genes)

    # PCA restricts to adata.var['highly_variable'] automatically once HVG
    # selection has run, so the solver's actual feature count is n_hvg, not
    # adata.n_vars -- and can be smaller than resolved_n_top_genes if HVG
    # selection itself returned fewer genes than requested (e.g. too few
    # genes with nonzero dispersion on a small/edge-case fixture). Clamp
    # against the *actual* n_hvg, and subtract one more than the naive
    # min(n_obs, n_features) bound: sklearn's arpack solver requires
    # n_components strictly less than min(n_samples, n_features).
    n_hvg = int(adata.var["highly_variable"].sum())
    resolved_n_pcs = min(n_pcs, adata.n_obs - 1, n_hvg - 1)
    sc.pp.pca(adata, n_comps=resolved_n_pcs, random_state=random_state)

    variance_ratio_top10 = adata.uns["pca"]["variance_ratio"][:10].tolist()

    summary = PreprocessSummary(
        dataset_id=None,
        n_cells=adata.n_obs,
        n_genes_total=adata.n_vars,
        n_hvg=int(adata.var["highly_variable"].sum()),
        n_pcs_computed=adata.obsm["X_pca"].shape[1],
        variance_ratio_top10=variance_ratio_top10,
        config={
            "target_sum": target_sum,
            "n_top_genes": resolved_n_top_genes,
            "n_pcs": resolved_n_pcs,
            "random_state": random_state,
        },
    )

    return adata, summary
