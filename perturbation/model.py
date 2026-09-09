"""LinearAdditivePerturbationModel -- Phase 5, Plan 05-02 (PERT-01).

Implements a linear/additive perturbation predictor:
  - Exact lookup for genes seen during fit (control_mean + known shift vector).
  - Ridge-regression fallback for genes in gene_names but not in fit-time pert_means
    (feature = target gene's own control-expression value; per 05-RESEARCH.md Pattern 1).
  - KeyError for genes absent from gene_names entirely.

Also provides fit_from_adata(), an AnnData-facing convenience wrapper that
pseudobulks control vs. perturbed cells and returns (fitted_model, control_mean_vector)
for Plan 05-03's pipeline.predict() to call directly.

Downstream plans (05-03/05-04/05-05) import:
    from perturbation.model import LinearAdditivePerturbationModel, fit_from_adata
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import numpy as np
from sklearn.linear_model import Ridge

if TYPE_CHECKING:
    from anndata import AnnData


class LinearAdditivePerturbationModel:
    """Control-mean + learned per-gene additive shift predictor.

    For each perturbation gene seen during fit(), stores the shift vector
    (pert_mean - control_mean) directly. For genes in gene_names that were not
    used as perturbation targets during fit(), falls back to a Ridge regression
    whose single feature is the target gene's own control-population expression
    value (per 05-RESEARCH.md Pattern 1 / Open Question 3's simplest defensible
    choice).

    Args:
        alpha: Ridge regularization strength (default 1.0). Passed through to
            sklearn.linear_model.Ridge. Only used for the fallback regression.
    """

    def __init__(self, alpha: float = 1.0) -> None:
        self.alpha = alpha
        self._gene_names: list[str] | None = None
        self._gene_index: dict[str, int] | None = None
        self._control_mean: np.ndarray | None = None
        self._known_shifts: dict[str, np.ndarray] | None = None
        self._fallback_model: Ridge | None = None

    def fit(
        self,
        gene_names: list[str],
        control_mean: np.ndarray,
        pert_means: dict[str, np.ndarray],
    ) -> None:
        """Fit the model from pre-computed pseudobulk summaries.

        Args:
            gene_names: Ordered list of gene names. Defines the index used by
                predict() to locate a target gene's control-expression feature.
            control_mean: 1-D array of shape (n_genes,). Mean expression of
                control (non-targeting) cells.
            pert_means: Mapping from perturbation gene name to its 1-D mean
                expression array (shape (n_genes,)), computed over that
                perturbation's cells.

        Raises:
            ValueError: if gene_names is empty or arrays are mismatched in shape.
        """
        gene_names = list(gene_names)
        control_mean = np.asarray(control_mean, dtype=float)

        self._gene_names = gene_names
        self._gene_index = {g: i for i, g in enumerate(gene_names)}
        self._control_mean = control_mean

        # Compute shift vectors: pert_mean - control_mean for each known perturbation.
        self._known_shifts = {
            g: np.asarray(v, dtype=float) - control_mean
            for g, v in pert_means.items()
        }

        # Fit ridge fallback: X = (n_known_genes, 1) single-feature matrix where
        # X[i] = control_mean[index of pert_gene_i]; Y = (n_known_genes, n_genes)
        # where Y[i] = known shift vector for pert_gene_i.
        # This lets predict() estimate a shift for any gene in gene_names not seen
        # during fit by using that gene's control expression as the feature.
        known_genes = list(self._known_shifts.keys())
        if known_genes:
            X_fit = np.array(
                [control_mean[self._gene_index[g]] for g in known_genes],
                dtype=float,
            ).reshape(-1, 1)  # shape (n_known, 1)
            Y_fit = np.stack(
                [self._known_shifts[g] for g in known_genes], axis=0
            )  # shape (n_known, n_genes)
            self._fallback_model = Ridge(alpha=self.alpha)
            self._fallback_model.fit(X_fit, Y_fit)
        else:
            # No perturbations seen at all: fit a zero-intercept ridge on empty data.
            # Fallback will always predict zeros (no shift).
            self._fallback_model = Ridge(alpha=self.alpha)

    def predict(self, control_mean: np.ndarray, target_gene: str) -> np.ndarray:
        """Predict the post-perturbation expression profile for target_gene.

        Uses the exact known shift (lookup path) for genes seen during fit(),
        and the ridge fallback for real genes not used as perturbation targets.

        Args:
            control_mean: 1-D array of shape (n_genes,). Typically the same
                control mean used to fit, but can vary at call time.
            target_gene: Gene name to perturb. Must be in gene_names.

        Returns:
            1-D numpy array of shape (n_genes,): predicted post-perturbation
            expression profile.

        Raises:
            RuntimeError: if called before fit().
            KeyError: if target_gene is not in gene_names at all (distinct from
                a gene that is in gene_names but was not used as a perturbation
                target during fit -- those use the fallback path).
        """
        if self._fallback_model is None:
            raise RuntimeError(
                "LinearAdditivePerturbationModel.predict() called before fit(). "
                "Call fit() or fit_from_adata() first."
            )

        control_mean = np.asarray(control_mean, dtype=float)

        # Exact lookup: gene was a perturbation target during fit.
        if target_gene in self._known_shifts:
            return control_mean + self._known_shifts[target_gene]

        # Fallback path: gene is in gene_names but not a fit-time perturbation.
        if target_gene in self._gene_index:
            gene_ctrl_expr = control_mean[self._gene_index[target_gene]]
            X_pred = np.array([[gene_ctrl_expr]], dtype=float)  # shape (1, 1)
            predicted_shift = self._fallback_model.predict(X_pred)[0]  # shape (n_genes,)
            return control_mean + predicted_shift

        # Gene is not in gene_names at all: distinct error.
        raise KeyError(f"{target_gene!r} not found in gene_names")


def fit_from_adata(
    adata: "AnnData",
    target_gene_col: str = "target_gene",
    control_token: str = "non-targeting",
    alpha: float = 1.0,
) -> tuple["LinearAdditivePerturbationModel", np.ndarray]:
    """Fit a LinearAdditivePerturbationModel directly from a labeled AnnData.

    Performs pseudobulking internally (mean per group), so callers do not need
    to compute control_mean or pert_means manually.

    Args:
        adata: AnnData with cells labeled in obs[target_gene_col]. Control cells
            have obs[target_gene_col] == control_token; perturbed cells have the
            target gene name.
        target_gene_col: Column in adata.obs that identifies each cell's
            perturbation condition or control status. Defaults to "target_gene"
            (cell-eval DEFAULT_PERT_COL; 05-RESEARCH.md Pitfall 4).
        control_token: Value in obs[target_gene_col] identifying control cells.
            Defaults to "non-targeting" (cell-eval DEFAULT_CTRL).
        alpha: Ridge regularization strength passed to LinearAdditivePerturbationModel.

    Returns:
        (model, control_mean): Tuple of the fitted model and the control mean
        vector (1-D array of shape (n_vars,)). Plan 05-03's pipeline.predict()
        needs control_mean alongside the model to call model.predict().
    """
    import scipy.sparse as sp

    # Densify X if sparse (mirrors annotation/baseline.py's densify pattern).
    X = adata.X
    if sp.issparse(X):
        X = X.toarray()
    X = np.asarray(X, dtype=float)

    labels = adata.obs[target_gene_col]

    # Pseudobulk: mean expression per group.
    control_mask = labels == control_token
    control_mean = X[control_mask].mean(axis=0)  # shape (n_vars,)

    pert_means: dict[str, np.ndarray] = {}
    for gene in labels.unique():
        if gene == control_token:
            continue
        mask = labels == gene
        pert_means[gene] = X[mask].mean(axis=0)

    gene_names = list(adata.var_names)
    model = LinearAdditivePerturbationModel(alpha=alpha)
    model.fit(gene_names, control_mean, pert_means)

    return model, control_mean
