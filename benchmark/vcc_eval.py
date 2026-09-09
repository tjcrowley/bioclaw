"""compute_vcc_metrics() / run_vcc_eval() -- Phase 5, Plan 05-04 (VCC-02).

Provides a thin, official wrapper around Arc Institute's cell_eval.MetricsEvaluator
for PDS/DES/MAE computation (compute_vcc_metrics), and a direct-call harness that
invokes perturbation.pipeline.predict() per target gene without going through the
agent/MCP tool-calling loop (run_vcc_eval).

Per 05-RESEARCH.md's Don't Hand-Roll section: all three VCC-02 metrics (MAE, PDS,
DES) are computed by cell_eval.MetricsEvaluator exclusively -- no reimplementation
of any formula appears here.  This module's only genuinely new work is the plumbing:
calling the predictor directly, assembling AnnData objects cell-eval expects.

Real cell_eval.MetricsEvaluator API (introspected against the installed package,
2026-09-09 -- supersedes 05-RESEARCH.md's research sketch where they diverge):

Constructor:
    MetricsEvaluator(
        adata_pred: AnnData | str | None,
        adata_real: AnnData | str,
        de_pred: pl.DataFrame | str | None = None,
        de_real: pl.DataFrame | str | None = None,
        control_pert: str = "non-targeting",
        pert_col: str = "target",          # DEFAULT IS "target", not "target_gene"
        num_threads: int = -1,
        outdir: str = "./cell-eval-outdir",
        allow_discrete: bool = False,
        prefix: str | None = None,
        pdex_kwargs: dict | None = None,
        skip_de: bool = False,
    )

    NOTE: Both adata_pred and adata_real MUST contain rows with the control label
    in obs[pert_col] -- MetricsEvaluator raises ValueError if control is absent.

compute(profile="vcc") return shape:
    Returns (results: pl.DataFrame, agg_results: pl.DataFrame).
    - results: per-perturbation DataFrame, columns:
        ["perturbation", "overlap_at_N", "mae", "discrimination_score_l1"]
      One row per target gene (control excluded).
    - agg_results: aggregate statistics (mean/std/min/max etc.) over all rows.
    VCC profile metric set (from VCC_METRICS in cell_eval._pipeline._runner):
        "mae"                    -> MAE  (0.0 = perfect, higher = worse)
        "discrimination_score_l1" -> PDS (1.0 = perfect, lower = worse)
        "overlap_at_N"           -> DES (0.0 to 1.0, higher = better)

compute_vcc_metrics() normalises this to a stable plain dict:
    {"mae": float, "pds": float, "des": float}
using the mean over all per-perturbation rows (so callers always get one scalar
per metric regardless of how many target genes were evaluated).

Downstream plans import:
    from benchmark.vcc_eval import compute_vcc_metrics, run_vcc_eval
"""

from __future__ import annotations

import tempfile
from pathlib import Path
from typing import TYPE_CHECKING

import numpy as np
import pandas as pd
import scipy.sparse as sp

if TYPE_CHECKING:
    from anndata import AnnData


def compute_vcc_metrics(
    adata_pred: "AnnData",
    adata_real: "AnnData",
    pert_col: str = "target_gene",
    control_pert: str = "non-targeting",
    num_threads: int = -1,
    outdir: str | None = None,
    allow_discrete: bool = False,
) -> dict:
    """Compute VCC benchmark metrics using cell_eval.MetricsEvaluator.

    Wraps Arc Institute's official MetricsEvaluator to produce PDS, DES, and MAE
    exactly as the VCC competition scores them.  No metric formula is reimplemented
    here -- computation is delegated entirely to cell_eval.

    Both adata_pred and adata_real must:
    - Have matching var_names (same gene set, same order).
    - Have obs[pert_col] populated with perturbation labels.
    - Include at least one row with obs[pert_col] == control_pert; MetricsEvaluator
      validates this and raises ValueError if the control row is absent.

    For raw integer count fixtures, pass allow_discrete=True to prevent
    MetricsEvaluator from applying normalize_total + log1p to already-integer data.
    Real VCC data (already log-normalized) does not need this flag.

    Args:
        adata_pred: Predicted expression AnnData.  One row per condition
            (including the control).  obs[pert_col] must match adata_real's labels.
        adata_real: Ground-truth expression AnnData.  Same shape requirements.
        pert_col: obs column identifying each row's perturbation label.
            Defaults to "target_gene" (cell-eval DEFAULT_PERT_COL).
        control_pert: Label identifying the control/non-perturbed condition.
            Defaults to "non-targeting" (cell-eval DEFAULT_CTRL).
        num_threads: Thread count for parallel DE computation.  -1 = all CPUs.
        outdir: Output directory for cell-eval's CSV files.  If None (default),
            a TemporaryDirectory is created and cleaned up automatically, so
            callers that only need the returned dict don't have to manage files.
        allow_discrete: Passed through to MetricsEvaluator.  Set True for raw
            integer count data (fixtures); False (default) for log-normalized data.

    Returns:
        dict with exactly three keys mapping to float scalars:
        - "mae":  Mean Absolute Error, averaged over all target genes.
                  Lower is better; 0.0 = perfect prediction.
        - "pds":  Perturbation Discrimination Score (discrimination_score_l1),
                  averaged over all target genes.
                  Higher is better; 1.0 = perfect discrimination.
        - "des":  Differential Expression Score (overlap_at_N),
                  averaged over all target genes.
                  Higher is better.
        The internal cell_eval column names (discrimination_score_l1, overlap_at_N)
        are mapped to these stable short keys so downstream plans (05-05's report)
        have one consistent shape to work against regardless of cell-eval's naming.

    Raises:
        ValueError: if MetricsEvaluator's validation fails (e.g., control label
            absent, shape mismatch, pert_col missing from obs).
    """
    from cell_eval import MetricsEvaluator

    if outdir is not None:
        _tmpdir = None
        _outdir = outdir
    else:
        _tmpdir = tempfile.TemporaryDirectory()
        _outdir = _tmpdir.name

    try:
        evaluator = MetricsEvaluator(
            adata_pred=adata_pred,
            adata_real=adata_real,
            control_pert=control_pert,
            pert_col=pert_col,
            num_threads=num_threads,
            outdir=_outdir,
            allow_discrete=allow_discrete,
        )
        # write_csv=False: we only need the in-memory DataFrames, not CSV files.
        results, _agg = evaluator.compute(profile="vcc", write_csv=False)
    finally:
        if _tmpdir is not None:
            _tmpdir.cleanup()

    # results is a Polars DataFrame with columns:
    #   perturbation, overlap_at_N, mae, discrimination_score_l1
    # (one row per non-control perturbation).
    # Normalise to a plain dict of mean-over-perturbations scalars.
    mae = float(results["mae"].mean())
    pds = float(results["discrimination_score_l1"].mean())
    des = float(results["overlap_at_N"].mean())

    return {"mae": mae, "pds": pds, "des": des}


def run_vcc_eval(
    name: str,
    target_genes: list[str],
    version: int | None = None,
    store_root: str | Path = "data",
    pert_col: str = "target_gene",
    control_pert: str = "non-targeting",
) -> dict:
    """Benchmark harness: compute VCC metrics for predictor and naive baseline.

    Calls perturbation.pipeline.predict() DIRECTLY for each target gene -- no
    agent/MCP tool-calling loop, no LLM tokens burned per prediction.  This is
    VCC-02's core requirement: hundreds of held-out perturbations must be
    evaluatable with deterministic, low-latency Python function calls.

    The returned dict is ready for Plan 05-05's side-by-side report:
        predictor_metrics  -- LinearAdditivePerturbationModel on the held-out data
        baseline_metrics   -- Arc Institute naive baseline (build_base_mean_adata)

    Workflow:
    1. Loads the stored dataset once to extract ground-truth per-gene means
       (adata_real). Each target gene contributes one row: the mean expression of
       all cells with obs[pert_col] == target_gene (pseudobulk, same logic as
       fit_from_adata in perturbation/model.py).
    2. For each target_gene, calls perturbation.pipeline.predict() directly to
       obtain (dataset_id, summary_dict) -- summary_dict has both 'model_call' and
       'baseline_call', each with 'predicted_expression'.
    3. Assembles three single-row-per-gene AnnData objects:
         adata_pred_model    -- model's predicted expression per target gene
         adata_pred_baseline -- naive baseline's predicted expression per target gene
         adata_real          -- ground-truth mean expression per target gene
       All three include a "non-targeting" control row so MetricsEvaluator's
       validation passes.
    4. Calls compute_vcc_metrics() twice (model vs. baseline), returns both.

    Args:
        name: Dataset name in the DatasetStore.
        target_genes: List of perturbation target gene names to evaluate.
        version: Dataset version (int), or None for latest.
        store_root: Root directory of the DatasetStore.
        pert_col: obs column identifying perturbation labels in the stored dataset.
        control_pert: Label for control (non-perturbed) cells.

    Returns:
        {
            "dataset_id": str,            # e.g. "my-dataset@1" or "my-dataset@(latest)"
            "target_genes": list[str],    # as provided
            "predictor_metrics": dict,    # {"mae": float, "pds": float, "des": float}
            "baseline_metrics": dict,     # {"mae": float, "pds": float, "des": float}
        }
    """
    from anndata import AnnData

    from ingest.store import DatasetStore
    from perturbation.pipeline import predict

    # 1. Load ground-truth dataset once.
    store = DatasetStore(root=store_root)
    adata = store.load(name, version)
    dataset_id = f"{name}@{version if version is not None else '(latest)'}"

    # Densify X for pseudobulk arithmetic (mirrors fit_from_adata / baseline_annotate).
    X = adata.X
    if sp.issparse(X):
        X = X.toarray()
    X = np.asarray(X, dtype=float)
    labels = adata.obs[pert_col]
    gene_names = list(adata.var_names)

    # Compute ground-truth per-gene means (pseudobulk).
    # We use the same approach as fit_from_adata: mean over cells for each label.
    real_rows: list[np.ndarray] = []
    for tg in target_genes:
        mask = (labels == tg).values
        if not mask.any():
            raise ValueError(
                f"run_vcc_eval: target_gene {tg!r} has no cells in "
                f"adata.obs[{pert_col!r}] of dataset {dataset_id!r}."
            )
        real_rows.append(X[mask].mean(axis=0))

    # Control mean row for the control row required by MetricsEvaluator.
    ctrl_mask = (labels == control_pert).values
    if not ctrl_mask.any():
        raise ValueError(
            f"run_vcc_eval: control_pert {control_pert!r} not found in "
            f"adata.obs[{pert_col!r}] of dataset {dataset_id!r}."
        )
    ctrl_mean = X[ctrl_mask].mean(axis=0)

    # 2. Call predict() directly per target gene (bypasses agent/MCP entirely).
    model_rows: list[np.ndarray] = []
    baseline_rows: list[np.ndarray] = []

    for tg in target_genes:
        _did, summary = predict(
            name,
            tg,
            version=version,
            store_root=store_root,
            target_gene_col=pert_col,
            control_pert=control_pert,
        )
        model_rows.append(np.asarray(summary["model_call"]["predicted_expression"], dtype=float))
        baseline_rows.append(np.asarray(summary["baseline_call"]["predicted_expression"], dtype=float))

    # 3. Assemble AnnData objects: one row per target gene + one control row.
    #    MetricsEvaluator requires the control label to appear in obs[pert_col].
    all_labels = [control_pert] + list(target_genes)
    obs = pd.DataFrame({pert_col: all_labels}, index=all_labels)
    var = pd.DataFrame(index=gene_names)

    def _build_adata(rows: list[np.ndarray]) -> "AnnData":
        # Stack [ctrl_mean] + per-gene rows into shape (1+n_genes, n_vars)
        mat = np.stack([ctrl_mean] + rows, axis=0)
        return AnnData(
            X=sp.csr_matrix(mat),
            obs=obs.copy(),
            var=var.copy(),
        )

    adata_real_eval = _build_adata(real_rows)
    adata_pred_model = _build_adata(model_rows)
    adata_pred_baseline = _build_adata(baseline_rows)

    # 4. Compute metrics via the official MetricsEvaluator wrapper.
    predictor_metrics = compute_vcc_metrics(
        adata_pred_model,
        adata_real_eval,
        pert_col=pert_col,
        control_pert=control_pert,
        allow_discrete=True,
    )
    baseline_metrics = compute_vcc_metrics(
        adata_pred_baseline,
        adata_real_eval,
        pert_col=pert_col,
        control_pert=control_pert,
        allow_discrete=True,
    )

    return {
        "dataset_id": dataset_id,
        "target_genes": list(target_genes),
        "predictor_metrics": predictor_metrics,
        "baseline_metrics": baseline_metrics,
    }
