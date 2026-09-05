"""Tests for analysis/diffexp.py -- generic Wilcoxon rank-sum differential
expression (ANLYS-03), and bounded DESummary/DEGeneResult construction
(ANLYS-04).

Uses the structured_adata fixture (~200 cells x ~80 genes) with its
built-in .obs["true_population"] ground-truth column ("A"/"B") directly as
the groupby target -- this plan does not depend on cluster.py's output.
"""

from dataclasses import asdict

import scanpy as sc

from analysis import diffexp
from analysis.summary import DEGeneResult, DESummary

A_MARKERS = {f"GENE{i:02d}" for i in range(15)}  # population A's known elevated block


def test_marker_genes_recovered(structured_adata):
    """differential_expression() between true_population A vs B recovers
    at least half of population A's known elevated marker block
    (GENE00..GENE14) among the top 25 ranked genes -- proves real Wilcoxon
    statistics recover the fixture's known structure, not just "returns
    something" (ANLYS-03)."""
    result, _ = diffexp.differential_expression(
        structured_adata, groupby="true_population", group1="A", group2="B", n_genes=25
    )

    df = sc.get.rank_genes_groups_df(result, group="A").head(25)
    hits = sum(1 for gene in df["names"] if gene in A_MARKERS)
    assert hits >= 13  # at least half of 25


def test_group2_none_behaves_like_explicit_reference(structured_adata):
    """group2=None (comparing vs. 'rest') behaves equivalently to the
    explicit group2='B' call for this two-group fixture, since 'rest' of
    A is exactly B."""
    result_explicit, _ = diffexp.differential_expression(
        structured_adata, groupby="true_population", group1="A", group2="B"
    )
    result_rest, _ = diffexp.differential_expression(
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

    result, summary = diffexp.differential_expression(
        structured_adata, groupby="condition", group1="ctrl", group2="treat"
    )

    df = sc.get.rank_genes_groups_df(result, group="ctrl")
    assert len(df) == structured_adata.n_vars
    assert result.uns["rank_genes_groups"]["params"]["groupby"] == "condition"
    assert summary.groupby == "condition"
    assert summary.group1 == "ctrl"
    assert summary.group2 == "treat"


def test_rank_genes_groups_config_recorded(structured_adata):
    """The DE call uses method='wilcoxon' and corr_method='benjamini-hochberg'
    (recorded in adata.uns['rank_genes_groups']['params']), and pts=True
    (evidenced by the pct_nz_group column being present in the extracted
    result)."""
    result, _ = diffexp.differential_expression(
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


def test_desummary_shape(structured_adata):
    """differential_expression() returns (adata, DESummary). top_genes is
    capped at n_genes (default 25) even though structured_adata has 80
    genes (all tested); each DEGeneResult has non-null gene/score/pval/
    pval_adj/logfoldchange and populated pct_group/pct_rest (from
    pts=True with the default group2=None -> reference='rest' path, which
    scanpy populates pct_nz_reference for). n_genes_tested/n_significant
    are computed over the full (untruncated) ranking (ANLYS-04)."""
    _, summary = diffexp.differential_expression(
        structured_adata, groupby="true_population", group1="A", group2=None
    )

    assert isinstance(summary, DESummary)
    assert summary.groupby == "true_population"
    assert summary.group1 == "A"
    assert summary.group2 is None
    assert summary.method == "wilcoxon"
    assert summary.dataset_id is None
    assert summary.n_genes_tested == 80
    assert 0 <= summary.n_significant <= 80

    assert len(summary.top_genes) <= 25
    for gene_result in summary.top_genes:
        assert isinstance(gene_result, DEGeneResult)
        assert gene_result.gene is not None
        assert gene_result.score is not None
        assert gene_result.pval is not None
        assert gene_result.pval_adj is not None
        assert gene_result.logfoldchange is not None
        assert gene_result.pct_group is not None
        assert gene_result.pct_rest is not None


def test_desummary_top_genes_capped_below_n_genes_tested(structured_adata):
    """With a small explicit n_genes, top_genes is capped at n_genes while
    n_genes_tested still reflects all 80 genes in the fixture."""
    _, summary = diffexp.differential_expression(
        structured_adata, groupby="true_population", group1="A", group2="B", n_genes=10
    )

    assert summary.n_genes_tested == 80
    assert len(summary.top_genes) <= 10


def test_desummary_is_bounded(structured_adata):
    """dataclasses.asdict(summary) never contains the full 80-gene ranked
    table -- only the capped top_genes list."""
    _, summary = diffexp.differential_expression(
        structured_adata, groupby="true_population", group1="A", group2="B"
    )

    data = asdict(summary)
    assert len(data["top_genes"]) <= 25
    for gene_row in data["top_genes"]:
        assert set(gene_row.keys()) == {
            "gene",
            "score",
            "pval",
            "pval_adj",
            "logfoldchange",
            "pct_group",
            "pct_rest",
        }
