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

from analysis.summary import DEGeneResult, DESummary


def differential_expression(
    adata: AnnData,
    groupby: str,
    group1: str,
    group2: str | None = None,
    *,
    n_genes: int = 25,
    tie_correct: bool = True,
) -> tuple[AnnData, DESummary]:
    """Runs Wilcoxon rank-sum DE for `group1` vs. `group2` (or vs. "rest"
    of `groupby` when `group2` is None) on a copy of `adata` (never mutates
    the caller's input, matching `preprocess()`'s tool-call boundary
    convention).

    Returns `(adata, DESummary)`: the mutated copy with
    `adata.uns["rank_genes_groups"]` populated, plus a bounded summary
    whose `top_genes` is capped at `n_genes` regardless of how many genes
    were tested.
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

    result_df = sc.get.rank_genes_groups_df(adata, group=group1)
    n_genes_tested = len(result_df)
    n_significant = int((result_df["pvals_adj"] < 0.05).sum())

    top_df = result_df.sort_values("pvals_adj", ascending=True).head(n_genes)
    top_genes = [
        DEGeneResult(
            gene=row["names"],
            score=row["scores"],
            pval=row["pvals"],
            pval_adj=row["pvals_adj"],
            logfoldchange=row["logfoldchanges"],
            pct_group=row.get("pct_nz_group"),
            pct_rest=row.get("pct_nz_reference"),
        )
        for _, row in top_df.iterrows()
    ]

    summary = DESummary(
        dataset_id=None,
        groupby=groupby,
        group1=group1,
        group2=group2,
        method="wilcoxon",
        n_genes_tested=n_genes_tested,
        n_significant=n_significant,
        top_genes=top_genes,
    )

    return adata, summary
