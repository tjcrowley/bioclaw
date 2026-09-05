"""Decoupler ORA marker-gene baseline for cell-type annotation (ANNOT-02).

Introspected against the actually-installed `decoupler==2.2.0` package
(the API differs from the v1.x `dc.get_resource`/`dc.run_ora` sketch in
04-RESEARCH.md Pattern 2 -- that sketch was explicitly flagged
LOW-MEDIUM confidence and is superseded here by the real, verified API):

- Resource retrieval: `dc.op.resource(name: str, organism: str = "human",
  license: str = "academic", verbose: bool = False) -> pd.DataFrame`
  (long-format `source`/`target`[/`weight`] network). Network access at
  call time -- this module only invokes it when `markers is None`.
- Enrichment: `dc.mt.ora(data, net, tmin=5, raw=False, empty=True,
  bsize=250_000, verbose=False, n_up=None, n_bm=0, n_bg=20000,
  ha_corr=True)`. It mutates `data` in place (returns `None`), writing
  per-observation results into `data.obsm["score_ora"]` (log odds ratio,
  higher = stronger enrichment) and `data.obsm["padj_ora"]`
  (Benjamini-Hochberg adjusted p-value) -- both `pd.DataFrame`s indexed
  by observation name, one column per `source` (cell type) in `net`.

`dc.mt.ora` operates per-*observation* (row), not per-group, and its
`n_up` (top-N-by-magnitude "up-regulated" features) parameter defaults to
the top 5% of features -- a sensible default for genome-scale panels
(thousands of genes) but too conservative to discriminate cleanly on
small marker panels, since so few genes are ever selected as "observed".
`baseline_annotate()` therefore:

1. Pseudobulks `adata` into one row per `groupby` group (sum of raw
   counts across all cells in that group), producing an
   `n_groups x n_genes` AnnData -- this both satisfies "one call per
   group, never per cell" and gives `dc.mt.ora` a single, less-sparse
   profile per group to score.
2. Runs `dc.mt.ora` on that pseudobulked AnnData with
   `n_up = round(0.1 * n_genes)` (10% of genes, not 5%) -- a deliberate,
   documented override that discriminates correctly on both this
   module's small unit-test fixtures and (being a fraction, not a fixed
   count) scales naturally to real, much larger gene panels.
3. For each group, takes the `source` (cell type) with the highest
   `score_ora` value as that group's label.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from anndata import AnnData
from scipy import sparse

import decoupler as dc

from annotation.summary import AnnotationCall

# Fraction of genes selected as "up-regulated" observed features per group
# pseudobulk profile, passed to dc.mt.ora's n_up kwarg. See module
# docstring for rationale (decoupler's own 5% default is too conservative
# on small marker panels; 10% is a deliberate, documented override).
_ORA_N_UP_FRACTION = 0.1


def baseline_annotate(
    adata: AnnData,
    groupby: str = "leiden",
    markers: pd.DataFrame | None = None,
    resource_name: str = "PanglaoDB",
) -> list[AnnotationCall]:
    """Marker-gene ORA statistical baseline: one `AnnotationCall` per
    unique value of `adata.obs[groupby]`, never per cell.

    `adata` must already be clustered/labeled -- a `groupby` column must
    already exist in `adata.obs`; this function never runs clustering
    itself.

    When `markers` is `None`, fetches the named resource via
    `dc.op.resource(name=resource_name)` (network access -- production
    only). When `markers` is provided directly (a decoupler-shaped
    long-format DataFrame with `source`/`target` columns), no network
    call is made -- this is the seam unit tests use to stay network-free.

    `ontology_term_id` is always `None` on every returned call:
    PanglaoDB/CellMarker-style marker resources carry no Cell Ontology
    terms. This is a permanent, documented property of the baseline
    side (see annotation/summary.py's module docstring), not a bug --
    ontology terms are populated only on the FM (scGPT) side.
    """
    if groupby not in adata.obs.columns:
        raise KeyError(
            f"groupby column {groupby!r} not found in adata.obs -- "
            "baseline_annotate() never runs clustering itself; run "
            "clustering (or otherwise label adata.obs) first"
        )

    if markers is None:
        markers = dc.op.resource(name=resource_name)

    groups = adata.obs[groupby].astype(str)
    unique_groups = sorted(groups.unique())

    X = adata.X
    X = X.toarray() if sparse.issparse(X) else np.asarray(X)

    group_values = groups.to_numpy()
    pseudobulk = np.vstack(
        [X[group_values == group].sum(axis=0) for group in unique_groups]
    ).astype(np.float64)

    pb_adata = AnnData(
        X=pseudobulk,
        obs=pd.DataFrame(index=pd.Index(unique_groups, name=groupby)),
        var=adata.var.copy(),
    )

    n_up = max(1, round(_ORA_N_UP_FRACTION * adata.n_vars))
    dc.mt.ora(pb_adata, markers, n_up=n_up, verbose=False)
    scores = pb_adata.obsm["score_ora"]

    calls = []
    for group in unique_groups:
        row = scores.loc[group]
        top_label = row.idxmax()
        top_score = row.max()
        calls.append(
            AnnotationCall(
                cluster=str(group),
                label=str(top_label),
                confidence=float(top_score),
                reference_dataset=f"decoupler ORA vs {resource_name} (human, canonical markers)",
                ontology_term_id=None,
            )
        )
    return calls
