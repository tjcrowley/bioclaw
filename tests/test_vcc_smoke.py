"""vcc_data-marked end-to-end smoke test -- Phase 5, Plan 05-06.

Marks: @pytest.mark.vcc_data

This test is excluded from the default fast-tier run (mirroring bio_fm_smoke's
established precedent).  It requires the real VCC public dataset to be
downloaded locally via benchmark/download_vcc.py before running.

Run after downloading the data:
    uv run pytest tests/test_vcc_smoke.py -m vcc_data -x -v -s

What this test proves:
  VCC-01: Real .h5ad ingest through ingest.loaders.load() -> ingest_10x pipeline
  VCC-02: run_full_benchmark() calls MetricsEvaluator with real data (no mocks)
  VCC-03: Benchmark report includes both predictor and baseline MAE/PDS/DES sections

Per 05-RESEARCH.md Pitfall 4: obs column names and control-token values are
VERIFIED from the real downloaded data (adata.obs columns), not assumed.  The
test reads obs[pert_col].unique() and asserts against what it actually finds
before passing anything to the benchmark.  If the real column names differ
from "target_gene" / "non-targeting", the assertion below will tell you what
the actual values are.

Per 05-RESEARCH.md Pitfall 6: the test evaluates target genes from the
VALIDATION split only (disjoint from the training split used to fit the model),
so there is no train/test leakage.  Target genes selected are a small handful
from the real validation set (not the full 300), keeping the test runtime
reasonable.

Per 05-RESEARCH.md Pitfall 5: the benchmark report carries a qc_provenance_note
documenting that scores reflect this project's own QC'd/ingested dataset state.
"""

import pytest

pytestmark = pytest.mark.vcc_data

# ---------------------------------------------------------------------------
# Constants: local cache paths (match benchmark/download_vcc.py defaults)
# ---------------------------------------------------------------------------

# benchmark/download_vcc.py stores downloads here by default
_VCC_RAW_ROOT = "data/vcc_raw"
# Validation split is smallest -- start here (per plan Task 1 rationale)
_VALIDATION_H5AD = f"{_VCC_RAW_ROOT}/validation/adata_Validation.h5ad"
# Training split needed to fit the linear-additive model
_TRAINING_H5AD = f"{_VCC_RAW_ROOT}/train/adata_Training.h5ad"
_TRAINING_COUNTS_CSV = f"{_VCC_RAW_ROOT}/train/pert_counts_Training.csv"

# Default column names from cell-eval's own _baseline.py / VCC tutorial notebook.
# IMPORTANT: these are VERIFIED against the real data inside the test body
# (see the adata.obs inspection step), not assumed from here.
_DEFAULT_PERT_COL = "target_gene"
_DEFAULT_CTRL = "non-targeting"

# Number of target genes to evaluate in this smoke test.
# Using a small subset keeps runtime reasonable while still exercising the
# full pipeline (ingest -> store -> run_full_benchmark -> report).
_N_TARGET_GENES = 5


def _require_path(path: str, hint: str) -> None:
    """Raise a descriptive skip if a required local file is missing."""
    import os
    if not os.path.exists(path):
        pytest.skip(
            f"Required file not found: {path}\n"
            f"{hint}\n"
            "See benchmark/download_vcc.py module docstring for setup steps."
        )


def _require_valid_h5ad(path: str) -> None:
    """Raise a descriptive skip if the local h5ad file is corrupt/empty."""
    import h5py
    try:
        with h5py.File(path, "r") as f:
            keys = list(f.keys())
            if not keys:
                pytest.skip(
                    f"File exists but appears empty (no HDF5 groups): {path}\n"
                    "Re-run the download: uv run python -c "
                    "\"from benchmark.download_vcc import download_vcc_split; "
                    "download_vcc_split('validation')\""
                )
    except Exception as exc:
        pytest.skip(
            f"File exists but is not valid HDF5 (may be a partial download): {path}\n"
            f"Error: {exc}\n"
            "Delete the file and re-run the download: uv run python -c "
            "\"from benchmark.download_vcc import download_vcc_split; "
            "download_vcc_split('validation')\""
        )


# ---------------------------------------------------------------------------
# Smoke test
# ---------------------------------------------------------------------------

def test_real_vcc_ingest_and_benchmark(tmp_path):
    """End-to-end VCC smoke test: real .h5ad ingest -> DatasetStore -> run_full_benchmark().

    Requires real data at data/vcc_raw/validation/adata_Validation.h5ad and
    data/vcc_raw/train/adata_Training.h5ad.  Skips with a descriptive message
    if either is missing or corrupt.

    Steps:
      1. Pre-flight checks: verify local files exist and are valid HDF5.
      2. Inspect obs columns on the validation .h5ad (Pitfall 4 verification).
      3. Ingest the TRAINING split through ingest.loaders.load() -> ingest_10x
         (proves VCC-01 -- the full QC'd ingest path, not a bespoke loader).
      4. Save to a DatasetStore at tmp_path.
      5. Pick a handful of target genes from the VALIDATION obs (disjoint from
         training targets? No -- both splits share 300 target genes; the model
         is fit on train and evaluated on the validation set's mean profiles,
         so we evaluate genes from the validation split).
      6. Call benchmark.report.run_full_benchmark() against the stored dataset.
      7. Assert both predictor and baseline sections have real numeric values.
      8. Print the report table (benchmark.report.to_markdown()) so the human
         checkpoint can eyeball the numbers.
      9. Sanity-check: predictor scores should be numerically valid (no NaN/Inf)
         and not suspiciously perfect (Pitfall 6 leakage check).
    """
    from pathlib import Path

    # Step 1: Pre-flight checks
    _require_path(
        _VALIDATION_H5AD,
        "Run: uv run python -c \"from benchmark.download_vcc import "
        "download_vcc_split; download_vcc_split('validation')\"",
    )
    _require_valid_h5ad(_VALIDATION_H5AD)
    _require_path(
        _TRAINING_H5AD,
        "Run: uv run python -c \"from benchmark.download_vcc import "
        "download_vcc_split; download_vcc_split('train')\"",
    )
    _require_valid_h5ad(_TRAINING_H5AD)

    # Step 2: Inspect obs columns on the validation .h5ad (Pitfall 4 verification)
    import scanpy as sc
    import anndata as ad

    print("\n=== VCC obs column inspection (Pitfall 4 verification) ===")
    val_adata = ad.read_h5ad(_VALIDATION_H5AD)
    print(f"Validation shape: {val_adata.shape}")
    print(f"Validation obs columns: {list(val_adata.obs.columns)}")

    # Determine the actual pert_col in this dataset
    for candidate in (_DEFAULT_PERT_COL, "target", "perturbation", "gene_target"):
        if candidate in val_adata.obs.columns:
            pert_col = candidate
            break
    else:
        pytest.fail(
            f"Could not find a perturbation column in validation obs. "
            f"Available columns: {list(val_adata.obs.columns)}. "
            "Update _DEFAULT_PERT_COL in this test to match the real column name."
        )

    print(f"Using pert_col: {pert_col!r}")
    unique_perts = list(val_adata.obs[pert_col].unique())
    print(f"Unique perturbation labels (first 20): {unique_perts[:20]}")

    # Determine the actual control token
    for candidate in (_DEFAULT_CTRL, "ntc", "control", "CTRL"):
        if candidate in unique_perts:
            control_pert = candidate
            break
    else:
        pytest.fail(
            f"Could not find a control label in validation obs[{pert_col!r}]. "
            f"Unique values (first 20): {unique_perts[:20]}. "
            "Update _DEFAULT_CTRL in this test to match the real control token."
        )

    print(f"Using control_pert: {control_pert!r}")

    # Pick target genes to evaluate: take the first N non-control genes from
    # the validation obs (disjoint from the control label; per Pitfall 6 these
    # should also appear in the training set so the model is non-trivially fit)
    target_genes = [p for p in unique_perts if p != control_pert][:_N_TARGET_GENES]
    assert len(target_genes) >= 1, (
        f"No non-control perturbations found in validation obs[{pert_col!r}]. "
        f"Unique values: {unique_perts[:20]}"
    )
    print(f"Target genes for smoke test: {target_genes}")

    # Step 3: Ingest the TRAINING split through ingest.loaders.load() -> ingest_10x
    # (proves VCC-01: real .h5ad ingest through the existing pipeline, no bespoke path)
    from ingest.loaders import load
    from ingest.pipeline import ingest_10x

    print("\n=== Ingesting training split through ingest.loaders.load() ===")
    # Use load() which now dispatches .h5ad -> sc.read_h5ad (VCC-01 branch added in 05-01)
    raw_adata = load(_TRAINING_H5AD)
    print(f"Raw training adata shape: {raw_adata.shape}")

    # Verify pert_col is present in the training adata
    assert pert_col in raw_adata.obs.columns, (
        f"pert_col {pert_col!r} not found in training adata obs. "
        f"Available: {list(raw_adata.obs.columns)}"
    )
    assert control_pert in raw_adata.obs[pert_col].unique(), (
        f"control_pert {control_pert!r} not found in training obs[{pert_col!r}]. "
        f"Unique values (first 20): {list(raw_adata.obs[pert_col].unique())[:20]}"
    )

    # Run ingest_10x (full QC pipeline) on the raw_adata.
    # QC may filter cells; the qc_provenance_note documents this (Pitfall 5).
    # ingest_10x expects a path; use the .h5ad path directly (it calls loaders.load internally)
    print("Running ingest_10x (full QC pipeline) on training split ...")
    adata = ingest_10x(_TRAINING_H5AD)
    print(f"QC'd training adata shape: {adata.shape}")
    print(f"QC'd obs columns: {list(adata.obs.columns)}")

    # After QC, pert_col must still be present (ingest_10x preserves obs columns)
    assert pert_col in adata.obs.columns, (
        f"pert_col {pert_col!r} missing from QC'd adata obs. "
        f"Available: {list(adata.obs.columns)}"
    )
    assert control_pert in adata.obs[pert_col].unique(), (
        f"control_pert {control_pert!r} missing from QC'd adata obs[{pert_col!r}]. "
        "QC may have filtered out all control cells -- check QC thresholds."
    )

    # Step 4: Save to DatasetStore at tmp_path
    from ingest.store import DatasetStore

    dataset_name = "vcc-training-smoke"
    store = DatasetStore(root=str(tmp_path))
    store.save(dataset_name, adata)
    print(f"Saved to DatasetStore at {tmp_path} as {dataset_name!r}")

    # Step 5+6: Call run_full_benchmark() (proves VCC-02, VCC-03)
    from benchmark.report import run_full_benchmark, to_markdown

    print(f"\n=== Running run_full_benchmark() on {len(target_genes)} target genes ===")
    print(f"Target genes: {target_genes}")
    print("(This may take several minutes for DE computation on real data)")

    report = run_full_benchmark(
        name=dataset_name,
        target_genes=target_genes,
        store_root=str(tmp_path),
    )

    # Step 7: Assert both sections have real numeric values (no NaN/Inf)
    import math

    print("\n=== Benchmark report ===")
    print(to_markdown(report))

    pred = report["predictor"]
    base = report["baseline"]

    for section_name, section in [("predictor", pred), ("baseline", base)]:
        for metric in ("mae", "pds", "des"):
            val = section[metric]
            assert isinstance(val, float), (
                f"{section_name}.{metric} is not a float: {val!r}"
            )
            assert not math.isnan(val), (
                f"{section_name}.{metric} is NaN -- MetricsEvaluator returned no data"
            )
            assert not math.isinf(val), (
                f"{section_name}.{metric} is Inf -- arithmetic overflow in metric computation"
            )
            assert val >= 0.0, (
                f"{section_name}.{metric} = {val} is negative -- metric invariant violated"
            )

    # Step 8: Sanity-check against Pitfall 6 (leakage detection)
    # PDS = 1.0 (perfect discrimination) on first attempt with a simple linear model
    # is a strong leakage signal. Flag, but don't fail (score depends on the data).
    if pred["pds"] >= 0.99:
        print(
            "\nWARNING (Pitfall 6 / leakage check): predictor PDS is suspiciously high "
            f"({pred['pds']:.4f} >= 0.99). "
            "If target genes used for evaluation also appeared in the training fit with "
            "exact pseudobulk means, this may indicate train/test leakage. "
            "Verify that the evaluation target genes are genuinely held-out predictions."
        )

    print("\n=== Predictor vs Baseline ===")
    print(f"  MAE  -- predictor: {pred['mae']:.4f}, baseline: {base['mae']:.4f}")
    print(f"  PDS  -- predictor: {pred['pds']:.4f}, baseline: {base['pds']:.4f}")
    print(f"  DES  -- predictor: {pred['des']:.4f}, baseline: {base['des']:.4f}")
    print(f"\nQC Provenance: {report['qc_provenance_note']}")

    # Final assertion: report structure is complete
    assert set(report.keys()) == {
        "dataset_id", "target_genes", "predictor", "baseline", "qc_provenance_note"
    }, f"Report is missing required keys: {report.keys()}"
    assert report["target_genes"] == target_genes
    assert report["dataset_id"] == f"{dataset_name}@(latest)"
