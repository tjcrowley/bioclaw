"""predict() -- Phase 5, Plan 05-03 (PERT-01/PERT-02 composition).

Composes LinearAdditivePerturbationModel (perturbation/model.py) and
naive_baseline_predict (perturbation/baseline.py) into a single
PerturbationSummary result, mirroring annotation/pipeline.py::annotate()'s
established load-from-store + unconditional-baseline pattern.

PERT-02 closure: `predict()` calls `naive_baseline_predict()` UNCONDITIONALLY
in the same code order that `annotate()` calls `baseline_annotate()` --
before the model's own prediction, regardless of whether the model call
succeeds.  No code path through this module produces a result that omits
`baseline_call`.

PERT-01 closure (composition point): this function is the single entrypoint
where the "as a tool" requirement is satisfied -- `pipeline.predict()` gives
`predict_perturbation_tool` in `agent/tools.py` a typed,
store-integrated boundary to call, exactly matching the Phase 3/4 pattern
(analyze/annotate -> analyze_dataset_tool/annotate_cell_type_tool).

Downstream plans (05-04/05-05) import this module by path:
    from perturbation.pipeline import predict
"""

from __future__ import annotations

import asyncio
import tempfile
from dataclasses import asdict
from pathlib import Path

from annotation.fm_client import ensure_worker_compatible_h5ad
from ingest.store import DatasetStore

from perturbation.baseline import naive_baseline_predict
from perturbation.ensembl import validate_ensembl_ids
from perturbation.geneformer_client import call_geneformer_perturb
from perturbation.model import fit_from_adata
from perturbation.summary import (
    GeneformerPerturbationSummary,
    PerturbationCall,
    PerturbationSummary,
)


def predict(
    name: str,
    target_gene: str,
    version: int | None = None,
    store_root: str | Path = "data",
    target_gene_col: str = "target_gene",
    control_pert: str = "non-targeting",
) -> tuple[str, dict]:
    """Load dataset, predict post-perturbation expression using both model and baseline.

    Mirrors `annotation/pipeline.py::annotate()`'s store-load entrypoint shape:
    - Loads the named/versioned dataset from the store.
    - Computes the LinearAdditivePerturbationModel prediction (model_call).
    - Computes Arc Institute's naive perturbation-mean baseline (baseline_call)
      UNCONDITIONALLY, same code-order pattern as `annotate()`'s unconditional
      `baseline_annotate()` call -- no `if` gate, no try/except around it.
    - Returns `(dataset_id, summary_dict)` where summary_dict is the `asdict()`
      of a `PerturbationSummary` with both `model_call` and `baseline_call` set.

    Args:
        name: Dataset name as registered in the DatasetStore.
        target_gene: The perturbation target gene to predict.  Must be present
            in the dataset's obs[target_gene_col] column.
        version: Dataset version to load (int), or None for the latest version.
        store_root: Root directory of the DatasetStore (overridable for tests).
        target_gene_col: obs column identifying each cell's perturbation label.
            Defaults to "target_gene" (cell-eval DEFAULT_PERT_COL).
        control_pert: Label identifying control (non-perturbed) cells.
            Defaults to "non-targeting" (cell-eval DEFAULT_CTRL).

    Returns:
        (dataset_id, summary_dict) where:
        - dataset_id is "{name}@{version}" or "{name}@(latest)".
        - summary_dict is the `dataclasses.asdict()` of a PerturbationSummary
          with both model_call and baseline_call populated.

    Raises:
        KeyError: if name/version is not found in the store (propagated from
            DatasetStore.load, not swallowed -- matches annotate()'s behaviour).
        ValueError: if target_gene has no matching cells in the dataset's
            obs[target_gene_col] (propagated from naive_baseline_predict or
            from model.predict's KeyError path).
    """
    store = DatasetStore(root=store_root)
    adata = store.load(name, version)
    dataset_id = f"{name}@{version if version is not None else '(latest)'}"

    # Fit the LinearAdditivePerturbationModel from the loaded AnnData.
    model, control_mean = fit_from_adata(
        adata,
        target_gene_col=target_gene_col,
        control_token=control_pert,
    )

    # Model prediction (linear additive).
    model_call = PerturbationCall(
        method="linear_additive",
        target_gene=target_gene,
        predicted_expression=list(model.predict(control_mean, target_gene)),
    )

    # Naive baseline (PERT-02): UNCONDITIONAL call -- same code order pattern
    # as annotate()'s unconditional baseline_annotate() call.  No try/except,
    # no if-gate.  baseline_call is ALWAYS present in the returned summary.
    baseline_call = naive_baseline_predict(
        adata,
        target_gene,
        pert_col=target_gene_col,
        control_pert=control_pert,
    )

    summary = PerturbationSummary(
        dataset_id=dataset_id,
        target_gene=target_gene,
        gene_names=list(adata.var_names),
        model_call=model_call,
        baseline_call=baseline_call,
    )
    return dataset_id, asdict(summary)


async def predict_geneformer(
    name: str,
    target_gene: str,
    version: int | None = None,
    store_root: str | Path = "data",
) -> tuple[str, dict]:
    """Load dataset, run Geneformer's real four-step in-silico-perturbation
    pipeline against the isolated `geneformer_worker/` environment, and
    return a ranked-by-cosine-shift gene list (FM-02).

    Mirrors `predict()`'s store-load entrypoint shape, but:
    - Validates Ensembl IDs (`validate_ensembl_ids()`) unconditionally,
      before anything else touches the worker boundary; its `ValueError` is
      propagated uncaught (matches `predict()`'s existing
      propagate-don't-swallow convention).
    - Resolves the target gene's Ensembl ID server-side (never asked of the
      LLM/user directly) via `adata.var["ensembl_id"]`.
    - Dispatches the blocking, potentially multi-hour subprocess call via
      `asyncio.to_thread()` (Pitfall 3), mirroring `ingest/census.py`'s
      existing `asyncio.to_thread()` precedent for blocking I/O in this
      codebase, so a long-running Geneformer call never blocks the agent
      session's event loop.

    Args:
        name: Dataset name as registered in the DatasetStore.
        target_gene: The perturbation target gene to predict (must be
            present in `adata.var_names`).
        version: Dataset version to load (int), or None for the latest
            version.
        store_root: Root directory of the DatasetStore (overridable for
            tests).

    Returns:
        (dataset_id, summary_dict) where summary_dict is the
        `dataclasses.asdict()` of a `GeneformerPerturbationSummary`.

    Raises:
        KeyError: if name/version is not found in the store (propagated
            from DatasetStore.load), or if target_gene is not present in
            adata.var_names.
        ValueError: if no Ensembl-ID-shaped gene identifier column is found
            (propagated from validate_ensembl_ids).
        RuntimeError: if the Geneformer worker subprocess fails or times
            out (propagated from call_geneformer_perturb).
    """
    store = DatasetStore(root=store_root)
    adata = store.load(name, version)
    dataset_id = f"{name}@{version if version is not None else '(latest)'}"

    # Validate (and alias into adata.var["ensembl_id"]) unconditionally,
    # before anything else touches the worker boundary -- per the roadmap's
    # explicit "validated... before inference runs" wording.
    validate_ensembl_ids(adata)

    # Resolve the target gene's Ensembl ID server-side -- never exposed as
    # an LLM-facing parameter the agent could get wrong.
    if target_gene not in adata.var_names:
        raise KeyError(f"target_gene {target_gene!r} not found in dataset")
    target_ensembl_id = str(adata.var.loc[target_gene, "ensembl_id"])

    ensure_worker_compatible_h5ad(adata)

    with tempfile.TemporaryDirectory() as tmp_dir:
        h5ad_path = Path(tmp_dir) / "query.h5ad"
        adata.write_h5ad(h5ad_path)

        # Dispatch the blocking, potentially multi-hour subprocess call off
        # the event loop (Pitfall 3).
        call = await asyncio.to_thread(
            call_geneformer_perturb, h5ad_path, target_gene, target_ensembl_id
        )

    summary = GeneformerPerturbationSummary(
        dataset_id=dataset_id, target_gene=target_gene, call=call
    )
    return dataset_id, asdict(summary)
