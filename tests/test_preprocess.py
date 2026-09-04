"""Tests for analysis/preprocess.py -- normalize/HVG/PCA prerequisite
pipeline, size guards, copy semantics, and PreprocessSummary construction
(ANLYS-01).

Uses the structured_adata fixture (~200 cells x ~80 genes, genuine
cluster structure) for the main behavior assertions, and Phase 1's
synthetic_adata fixture (20 genes x 50 cells) for the small-input size
guard.
"""

from dataclasses import asdict

import numpy as np

from analysis import preprocess
from analysis.summary import PreprocessSummary


def test_preprocess_runs_normalize_hvg_pca(structured_adata):
    """preprocess() returns an AnnData with HVG selection and PCA present,
    with .X changed (normalized + log1p'd) from the raw input (ANLYS-01)."""
    original_X = structured_adata.X.toarray().copy()

    result, _ = preprocess.preprocess(
        structured_adata, n_top_genes=50, n_pcs=10, random_state=0
    )

    assert "highly_variable" in result.var
    assert result.var["highly_variable"].sum() == min(50, result.n_vars)

    assert "X_pca" in result.obsm
    assert result.obsm["X_pca"].shape == (result.n_obs, min(10, result.n_obs - 1, result.n_vars - 1))

    assert not np.allclose(result.X.toarray(), original_X)


def test_preprocess_does_not_mutate_input(structured_adata):
    """preprocess() must not mutate the caller's input AnnData in place."""
    original = structured_adata.copy()

    preprocess.preprocess(structured_adata, n_top_genes=50, n_pcs=10, random_state=0)

    assert np.allclose(
        structured_adata.X.toarray(), original.X.toarray()
    ), "input .X was mutated"
    assert "highly_variable" not in structured_adata.var
    assert "X_pca" not in structured_adata.obsm


def test_preprocess_deterministic(structured_adata):
    """Calling preprocess() twice with the same random_state on the same
    input produces identical X_pca arrays."""
    result1, _ = preprocess.preprocess(
        structured_adata, n_top_genes=50, n_pcs=10, random_state=0
    )
    result2, _ = preprocess.preprocess(
        structured_adata, n_top_genes=50, n_pcs=10, random_state=0
    )

    assert np.allclose(result1.obsm["X_pca"], result2.obsm["X_pca"])


def test_preprocess_small_input_size_guard(synthetic_adata):
    """preprocess() on a small fixture (20 genes, 50 cells) with default
    n_top_genes/n_pcs does not raise -- internal clamping keeps PCA/HVG
    solvers within bounds."""
    result, summary = preprocess.preprocess(synthetic_adata)

    assert "highly_variable" in result.var
    assert "X_pca" in result.obsm
    assert isinstance(summary, PreprocessSummary)


def test_preprocess_summary_shape(structured_adata):
    """preprocess() returns a PreprocessSummary with correct scalar fields
    and post-clamping config values (ANLYS-04)."""
    result, summary = preprocess.preprocess(
        structured_adata, n_top_genes=50, n_pcs=10, random_state=0
    )

    assert isinstance(summary, PreprocessSummary)
    assert summary.n_cells == 200
    assert summary.n_genes_total == 80
    assert summary.n_hvg == min(50, 80)
    assert summary.n_pcs_computed == min(10, 199, 79)
    assert len(summary.variance_ratio_top10) <= 10
    assert summary.dataset_id is None

    assert summary.config["target_sum"] is None
    assert summary.config["n_top_genes"] == min(50, 80)
    assert summary.config["n_pcs"] == min(10, 199, 79)
    assert summary.config["random_state"] == 0


def test_preprocess_summary_is_bounded(structured_adata):
    """dataclasses.asdict(summary) contains no field whose length scales
    with n_cells or n_genes_total -- structural bound check."""
    _, summary = preprocess.preprocess(
        structured_adata, n_top_genes=50, n_pcs=10, random_state=0
    )

    data = asdict(summary)
    for key, value in data.items():
        if isinstance(value, list):
            assert len(value) <= 10, f"field {key} is not bounded: len={len(value)}"
