"""Tests for benchmark/report.py -- Plan 05-05 (VCC-03).

Tests are structured in two groups:

Group 1 (Task 1): build_benchmark_report() -- structurally baseline-enforced report.
  - Returns a report with predictor/baseline sections, each having all three
    metric keys (mae/pds/des) from compute_vcc_metrics().
  - Raises ValueError when baseline_metrics is None, empty, or missing a required key.
  - Raises ValueError when predictor_metrics is None, empty, or missing a required key.
  - The returned report carries the qc_provenance_note verbatim.

Group 2 (Task 2): run_full_benchmark() -- single top-level orchestration entrypoint.
  - Persists perturbation_adata into a DatasetStore at tmp_path, calls
    run_full_benchmark() with real fixtures, asserts the returned report has both
    predictor/baseline sections fully populated.  This is the exact function Plan
    05-06 will call against real VCC data.

Metric keys (normalized by benchmark/vcc_eval.py::compute_vcc_metrics()):
    {"mae": float, "pds": float, "des": float}
"""

from __future__ import annotations

import pytest

# Minimal valid metric dicts (all three required keys present)
_VALID_PREDICTOR = {"mae": 0.1, "pds": 0.9, "des": 0.8}
_VALID_BASELINE = {"mae": 0.3, "pds": 0.6, "des": 0.5}


# ---------------------------------------------------------------------------
# Task 1 tests: build_benchmark_report()
# ---------------------------------------------------------------------------


class TestBuildBenchmarkReport:
    """Tests for build_benchmark_report() -- structurally baseline-enforced."""

    def test_returns_report_with_all_three_metrics_for_predictor_and_baseline(self):
        """Report must include MAE, PDS, DES for BOTH predictor and baseline sections."""
        from benchmark.report import build_benchmark_report

        report = build_benchmark_report(
            predictor_metrics=_VALID_PREDICTOR.copy(),
            baseline_metrics=_VALID_BASELINE.copy(),
            dataset_id="x@1",
            target_genes=["GENE00"],
        )

        required_keys = {"mae", "pds", "des"}

        # Predictor section
        assert "predictor" in report, f"Report missing 'predictor' section: {list(report.keys())}"
        pred = report["predictor"]
        assert required_keys.issubset(pred.keys()), (
            f"predictor section missing keys: {required_keys - set(pred.keys())}"
        )

        # Baseline section
        assert "baseline" in report, f"Report missing 'baseline' section: {list(report.keys())}"
        base = report["baseline"]
        assert required_keys.issubset(base.keys()), (
            f"baseline section missing keys: {required_keys - set(base.keys())}"
        )

    def test_raises_value_error_on_none_baseline(self):
        """build_benchmark_report must raise ValueError when baseline_metrics is None."""
        from benchmark.report import build_benchmark_report

        with pytest.raises(ValueError):
            build_benchmark_report(
                predictor_metrics=_VALID_PREDICTOR.copy(),
                baseline_metrics=None,
                dataset_id="x@1",
                target_genes=["GENE00"],
            )

    def test_raises_value_error_on_empty_baseline(self):
        """build_benchmark_report must raise ValueError when baseline_metrics is empty dict."""
        from benchmark.report import build_benchmark_report

        with pytest.raises(ValueError):
            build_benchmark_report(
                predictor_metrics=_VALID_PREDICTOR.copy(),
                baseline_metrics={},
                dataset_id="x@1",
                target_genes=["GENE00"],
            )

    def test_raises_value_error_on_baseline_missing_one_key(self):
        """build_benchmark_report must raise ValueError when baseline_metrics is missing a key."""
        from benchmark.report import build_benchmark_report

        # Missing 'des'
        incomplete_baseline = {"mae": 0.3, "pds": 0.6}

        with pytest.raises(ValueError):
            build_benchmark_report(
                predictor_metrics=_VALID_PREDICTOR.copy(),
                baseline_metrics=incomplete_baseline,
                dataset_id="x@1",
                target_genes=["GENE00"],
            )

    def test_raises_value_error_on_none_predictor(self):
        """build_benchmark_report must raise ValueError when predictor_metrics is None."""
        from benchmark.report import build_benchmark_report

        with pytest.raises(ValueError):
            build_benchmark_report(
                predictor_metrics=None,
                baseline_metrics=_VALID_BASELINE.copy(),
                dataset_id="x@1",
                target_genes=["GENE00"],
            )

    def test_raises_value_error_on_empty_predictor(self):
        """build_benchmark_report must raise ValueError when predictor_metrics is empty dict."""
        from benchmark.report import build_benchmark_report

        with pytest.raises(ValueError):
            build_benchmark_report(
                predictor_metrics={},
                baseline_metrics=_VALID_BASELINE.copy(),
                dataset_id="x@1",
                target_genes=["GENE00"],
            )

    def test_raises_value_error_on_predictor_missing_one_key(self):
        """build_benchmark_report must raise ValueError when predictor_metrics is missing a key."""
        from benchmark.report import build_benchmark_report

        # Missing 'mae'
        incomplete_predictor = {"pds": 0.9, "des": 0.8}

        with pytest.raises(ValueError):
            build_benchmark_report(
                predictor_metrics=incomplete_predictor,
                baseline_metrics=_VALID_BASELINE.copy(),
                dataset_id="x@1",
                target_genes=["GENE00"],
            )

    def test_report_includes_qc_provenance_note_default(self):
        """Report must carry the default qc_provenance_note text verbatim."""
        from benchmark.report import build_benchmark_report, DEFAULT_QC_PROVENANCE_NOTE

        report = build_benchmark_report(
            predictor_metrics=_VALID_PREDICTOR.copy(),
            baseline_metrics=_VALID_BASELINE.copy(),
            dataset_id="x@1",
            target_genes=["GENE00"],
        )

        assert "qc_provenance_note" in report, (
            f"Report missing 'qc_provenance_note' field: {list(report.keys())}"
        )
        assert report["qc_provenance_note"] == DEFAULT_QC_PROVENANCE_NOTE, (
            f"qc_provenance_note text does not match expected default:\n"
            f"  got: {report['qc_provenance_note']!r}\n"
            f"  expected: {DEFAULT_QC_PROVENANCE_NOTE!r}"
        )

    def test_report_includes_custom_qc_provenance_note(self):
        """A custom qc_provenance_note passed by caller must appear verbatim in the report."""
        from benchmark.report import build_benchmark_report

        custom_note = "Custom provenance: validated against internal QC pipeline v2."

        report = build_benchmark_report(
            predictor_metrics=_VALID_PREDICTOR.copy(),
            baseline_metrics=_VALID_BASELINE.copy(),
            dataset_id="x@1",
            target_genes=["GENE00"],
            qc_provenance_note=custom_note,
        )

        assert report["qc_provenance_note"] == custom_note, (
            f"Expected custom provenance note, got: {report['qc_provenance_note']!r}"
        )

    def test_report_includes_dataset_id_and_target_genes(self):
        """Report must carry dataset_id and target_genes as provided."""
        from benchmark.report import build_benchmark_report

        target_genes = ["GENE00", "GENE01", "GENE02"]

        report = build_benchmark_report(
            predictor_metrics=_VALID_PREDICTOR.copy(),
            baseline_metrics=_VALID_BASELINE.copy(),
            dataset_id="my-dataset@3",
            target_genes=target_genes,
        )

        assert report["dataset_id"] == "my-dataset@3"
        assert report["target_genes"] == target_genes

    def test_to_markdown_renders_both_sections(self):
        """to_markdown() must produce a string with both predictor and baseline metric values."""
        from benchmark.report import build_benchmark_report, to_markdown

        report = build_benchmark_report(
            predictor_metrics=_VALID_PREDICTOR.copy(),
            baseline_metrics=_VALID_BASELINE.copy(),
            dataset_id="x@1",
            target_genes=["GENE00"],
        )

        md = to_markdown(report)
        assert isinstance(md, str), f"to_markdown() must return str, got {type(md)}"

        # Must include each metric name at least once
        for metric in ("MAE", "PDS", "DES"):
            assert metric in md, f"to_markdown() output missing metric name '{metric}': {md!r}"

        # Must include the provenance note
        assert "QC" in md or "provenance" in md.lower() or "Pitfall" in md, (
            f"to_markdown() output must reference QC provenance: {md!r}"
        )


# ---------------------------------------------------------------------------
# Task 2 tests: run_full_benchmark()
# ---------------------------------------------------------------------------


class TestRunFullBenchmark:
    """Tests for run_full_benchmark() -- single top-level orchestration entrypoint."""

    def test_returns_complete_report_with_both_sections(self, perturbation_adata, tmp_path):
        """run_full_benchmark must return a report with fully populated predictor and baseline."""
        from benchmark.report import run_full_benchmark
        from ingest.store import DatasetStore

        # Persist perturbation_adata into a tmp DatasetStore
        store = DatasetStore(root=tmp_path)
        store.save("pert-fixture", perturbation_adata)

        report = run_full_benchmark(
            "pert-fixture",
            ["GENE00", "GENE01"],
            store_root=tmp_path,
        )

        required_metric_keys = {"mae", "pds", "des"}

        assert "predictor" in report, f"Report missing 'predictor': {list(report.keys())}"
        assert required_metric_keys.issubset(report["predictor"].keys()), (
            f"predictor section missing keys: {required_metric_keys - set(report['predictor'].keys())}"
        )

        assert "baseline" in report, f"Report missing 'baseline': {list(report.keys())}"
        assert required_metric_keys.issubset(report["baseline"].keys()), (
            f"baseline section missing keys: {required_metric_keys - set(report['baseline'].keys())}"
        )

    def test_run_full_benchmark_includes_provenance_note(self, perturbation_adata, tmp_path):
        """run_full_benchmark must always carry qc_provenance_note."""
        from benchmark.report import run_full_benchmark
        from ingest.store import DatasetStore

        store = DatasetStore(root=tmp_path)
        store.save("pert-fixture", perturbation_adata)

        report = run_full_benchmark(
            "pert-fixture",
            ["GENE00"],
            store_root=tmp_path,
        )

        assert "qc_provenance_note" in report, (
            f"Report missing 'qc_provenance_note': {list(report.keys())}"
        )
        assert len(report["qc_provenance_note"]) > 0

    def test_run_full_benchmark_dataset_id_and_genes(self, perturbation_adata, tmp_path):
        """run_full_benchmark must carry dataset_id and target_genes in the returned report."""
        from benchmark.report import run_full_benchmark
        from ingest.store import DatasetStore

        store = DatasetStore(root=tmp_path)
        store.save("pert-fixture", perturbation_adata)

        target_genes = ["GENE00", "GENE01"]
        report = run_full_benchmark(
            "pert-fixture",
            target_genes,
            store_root=tmp_path,
        )

        assert "dataset_id" in report
        assert "target_genes" in report
        assert report["target_genes"] == target_genes
        assert "pert-fixture" in report["dataset_id"]

    def test_run_full_benchmark_single_call_no_wiring_needed(self, perturbation_adata, tmp_path):
        """run_full_benchmark is a single top-level call -- name + target_genes in, report out.

        This test verifies the exact call signature Plan 05-06 will use against
        real VCC data: store.save() then run_full_benchmark() is all that's needed.
        """
        from benchmark.report import run_full_benchmark
        from ingest.store import DatasetStore

        store = DatasetStore(root=tmp_path)
        store.save("pert-fixture", perturbation_adata)

        # Single-call entrypoint: no additional wiring needed beyond these two calls
        report = run_full_benchmark("pert-fixture", ["GENE00"], store_root=tmp_path)

        # Verify it's a complete, baseline-enforced report
        assert isinstance(report, dict)
        assert "predictor" in report
        assert "baseline" in report
        assert report["predictor"]["mae"] >= 0.0
        assert report["baseline"]["mae"] >= 0.0
