"""Tests for benchmark/vcc_eval.py -- Plan 05-04 (VCC-02).

Tests are structured in two groups:

Group 1 (Task 1): compute_vcc_metrics() wrapper around cell_eval.MetricsEvaluator.
  - Fixture pair where adata_pred is IDENTICAL to adata_real: MAE ~ 0, PDS = 1.0.
  - Fixture pair where adata_pred is corrupted: MAE is meaningfully higher than the
    identical-data case, proving the wrapper actually invokes real computation.

Group 2 (Task 2): run_vcc_eval() direct-call harness.
  - Persists perturbation_adata into a DatasetStore at tmp_path, calls run_vcc_eval()
    over ["GENE00", "GENE01"], asserts both predictor_metrics and baseline_metrics
    carry the same MAE/PDS/DES keys produced by compute_vcc_metrics().
    This proves VCC-02's "bypasses the agent loop" harness works end-to-end on
    real (fixture) data.

Real API (introspected against the actually-installed cell-eval package, 2026-09-09):
- cell_eval.MetricsEvaluator() constructor arg is `pert_col` (default "target"),
  not "target_gene_col" or "perturbation_col".
- compute(profile="vcc") returns (results: pl.DataFrame, agg_results: pl.DataFrame).
  Per-perturbation df columns: perturbation, overlap_at_N, mae, discrimination_score_l1.
  Aggregate df columns: statistic, overlap_at_N, mae, discrimination_score_l1.
- compute_vcc_metrics() normalises this to:
    {"mae": float, "pds": float, "des": float}
  using per-perturbation mean (one scalar per metric, aggregated over target_genes).

NOTE: Both adata_pred and adata_real supplied to MetricsEvaluator MUST contain a
"non-targeting" control row in obs[pert_col] -- the evaluator validates this.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest
from anndata import AnnData
from scipy import sparse


# ---------------------------------------------------------------------------
# Shared helper: build a minimal MetricsEvaluator-compatible AnnData
# ---------------------------------------------------------------------------

def _make_fixture_pair(
    data_pred: np.ndarray,
    data_real: np.ndarray,
    pert_names: list[str],
    gene_names: list[str],
    pert_col: str = "target_gene",
    control_pert: str = "non-targeting",
) -> tuple[AnnData, AnnData]:
    """Build (adata_pred, adata_real) with control row included.

    Both datas must have one row per label in all_labels = [control_pert] + pert_names.
    data_pred/data_real should have shape (1 + len(pert_names), len(gene_names)).
    """
    all_labels = [control_pert] + pert_names
    obs = pd.DataFrame({pert_col: all_labels}, index=all_labels)
    var = pd.DataFrame(index=gene_names)

    adata_real = AnnData(X=sparse.csr_matrix(data_real), obs=obs.copy(), var=var.copy())
    adata_pred = AnnData(X=sparse.csr_matrix(data_pred), obs=obs.copy(), var=var.copy())
    return adata_pred, adata_real


# ---------------------------------------------------------------------------
# Task 1 tests: compute_vcc_metrics()
# ---------------------------------------------------------------------------

class TestComputeVccMetrics:
    """Tests for compute_vcc_metrics() -- the MetricsEvaluator wrapper."""

    def _make_perfect_pair(self) -> tuple[AnnData, AnnData]:
        """adata_pred IDENTICAL to adata_real (perfect prediction)."""
        n_genes = 10
        pert_names = ["GENE_A", "GENE_B", "GENE_C"]
        gene_names = [f"GENE{i}" for i in range(n_genes)]

        rng = np.random.default_rng(42)
        # One row per label (control + 3 perts)
        data = rng.poisson(lam=5, size=(1 + len(pert_names), n_genes)).astype(float)
        return _make_fixture_pair(data, data, pert_names, gene_names)

    def _make_corrupted_pair(self) -> tuple[AnnData, AnnData]:
        """adata_pred has shuffled values vs adata_real (corrupted prediction)."""
        n_genes = 10
        pert_names = ["GENE_A", "GENE_B", "GENE_C"]
        gene_names = [f"GENE{i}" for i in range(n_genes)]

        rng = np.random.default_rng(42)
        data = rng.poisson(lam=5, size=(1 + len(pert_names), n_genes)).astype(float)

        rng2 = np.random.default_rng(99)
        data_corrupt = data.copy()
        for i in range(data_corrupt.shape[0]):
            data_corrupt[i] = rng2.permutation(data_corrupt[i])

        return _make_fixture_pair(data_corrupt, data, pert_names, gene_names)

    def test_perfect_prediction_mae_near_zero(self):
        """When pred == real, MAE must be essentially zero."""
        from benchmark.vcc_eval import compute_vcc_metrics

        adata_pred, adata_real = self._make_perfect_pair()
        metrics = compute_vcc_metrics(adata_pred, adata_real, allow_discrete=True)

        assert "mae" in metrics, f"Expected 'mae' key in metrics, got: {list(metrics.keys())}"
        assert metrics["mae"] == pytest.approx(0.0, abs=1e-9), (
            f"Expected MAE ~ 0.0 for identical pred/real, got {metrics['mae']}"
        )

    def test_perfect_prediction_pds_is_one(self):
        """When pred == real, PDS (discrimination_score_l1) must be 1.0."""
        from benchmark.vcc_eval import compute_vcc_metrics

        adata_pred, adata_real = self._make_perfect_pair()
        metrics = compute_vcc_metrics(adata_pred, adata_real, allow_discrete=True)

        assert "pds" in metrics, f"Expected 'pds' key in metrics, got: {list(metrics.keys())}"
        assert metrics["pds"] == pytest.approx(1.0, abs=1e-9), (
            f"Expected PDS = 1.0 for identical pred/real, got {metrics['pds']}"
        )

    def test_perfect_prediction_des_key_present(self):
        """DES (overlap_at_N) key must be present regardless of value."""
        from benchmark.vcc_eval import compute_vcc_metrics

        adata_pred, adata_real = self._make_perfect_pair()
        metrics = compute_vcc_metrics(adata_pred, adata_real, allow_discrete=True)

        assert "des" in metrics, f"Expected 'des' key in metrics, got: {list(metrics.keys())}"
        # DES value is valid (non-negative float)
        assert isinstance(metrics["des"], float), (
            f"Expected float for 'des', got {type(metrics['des'])}"
        )
        assert metrics["des"] >= 0.0

    def test_corrupted_prediction_mae_higher_than_perfect(self):
        """Corrupted pred must produce meaningfully higher MAE than identical pred."""
        from benchmark.vcc_eval import compute_vcc_metrics

        adata_pred_perfect, adata_real = self._make_perfect_pair()
        adata_pred_corrupt, _ = self._make_corrupted_pair()

        metrics_perfect = compute_vcc_metrics(adata_pred_perfect, adata_real, allow_discrete=True)
        metrics_corrupt = compute_vcc_metrics(adata_pred_corrupt, adata_real, allow_discrete=True)

        assert metrics_corrupt["mae"] > metrics_perfect["mae"] + 0.5, (
            f"Expected corrupted MAE ({metrics_corrupt['mae']}) to be meaningfully "
            f"higher than perfect MAE ({metrics_perfect['mae']})"
        )

    def test_returns_dict_with_required_keys(self):
        """compute_vcc_metrics must return dict with all three required keys."""
        from benchmark.vcc_eval import compute_vcc_metrics

        adata_pred, adata_real = self._make_perfect_pair()
        metrics = compute_vcc_metrics(adata_pred, adata_real, allow_discrete=True)

        required_keys = {"mae", "pds", "des"}
        assert required_keys.issubset(metrics.keys()), (
            f"Missing keys: {required_keys - set(metrics.keys())}"
        )
        for key in required_keys:
            assert isinstance(metrics[key], float), (
                f"Expected float for '{key}', got {type(metrics[key])}"
            )

    def test_no_outdir_required(self):
        """compute_vcc_metrics must work without explicit outdir (uses tmpdir internally)."""
        from benchmark.vcc_eval import compute_vcc_metrics

        adata_pred, adata_real = self._make_perfect_pair()
        # Should not raise even without outdir argument
        metrics = compute_vcc_metrics(adata_pred, adata_real, allow_discrete=True)
        assert isinstance(metrics, dict)


# ---------------------------------------------------------------------------
# Task 2 tests: run_vcc_eval()
# ---------------------------------------------------------------------------

class TestRunVccEval:
    """Tests for run_vcc_eval() -- direct-call harness (bypasses agent/MCP)."""

    def test_returns_both_metric_sets(self, perturbation_adata, tmp_path):
        """run_vcc_eval must return predictor_metrics and baseline_metrics."""
        from benchmark.vcc_eval import run_vcc_eval
        from ingest.store import DatasetStore

        # Persist perturbation_adata into a tmp DatasetStore
        store = DatasetStore(root=tmp_path)
        store.save("pert-fixture", perturbation_adata)

        result = run_vcc_eval(
            "pert-fixture",
            ["GENE00", "GENE01"],
            store_root=tmp_path,
        )

        assert "predictor_metrics" in result, f"Missing 'predictor_metrics' in result: {list(result.keys())}"
        assert "baseline_metrics" in result, f"Missing 'baseline_metrics' in result: {list(result.keys())}"

    def test_metric_keys_match_compute_vcc_metrics(self, perturbation_adata, tmp_path):
        """Both predictor_metrics and baseline_metrics must have mae/pds/des keys."""
        from benchmark.vcc_eval import run_vcc_eval
        from ingest.store import DatasetStore

        store = DatasetStore(root=tmp_path)
        store.save("pert-fixture", perturbation_adata)

        result = run_vcc_eval(
            "pert-fixture",
            ["GENE00", "GENE01"],
            store_root=tmp_path,
        )

        required_keys = {"mae", "pds", "des"}
        for name, metrics in [("predictor_metrics", result["predictor_metrics"]),
                               ("baseline_metrics", result["baseline_metrics"])]:
            assert required_keys.issubset(metrics.keys()), (
                f"{name} missing keys: {required_keys - set(metrics.keys())}"
            )

    def test_returns_dataset_id_and_target_genes(self, perturbation_adata, tmp_path):
        """Result must include dataset_id and target_genes fields."""
        from benchmark.vcc_eval import run_vcc_eval
        from ingest.store import DatasetStore

        store = DatasetStore(root=tmp_path)
        store.save("pert-fixture", perturbation_adata)

        target_genes = ["GENE00", "GENE01"]
        result = run_vcc_eval(
            "pert-fixture",
            target_genes,
            store_root=tmp_path,
        )

        assert "dataset_id" in result
        assert "target_genes" in result
        assert result["target_genes"] == target_genes
        assert "pert-fixture" in result["dataset_id"]

    def test_predict_called_directly_not_via_agent(self, perturbation_adata, tmp_path):
        """run_vcc_eval must import perturbation.pipeline.predict -- not agent/tools.py.

        This is verified structurally: the function is importable and callable without
        any agent/MCP infrastructure (no claude_agent_sdk, no event loop, no tool
        call overhead).
        """
        from benchmark.vcc_eval import run_vcc_eval
        from ingest.store import DatasetStore

        store = DatasetStore(root=tmp_path)
        store.save("pert-fixture", perturbation_adata)

        # If run_vcc_eval internally called agent/tools.py's predict_perturbation_tool,
        # it would require an async event loop and tool-calling machinery.  The fact
        # that this plain synchronous call completes proves the direct-call invariant.
        result = run_vcc_eval(
            "pert-fixture",
            ["GENE00"],
            store_root=tmp_path,
        )
        assert isinstance(result, dict)
        assert result["predictor_metrics"]["mae"] >= 0.0
