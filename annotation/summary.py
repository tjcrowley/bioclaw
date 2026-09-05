"""Bounded-summary dataclass contracts for Phase 4 (annotation) modules.

Mirrors analysis/summary.py's dataclass-per-result-type convention.
AnnotationCall is the shared shape used by BOTH the FM (scGPT) and
baseline (decoupler) sides -- one call per cluster, never per cell
(O(n_clusters) bounding invariant, matching ClusterSummary.cluster_sizes'
established precedent). `ontology_term_id` is always None for
decoupler/PanglaoDB-baseline calls (that resource carries no Cell
Ontology terms) and populated from the cellxgene-census reference's
pre-existing `cell_type_ontology_term_id` for FM-side calls -- see
04-RESEARCH.md Don't Hand-Roll.
"""

from dataclasses import dataclass


@dataclass
class AnnotationCall:
    """One method's call for one cluster -- FM or baseline, same shape."""

    cluster: str
    label: str
    confidence: float
    reference_dataset: str
    ontology_term_id: str | None


@dataclass
class AnnotationSummary:
    dataset_id: str | None
    fm_calls: list[AnnotationCall]
    baseline_calls: list[AnnotationCall]
    fm_model: str
    baseline_method: str
