"""Tests for analysis/diffexp.py -- generic Wilcoxon rank-sum differential
expression (ANLYS-03), and bounded DESummary/DEGeneResult construction
(ANLYS-04).

Uses the structured_adata fixture (~200 cells x ~80 genes) with its
built-in .obs["true_population"] ground-truth column ("A"/"B") directly as
the groupby target -- this plan does not depend on cluster.py's output.
"""

import scanpy as sc

from analysis import diffexp

A_MARKERS = {f"GENE{i:02d}" for i in range(15)}  # population A's known elevated block


def test_marker_genes_recovered(structured_adata):
    """differential_expression() between true_population A vs B recovers
    at least half of population A's known elevated marker block
    (GENE00..GENE14) among the top 25 ranked genes -- proves real Wilcoxon
    statistics recover the fixture's known structure, not just "returns
    something" (ANLYS-03)."""
    result = diffexp.differential_expression(
        structured_adata, groupby="true_population", group1="A", group2="B", n_genes=25
    )

    df = sc.get.rank_genes_groups_df(result, group="A").head(25)
    hits = sum(1 for gene in df["names"] if gene in A_MARKERS)
    assert hits >= 13  # at least half of 25


def test_group2_none_behaves_like_explicit_reference(structured_adata):
    """group2=None (comparing vs. 'rest') behaves equivalently to the
    explicit group2='B' call for this two-group fixture, since 'rest' of
    A is exactly B."""
    result_explicit = diffexp.differential_expression(
        structured_adata, groupby="true_population", group1="A", group2="B"
    )
    result_rest = diffexp.differential_expression(
        structured_adata, groupby="true_population", group1="A", group2=None
    )

    df_explicit = sc.get.rank_genes_groups_df(result_explicit, group="A")
    df_rest = sc.get.rank_genes_groups_df(result_rest, group="A")
    assert df_explicit["names"].tolist() == df_rest["names"].tolist()


def test_generic_over_arbitrary_obs_column(structured_adata):
    """differential_expression() is generic over any categorical .obs
    column -- not hard-coded to a Leiden cluster key. Re-running with a
    synthetically added, population-unrelated 'condition' column also
    succeeds and returns a well-formed result."""
    structured_adata.obs["condition"] = (
        ["ctrl", "treat"] * (structured_adata.n_obs // 2)
    )[: structured_adata.n_obs]

    result = diffexp.differential_expression(
        structured_adata, groupby="condition", group1="ctrl", group2="treat"
    )

    df = sc.get.rank_genes_groups_df(result, group="ctrl")
    assert len(df) == structured_adata.n_vars
    assert result.uns["rank_genes_groups"]["params"]["groupby"] == "condition"


def test_rank_genes_groups_config_recorded(structured_adata):
    """The DE call uses method='wilcoxon' and corr_method='benjamini-hochberg'
    (recorded in adata.uns['rank_genes_groups']['params']), and pts=True
    (evidenced by the pct_nz_group column being present in the extracted
    result)."""
    result = diffexp.differential_expression(
        structured_adata, groupby="true_population", group1="A", group2="B"
    )

    params = result.uns["rank_genes_groups"]["params"]
    assert params["method"] == "wilcoxon"
    assert params["corr_method"] == "benjamini-hochberg"

    df = sc.get.rank_genes_groups_df(result, group="A")
    assert "pct_nz_group" in df.columns


def test_does_not_mutate_input(structured_adata):
    """differential_expression() must not mutate the caller's input
    AnnData in place (tool-call boundary convention shared with
    preprocess())."""
    original_obs_columns = set(structured_adata.obs.columns)

    diffexp.differential_expression(
        structured_adata, groupby="true_population", group1="A", group2="B"
    )

    assert set(structured_adata.obs.columns) == original_obs_columns
    assert "rank_genes_groups" not in structured_adata.uns
