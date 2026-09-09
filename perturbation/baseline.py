"""naive_baseline_predict() -- Phase 5, Plan 05-03 (PERT-02).

Wraps `cell_eval.build_base_mean_adata` (Arc Institute's official naive
perturbation-mean baseline) so that Plan 05-03's `pipeline.predict()` can
include the baseline comparison unconditionally, without hand-rolling any
averaging logic.

Real API (introspected against the actually-installed `cell-eval` package,
2026-09-09 -- supersedes 05-RESEARCH.md Code Examples sketch):

    cell_eval.build_base_mean_adata(
        adata: AnnData | str,
        counts_df: pl.DataFrame | str | None = None,  # auto-built from adata if None
        pert_col: str = "target_gene",
        control_pert: str = "non-targeting",
        counts_col: str = "n_cells",
        as_delta: bool = False,
        allow_discrete: bool = False,
        output_path: str | None = None,
        output_de_path: str | None = None,
        num_threads: int = 1,
        pdex_kwargs: dict = {},
    ) -> AnnData

Return shape:
- Returns an AnnData whose obs column `pert_col` contains the perturbation
  labels (excluding control -- only perturbed conditions appear), and whose X
  holds the predicted expression vector for each row.
- Critically: every row's X value is the SAME global value -- the mean of all
  perturbation group means (not the per-target-gene mean).  The returned rows
  are labeled by `pert_col` to mirror the original adata structure, but all
  rows carry the same "naive best guess" expression vector regardless of which
  perturbation label they carry.

Divergence from 05-RESEARCH.md Code Examples sketch:
- The research sketch omitted `allow_discrete`.  Raw integer count AnnDatas
  (the fixture type used in all Phase 5 tests) require `allow_discrete=True`
  to prevent `build_base_mean_adata` from guessing the data is already
  log-normalized and producing nonsense.  Without this flag the function runs
  `sc.pp.normalize_total` + `sc.pp.log1p` on the input, which is correct for
  real VCC data but would leave integer fixtures in an inconsistent state.
  `naive_baseline_predict` always passes `allow_discrete=True` so the caller
  does not need to normalize beforehand.

Per 05-RESEARCH.md Pitfall 4: obs column "target_gene" and control token
"non-targeting" match cell-eval's DEFAULT_PERT_COL/DEFAULT_CTRL -- do not
rename without updating every Phase 5 test.

Downstream plans (05-04/05-05) import this module by path:
    from perturbation.baseline import naive_baseline_predict
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import numpy as np
import scipy.sparse as sp

import cell_eval

from perturbation.summary import PerturbationCall

if TYPE_CHECKING:
    from anndata import AnnData


def naive_baseline_predict(
    adata: "AnnData",
    target_gene: str,
    pert_col: str = "target_gene",
    control_pert: str = "non-targeting",
) -> PerturbationCall:
    """Return the Arc Institute naive perturbation-mean baseline prediction.

    Delegates entirely to `cell_eval.build_base_mean_adata` (Arc Institute's
    own official naive baseline implementation) rather than re-implementing any
    averaging logic.  This ensures that VCC benchmark scores produced by this
    function are directly comparable to Arc Institute's own reference numbers --
    per 05-RESEARCH.md Don't Hand-Roll.

    The baseline is the GLOBAL MEAN OF PERTURBATION GROUP MEANS (not the
    per-target-gene cell mean).  The same expression vector is returned
    regardless of which `target_gene` is queried, because `build_base_mean_adata`
    computes a single population-level 'naive best guess' and replicates it
    across all perturbation rows.  The `target_gene` argument is used only to:
    (a) validate that the gene has cells in `adata.obs[pert_col]` (raising
        ValueError if not), and
    (b) select the corresponding rows from the returned baseline AnnData (all
        rows within a label carry the same X value, so we take the first one).

    Args:
        adata: AnnData with raw or log-normalized expression in .X.  Must have
            obs[pert_col] populated with perturbation labels.
        target_gene: The perturbation label to query.  Must appear in
            adata.obs[pert_col] (excluding `control_pert`).
        pert_col: Column in adata.obs identifying each cell's perturbation
            condition.  Defaults to "target_gene" (cell-eval DEFAULT_PERT_COL).
        control_pert: Value in obs[pert_col] identifying control cells.
            Defaults to "non-targeting" (cell-eval DEFAULT_CTRL).

    Returns:
        PerturbationCall(method="naive_baseline", target_gene=target_gene,
        predicted_expression=[...]) where predicted_expression has length
        adata.n_vars and is aligned to adata.var_names.

    Raises:
        ValueError: if target_gene has no matching cells in adata.obs[pert_col].
            The error message includes target_gene's name so the caller can
            diagnose which gene was missing.
    """
    # Validate that target_gene exists in adata before calling cell_eval,
    # so we get a clear ValueError rather than a cryptic empty-adata downstream error.
    observed_labels = set(adata.obs[pert_col].unique())
    if target_gene not in observed_labels:
        raise ValueError(
            f"naive_baseline_predict: target_gene {target_gene!r} has no cells in "
            f"adata.obs[{pert_col!r}]. Observed labels: {sorted(observed_labels)}"
        )

    # Call Arc Institute's official naive baseline.
    # We pass a copy so that the in-place normalize_total/log1p that
    # _convert_to_normlog applies (when allow_discrete=False) does not mutate
    # the caller's adata.  allow_discrete=True is passed for raw-count fixtures;
    # real VCC data is already log-normalized and build_base_mean_adata's own
    # heuristic (guess_is_lognorm) will skip normalization when appropriate.
    baseline_adata = cell_eval.build_base_mean_adata(
        adata.copy(),
        pert_col=pert_col,
        control_pert=control_pert,
        allow_discrete=True,
    )

    # Extract the row(s) labeled with target_gene from the returned baseline adata.
    # All such rows carry the same X value (the global mean of perturbation group means),
    # so we take the first one.  Use .values on the boolean pandas Series before passing
    # it as a sparse matrix index -- scipy sparse indexing does not accept pandas Series.
    mask = (baseline_adata.obs[pert_col] == target_gene).values
    row_x = baseline_adata.X[mask][0]
    if sp.issparse(row_x):
        row_x = row_x.toarray().squeeze()
    row_x = np.asarray(row_x, dtype=float).ravel()

    return PerturbationCall(
        method="naive_baseline",
        target_gene=target_gene,
        predicted_expression=list(row_x),
    )
