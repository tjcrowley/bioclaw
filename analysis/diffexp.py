"""Generic Wilcoxon rank-sum differential expression (ANLYS-03).

Per 02-RESEARCH.md Open Question 3 and Pattern 3, `sc.tl.rank_genes_groups`'s
`groupby`/`groups`/`reference` params are already fully generic -- nothing
scanpy-specific ties DE to a Leiden cluster key, so `differential_expression`
works identically for cluster labels or arbitrary condition columns. Per
Don't Hand-Roll guidance, extraction always goes through
`sc.get.rank_genes_groups_df`, never a hand-parsed
`adata.uns["rank_genes_groups"]` structured array.
"""

from __future__ import annotations

import scanpy as sc
from anndata import AnnData


def differential_expression(
    adata: AnnData,
    groupby: str,
    group1: str,
    group2: str | None = None,
    *,
    n_genes: int = 25,
    tie_correct: bool = True,
) -> AnnData:
    """Runs Wilcoxon rank-sum DE for `group1` vs. `group2` (or vs. "rest"
    of `groupby` when `group2` is None) on a copy of `adata` (never mutates
    the caller's input, matching `preprocess()`'s tool-call boundary
    convention).

    Returns the mutated copy with `adata.uns["rank_genes_groups"]`
    populated; callers extract a bounded result via
    `sc.get.rank_genes_groups_df(result, group=group1)`.
    """
    adata = adata.copy()  # tool-call boundary: never mutate caller's object

    reference = group2 if group2 is not None else "rest"
    sc.tl.rank_genes_groups(
        adata,
        groupby=groupby,
        groups=[group1],
        reference=reference,
        method="wilcoxon",
        tie_correct=tie_correct,
        pts=True,
        corr_method="benjamini-hochberg",
    )

    return adata
