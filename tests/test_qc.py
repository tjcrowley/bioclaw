"""Tests for ingest/qc.py -- QC metric computation, config-driven filtering,
and the per-run audit log in adata.uns['qc'] (QC-01, QC-02).

Uses the synthetic_adata fixture from tests/conftest.py directly -- this
module operates on any AnnData, no loaders.py involvement needed.
"""

from ingest import qc


def test_qc_metrics_present(synthetic_adata):
    """calculate_qc_metrics + scrublet columns are present and non-null for
    every cell in the fixture (QC-01)."""
    result = qc.run(synthetic_adata, qc.QCConfig(min_genes_per_cell=0, max_pct_mt=None))

    expected_cols = [
        "pct_counts_mt",
        "n_genes_by_counts",
        "total_counts",
        "doublet_score",
        "predicted_doublet",
    ]
    for col in expected_cols:
        assert col in result.obs.columns, f"missing column: {col}"
        assert result.obs[col].notna().all(), f"null values in column: {col}"


def test_qc_config_logged(synthetic_adata):
    """run() with default QCConfig filters by thresholds, does not remove
    doublets by default, and writes a complete adata.uns['qc'] audit dict
    (QC-02)."""
    cfg = qc.QCConfig()
    n_before = synthetic_adata.n_obs
    result = qc.run(synthetic_adata, cfg)

    assert "qc" in result.uns
    log = result.uns["qc"]

    assert log["config"] == {
        "min_genes_per_cell": cfg.min_genes_per_cell,
        "min_cells_per_gene": cfg.min_cells_per_gene,
        "max_pct_mt": cfg.max_pct_mt,
        "doublet_action": cfg.doublet_action,
    }
    assert log["n_cells_before"] == n_before
    assert log["n_cells_after"] == result.n_obs
    assert "removed_by_reason" in log
    assert isinstance(log["removed_by_reason"], dict)

    # default doublet_action="flag" -- doublets not removed, just labeled
    assert cfg.doublet_action == "flag"
    assert "predicted_doublet" in result.obs.columns


def test_threshold_changes_filtering(synthetic_adata):
    """Changing min_genes_per_cell/max_pct_mt between two run() calls on the
    same input changes n_cells_after and the corresponding removed_by_reason
    entry -- proves thresholds are live parameters, not hard-coded."""
    lenient = qc.run(synthetic_adata.copy(), qc.QCConfig(min_genes_per_cell=0, max_pct_mt=None))
    strict = qc.run(synthetic_adata.copy(), qc.QCConfig(min_genes_per_cell=15, max_pct_mt=None))

    assert strict.uns["qc"]["n_cells_after"] < lenient.uns["qc"]["n_cells_after"]
    assert strict.uns["qc"]["removed_by_reason"]["low_gene_count"] > 0

    lenient_mt = qc.run(synthetic_adata.copy(), qc.QCConfig(min_genes_per_cell=0, max_pct_mt=None))
    strict_mt = qc.run(synthetic_adata.copy(), qc.QCConfig(min_genes_per_cell=0, max_pct_mt=5.0))

    assert strict_mt.uns["qc"]["n_cells_after"] < lenient_mt.uns["qc"]["n_cells_after"]
    assert strict_mt.uns["qc"]["removed_by_reason"]["high_mito"] > 0


def test_doublet_filter_action(synthetic_adata):
    """doublet_action='filter' removes predicted doublets and records them
    under removed_by_reason['doublet']; default 'flag' leaves them in."""
    flagged = qc.run(
        synthetic_adata.copy(),
        qc.QCConfig(min_genes_per_cell=0, max_pct_mt=None, doublet_action="flag"),
    )
    assert flagged.uns["qc"]["removed_by_reason"].get("doublet", 0) == 0

    filtered = qc.run(
        synthetic_adata.copy(),
        qc.QCConfig(min_genes_per_cell=0, max_pct_mt=None, doublet_action="filter"),
    )
    n_doublets_flagged = int(flagged.obs["predicted_doublet"].sum())
    assert filtered.uns["qc"]["removed_by_reason"].get("doublet", 0) == n_doublets_flagged
    assert filtered.n_obs == flagged.n_obs - n_doublets_flagged


def test_impossibly_strict_config_returns_empty_result(synthetic_adata):
    """An implausibly strict config (min_genes_per_cell=100000) does not
    raise or crash; returns a valid 0-n_obs AnnData with n_cells_after == 0
    and removed_by_reason reflecting the full removal. A subsequent .obs
    access on the empty result must not error."""
    cfg = qc.QCConfig(min_genes_per_cell=100000)
    result = qc.run(synthetic_adata, cfg)

    assert result.n_obs == 0
    assert result.uns["qc"]["n_cells_after"] == 0
    assert result.uns["qc"]["removed_by_reason"]["low_gene_count"] > 0

    # must not error on empty .obs access
    assert list(result.obs.columns) is not None
    assert len(result.obs) == 0
