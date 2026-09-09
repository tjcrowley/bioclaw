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
