"""Bounded-summary dataclass contracts for Phase 5 (perturbation-response) modules.

Mirrors annotation/summary.py's dataclass-per-result-type convention (see that
module for the established precedent, established in Phase 4).

Design note -- one target gene per call:
Unlike AnnotationSummary (many clusters per call), PerturbationSummary predicts
ONE target gene per predict() invocation. PERT-01's wording is "control profiles
and a target gene" (singular), so there is exactly one model_call and one
baseline_call per PerturbationSummary, not a list. This matches the VCC task
format (one gene knocked out/activated at a time).

field semantics:
- PerturbationCall.method: "linear_additive" for the learned model
  (Plan 05-02, LinearAdditivePerturbationModel) or "naive_baseline" for the
  naive baseline (Plan 05-03, wraps cell_eval.build_base_mean_adata).
- PerturbationCall.predicted_expression: a vector of length len(gene_names);
  both calls' vectors are aligned to the same gene order given by
  PerturbationSummary.gene_names.
- PerturbationSummary.gene_names: the shared gene order both calls'
  predicted_expression vectors are aligned to.

Every Phase 5 plan (05-02 through 05-06) implements against this contract.
Do not change field names or types without updating all downstream plans.
"""

from dataclasses import dataclass


@dataclass
class PerturbationCall:
    """One method's prediction for one target gene -- model or baseline, same shape."""

    method: str
    target_gene: str
    predicted_expression: list[float]


@dataclass
class PerturbationSummary:
    """Full result for one predict() invocation (one target gene, two methods)."""

    dataset_id: str | None
    target_gene: str
    gene_names: list[str]
    model_call: PerturbationCall
    baseline_call: PerturbationCall


# ---------------------------------------------------------------------------
# Geneformer (FM-02) output-shape contract -- Phase 13.
#
# Design note -- structurally distinct from PerturbationCall/PerturbationSummary:
# Per 13-RESEARCH.md Pitfall 4, Geneformer's in-silico-perturbation output is a
# ranked gene list by cosine shift (InSilicoPerturberStats.get_stats()'s native
# shape), not a per-gene expression vector aligned to a shared gene order. Do
# NOT shoehorn this into PerturbationCall.predicted_expression -- these three
# dataclasses are additive, parallel contracts that Plans 13-03/13-04
# implement against, and the existing PerturbationCall/PerturbationSummary
# above are left untouched.
# ---------------------------------------------------------------------------


@dataclass
class GeneShift:
    """One gene's ranked cosine-similarity shift from an in-silico perturbation."""

    gene: str
    ensembl_id: str
    cosine_shift: float


@dataclass
class GeneformerPerturbationCall:
    """Geneformer's prediction for one target gene -- ranked gene list, not a vector."""

    method: str  # always "geneformer"
    target_gene: str
    target_ensembl_id: str
    match_rate: float  # fraction of adata.var Ensembl IDs found in Geneformer's vocab
    ranked_genes: list[GeneShift]  # sorted by |cosine_shift| descending


@dataclass
class GeneformerPerturbationSummary:
    """Full result for one Geneformer predict() invocation (one target gene)."""

    dataset_id: str | None
    target_gene: str
    call: GeneformerPerturbationCall
