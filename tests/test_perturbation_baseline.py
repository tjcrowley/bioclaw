"""Tests for perturbation/baseline.py: naive_baseline_predict() (PERT-02).

Uses the `perturbation_adata` fixture (30 genes x 350 cells, 5 perturbations
x 50 cells each, 100 control cells) from conftest.py.

Key divergence from 05-03-PLAN.md's test-spec description (documented inline):
`cell_eval.build_base_mean_adata`'s 'naive perturbation-mean baseline' is the
MEAN OF ALL PERTURBATION GROUP MEANS (a global mean), not the per-target-gene
cell mean.  The plan's loose wording 'close to the mean of GENE00-labeled
cells' would only hold if the fixture had a single perturbation -- in this
five-perturbation fixture the two values diverge significantly (GENE00's
per-cell raw mean at index 0 is ~12; the global group mean at index 0 is ~3.7
after normalization).  All tests below assert against the *actual* output of
`build_base_mean_adata`, which is the right ground truth.
"""

import numpy as np
import pytest
import scipy.sparse as sp

import cell_eval

from perturbation.baseline import naive_baseline_predict
from perturbation.summary import PerturbationCall


# ---------------------------------------------------------------------------
# Happy-path test
# ---------------------------------------------------------------------------


def test_naive_baseline_predict_returns_perturbation_call(perturbation_adata):
    """naive_baseline_predict returns a correctly-shaped PerturbationCall.

    Asserts:
    - result is a PerturbationCall with method="naive_baseline" and
      target_gene="GENE00".
    - predicted_expression has length equal to perturbation_adata.n_vars (30).
    - The value matches build_base_mean_adata's actual output for GENE00 rows
      (all GENE00 rows carry the same global-mean-of-pert-means expression
      vector -- extract the first such row as the reference value).
    """
    result = naive_baseline_predict(perturbation_adata, "GENE00")

    assert isinstance(result, PerturbationCall)
    assert result.method == "naive_baseline"
    assert result.target_gene == "GENE00"
    assert len(result.predicted_expression) == perturbation_adata.n_vars

    # Reference: independently call build_base_mean_adata and extract GENE00's row.
    # We call it on a copy to avoid mutating the fixture (the function normalizes X
    # in-place when the data appears to be raw counts).
    ref_adata = cell_eval.build_base_mean_adata(
        perturbation_adata.copy(), allow_discrete=True
    )
    gene00_mask = (ref_adata.obs["target_gene"] == "GENE00").values
    assert gene00_mask.sum() > 0, "GENE00 must appear in baseline_adata"
    # Use numpy bool array (not pandas Series) for sparse matrix indexing.
    ref_row = ref_adata.X[gene00_mask][0]
    if sp.issparse(ref_row):
        ref_row = ref_row.toarray().squeeze()
    ref_row = np.asarray(ref_row).ravel()

    # Tolerance: default np.allclose (rtol=1e-5, atol=1e-8), documented here.
    np.testing.assert_allclose(
        result.predicted_expression,
        ref_row,
        rtol=1e-5,
        atol=1e-8,
        err_msg=(
            "naive_baseline_predict must return the same expression vector that "
            "cell_eval.build_base_mean_adata produces for target_gene rows."
        ),
    )


# ---------------------------------------------------------------------------
# Zero-matching-cells test
# ---------------------------------------------------------------------------


def test_naive_baseline_predict_unknown_gene_raises_value_error(perturbation_adata):
    """naive_baseline_predict raises ValueError for a gene with no matching cells.

    If target_gene is not present in adata.obs[pert_col], the function must raise
    a clear ValueError -- it must NOT silently return a zero/NaN vector.
    """
    with pytest.raises(ValueError, match="GENE99"):
        naive_baseline_predict(perturbation_adata, "GENE99")


# ---------------------------------------------------------------------------
# pipeline.predict() composition test (PERT-02 enforcement)
# ---------------------------------------------------------------------------


def test_predict_pipeline_returns_both_calls(tmp_path, perturbation_adata):
    """pipeline.predict() returns a PerturbationSummary dict with both model_call
    and baseline_call populated -- PERT-02's actual enforcement point.

    Design: persists perturbation_adata directly into a DatasetStore at tmp_path
    via DatasetStore.save() rather than going through the full ingest_10x/QC
    pipeline.  This is intentional -- perturbation_adata already has correct
    target_gene labels and does not need QC filtering or the 10x ingest path.
    Documented here per the plan's instruction to record this choice.
    """
    from ingest.store import DatasetStore
    from perturbation.pipeline import predict

    store = DatasetStore(root=tmp_path)
    store.save("pert-pilot", perturbation_adata)

    dataset_id, summary = predict("pert-pilot", "GENE00", store_root=tmp_path)

    assert dataset_id == "pert-pilot@(latest)"
    # PERT-02 enforcement: both model_call and baseline_call must be present and non-null.
    assert "model_call" in summary, "model_call must be present in summary"
    assert "baseline_call" in summary, "baseline_call must be present in summary"
    assert summary["model_call"] is not None
    assert summary["baseline_call"] is not None

    # Shape checks: predicted_expression vectors must match gene_names length.
    n_genes = len(summary["gene_names"])
    assert len(summary["model_call"]["predicted_expression"]) == n_genes
    assert len(summary["baseline_call"]["predicted_expression"]) == n_genes

    # Method labels must be correct.
    assert summary["model_call"]["method"] == "linear_additive"
    assert summary["baseline_call"]["method"] == "naive_baseline"
    assert summary["model_call"]["target_gene"] == "GENE00"
    assert summary["baseline_call"]["target_gene"] == "GENE00"
