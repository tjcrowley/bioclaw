"""Tests for perturbation/model.py -- LinearAdditivePerturbationModel and fit_from_adata.

Task 1 tests: hand-built numpy arrays, no fixture dependency, fast and self-contained.
  - Exact known-gene recovery (seen during fit -> lookup path, never fallback regression)
  - Non-crashing unseen-gene fallback (in gene_names but NOT in fit-time pert_means)
  - KeyError for a gene absent from gene_names entirely

Task 2 tests: fixture-based (perturbation_adata), verifying fit_from_adata() round-trip.
  - control_mean matches the fixture's non-targeting cell group mean
  - predict() for each of GENE00-GENE04 tracks the observed group mean within tolerance
"""

import numpy as np
import pytest

from perturbation.model import LinearAdditivePerturbationModel, fit_from_adata


# ---------------------------------------------------------------------------
# Task 1: Hand-built unit tests (no fixture dependency)
# ---------------------------------------------------------------------------

def _make_small_problem():
    """Returns (gene_names, control_mean, pert_means) for a 5-gene toy problem.

    gene_names: ["GA", "GB", "GC", "GD", "GE"]
    control_mean: [1.0, 2.0, 3.0, 4.0, 5.0]
    pert_means: three of the five genes used as fit-time perturbations.
      GA_pert_mean = [11.0, 2.0, 3.0, 4.0, 5.0]  (shift +10 on index 0)
      GB_pert_mean = [1.0, 12.0, 3.0, 4.0, 5.0]  (shift +10 on index 1)
      GC_pert_mean = [1.0, 2.0, 13.0, 4.0, 5.0]  (shift +10 on index 2)
    GD and GE are in gene_names but were NOT used as perturbations during fit().
    """
    gene_names = ["GA", "GB", "GC", "GD", "GE"]
    control_mean = np.array([1.0, 2.0, 3.0, 4.0, 5.0])
    pert_means = {
        "GA": np.array([11.0, 2.0, 3.0, 4.0, 5.0]),
        "GB": np.array([1.0, 12.0, 3.0, 4.0, 5.0]),
        "GC": np.array([1.0, 2.0, 13.0, 4.0, 5.0]),
    }
    return gene_names, control_mean, pert_means


def test_known_gene_exact_recovery():
    """predict(control_mean, target_gene) for a gene seen during fit() returns
    control_mean + known_shift == pert_mean_at_fit_time, exactly (np.allclose).

    Verifies the lookup path: no ridge regression is involved for known genes.
    """
    gene_names, control_mean, pert_means = _make_small_problem()
    model = LinearAdditivePerturbationModel(alpha=1.0)
    model.fit(gene_names, control_mean, pert_means)

    for gene, expected_pert_mean in pert_means.items():
        predicted = model.predict(control_mean, gene)
        assert predicted.shape == control_mean.shape, (
            f"predict() shape mismatch for {gene}: got {predicted.shape}"
        )
        assert np.allclose(predicted, expected_pert_mean), (
            f"Exact recovery failed for known gene {gene}: "
            f"expected {expected_pert_mean}, got {predicted}"
        )


def test_unseen_gene_fallback_no_crash():
    """predict(control_mean, target_gene) for a gene in gene_names but NOT in
    fit-time pert_means exercises the ridge fallback path and returns a full-length
    vector without raising.

    Does NOT assert exact numeric values (the fallback is an extrapolation);
    just verifies shape and non-NaN.
    """
    gene_names, control_mean, pert_means = _make_small_problem()
    model = LinearAdditivePerturbationModel(alpha=1.0)
    model.fit(gene_names, control_mean, pert_means)

    # "GD" is in gene_names (index 3, control_mean[3] = 4.0) but never in pert_means.
    predicted = model.predict(control_mean, "GD")
    assert predicted.shape == control_mean.shape, (
        f"Fallback predict() shape mismatch: got {predicted.shape}"
    )
    assert not np.any(np.isnan(predicted)), "Fallback predict() returned NaN values"


def test_gene_absent_from_gene_names_raises_key_error():
    """predict(control_mean, target_gene) for a gene NOT in gene_names at all
    raises KeyError naming the missing gene.

    This is a distinct failure mode from 'unseen during fit but a real gene'.
    """
    gene_names, control_mean, pert_means = _make_small_problem()
    model = LinearAdditivePerturbationModel(alpha=1.0)
    model.fit(gene_names, control_mean, pert_means)

    with pytest.raises(KeyError, match="NOT_IN_GENE_NAMES"):
        model.predict(control_mean, "NOT_IN_GENE_NAMES")


def test_predict_before_fit_raises_runtime_error():
    """Calling predict() on an unfitted model raises RuntimeError."""
    model = LinearAdditivePerturbationModel()
    control_mean = np.array([1.0, 2.0, 3.0])
    with pytest.raises(RuntimeError):
        model.predict(control_mean, "GENE00")


# ---------------------------------------------------------------------------
# Task 2: Fixture-based tests using perturbation_adata
# ---------------------------------------------------------------------------

def test_fit_from_adata_control_mean(perturbation_adata):
    """fit_from_adata() control_mean equals the mean of the non-targeting cells'
    expression, computed independently.

    The fixture has 100 non-targeting control cells and 250 perturbed cells (350 total).
    """
    model, control_mean = fit_from_adata(perturbation_adata)

    assert len(control_mean) == perturbation_adata.n_vars, (
        f"control_mean length {len(control_mean)} != n_vars {perturbation_adata.n_vars}"
    )

    # Independently compute control mean from the raw fixture.
    mask = perturbation_adata.obs["target_gene"] == "non-targeting"
    X = perturbation_adata.X
    # Densify if sparse (mirrors fit_from_adata's own densification).
    try:
        from scipy import sparse as sp
        if sp.issparse(X):
            X = X.toarray()
    except ImportError:
        pass
    expected_control_mean = X[mask].mean(axis=0)

    assert np.allclose(control_mean, expected_control_mean), (
        f"fit_from_adata control_mean mismatch: max abs diff = "
        f"{np.abs(control_mean - expected_control_mean).max()}"
    )


def test_fit_from_adata_known_gene_recovery(perturbation_adata):
    """For each of GENE00-GENE04, model.predict(control_mean, gene) matches the
    observed 50-cell group mean (computed independently) within a reasonable tolerance.

    The fixture applies a hard +10 shift on a single gene index per perturbation on top
    of Poisson(lam=2) background. Since these genes are present in pert_means at fit
    time (fit_from_adata computes group means and passes them to model.fit), predict()
    uses the exact known-shift lookup path, so recovery should be very close to the
    actual group mean (limited only by floating-point precision).

    Tolerance: atol=0.5 per gene. The fit uses the empirical group mean (same as the
    test's reference), so np.allclose default tolerance (atol=1e-8) would hold for
    the exact lookup path. We use atol=0.5 as a defensively generous threshold to
    document intent; if this fails substantially it indicates a regression to the
    fallback path rather than the lookup path.
    """
    model, control_mean = fit_from_adata(perturbation_adata)

    X = perturbation_adata.X
    try:
        from scipy import sparse as sp
        if sp.issparse(X):
            X = X.toarray()
    except ImportError:
        pass

    perturbed_genes = ["GENE00", "GENE01", "GENE02", "GENE03", "GENE04"]
    for gene in perturbed_genes:
        mask = perturbation_adata.obs["target_gene"] == gene
        expected_group_mean = X[mask].mean(axis=0)

        predicted = model.predict(control_mean, gene)

        assert predicted.shape == (perturbation_adata.n_vars,), (
            f"predict() shape mismatch for {gene}"
        )
        assert np.allclose(predicted, expected_group_mean, atol=0.5), (
            f"fit_from_adata recovery failed for {gene}: "
            f"max abs diff = {np.abs(predicted - expected_group_mean).max():.4f} "
            f"(atol=0.5)"
        )
