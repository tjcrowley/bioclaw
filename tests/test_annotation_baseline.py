"""Tests for annotation/baseline.py: baseline_annotate(), the decoupler
ORA marker-gene statistical baseline for cell-type annotation (ANNOT-02).

All tests pass an explicit `markers` DataFrame, so the network-backed
`dc.op.resource()` code path (only exercised when `markers is None`) is
never invoked here -- no network access required to pass this suite.
"""

import pandas as pd
import pytest

from annotation.baseline import baseline_annotate
from annotation.summary import AnnotationCall


@pytest.fixture
def synthetic_marker_resource() -> pd.DataFrame:
    """A hand-crafted decoupler-shaped marker resource (source=cell type
    label, target=gene symbol) matching structured_adata's own known
    marker genes: GENE00-14 for a "Population A"-like label, GENE15-29
    for a "Population B"-like label.
    """
    pop_a_genes = [f"GENE{i:02d}" for i in range(0, 15)]
    pop_b_genes = [f"GENE{i:02d}" for i in range(15, 30)]
    return pd.DataFrame(
        {
            "source": ["Population A"] * len(pop_a_genes) + ["Population B"] * len(pop_b_genes),
            "target": pop_a_genes + pop_b_genes,
        }
    )


def test_baseline_annotate_returns_one_call_per_group(structured_adata, synthetic_marker_resource):
    calls = baseline_annotate(
        structured_adata,
        groupby="true_population",
        markers=synthetic_marker_resource,
    )

    assert len(calls) == 2
    assert all(isinstance(c, AnnotationCall) for c in calls)
    clusters = {c.cluster for c in calls}
    assert clusters == {"A", "B"}


def test_baseline_annotate_call_fields_are_well_formed(structured_adata, synthetic_marker_resource):
    calls = baseline_annotate(
        structured_adata,
        groupby="true_population",
        markers=synthetic_marker_resource,
        resource_name="PanglaoDB",
    )

    for call in calls:
        assert call.label is not None
        assert isinstance(call.confidence, float)
        assert "PanglaoDB" in call.reference_dataset
        assert call.ontology_term_id is None


def test_baseline_annotate_discriminates_populations(structured_adata, synthetic_marker_resource):
    """Population A's marker genes (GENE00-14) should enrich its group
    against the "Population A" resource entry, not "Population B", and
    vice versa for Population B -- proving the statistical logic actually
    discriminates rather than returning a fixed label.
    """
    calls = baseline_annotate(
        structured_adata,
        groupby="true_population",
        markers=synthetic_marker_resource,
    )
    calls_by_cluster = {c.cluster: c for c in calls}

    assert calls_by_cluster["A"].label == "Population A"
    assert calls_by_cluster["B"].label == "Population B"
    assert calls_by_cluster["A"].label != calls_by_cluster["B"].label


def test_baseline_annotate_never_calls_network_resource_fetch(structured_adata, synthetic_marker_resource, monkeypatch):
    """When markers is provided, the network-backed dc.op.resource() path
    must never be invoked."""
    import decoupler as dc

    def _fail_if_called(*args, **kwargs):
        raise AssertionError("dc.op.resource() must not be called when markers is provided")

    monkeypatch.setattr(dc.op, "resource", _fail_if_called)

    calls = baseline_annotate(
        structured_adata,
        groupby="true_population",
        markers=synthetic_marker_resource,
    )
    assert len(calls) == 2


def test_baseline_annotate_raises_on_missing_groupby_column(structured_adata, synthetic_marker_resource):
    with pytest.raises(KeyError):
        baseline_annotate(
            structured_adata,
            groupby="leiden",
            markers=synthetic_marker_resource,
        )
