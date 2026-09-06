"""Tests for annotation/pipeline.py::annotate() -- composes Plan 04-02's
baseline_annotate() (unconditional) with Plan 04-03's call_scgpt_annotate()
(best-effort, never crashes the pipeline) into one bounded AnnotationSummary.

fm_client.call_scgpt_annotate is monkeypatched throughout -- no real
isolated environment or checkpoint is required for this fast tier.
"""

import numpy as np
import pandas as pd
import pytest
from anndata import AnnData

import annotation.pipeline as pipeline
from annotation.summary import AnnotationCall
from ingest.store import DatasetStore

MARKERS = pd.DataFrame(
    {
        "source": ["PopA"] * 5 + ["PopB"] * 5,
        "target": [f"GENE{i:03d}" for i in range(0, 5)]
        + [f"GENE{i:03d}" for i in range(5, 10)],
    }
)


@pytest.fixture
def clustered_dataset(tmp_path):
    """A store containing one already-clustered ("leiden" in .obs) dataset,
    matching what analyze() would have produced -- annotate() must not
    re-run clustering itself."""
    n_genes, n_cells = 20, 20
    rng = np.random.default_rng(7)
    counts = rng.poisson(lam=2, size=(n_cells, n_genes)).astype(np.float64)
    counts[0:10, 0:5] = rng.poisson(lam=20, size=(10, 5)).astype(np.float64)
    counts[10:20, 5:10] = rng.poisson(lam=20, size=(10, 5)).astype(np.float64)

    adata = AnnData(X=counts)
    adata.var_names = [f"GENE{i:03d}" for i in range(n_genes)]
    adata.obs["leiden"] = ["0"] * 10 + ["1"] * 10

    store = DatasetStore(root=tmp_path)
    store.save("pilot", adata)
    return tmp_path


def _mock_baseline(monkeypatch):
    monkeypatch.setattr(
        pipeline,
        "baseline_annotate",
        lambda adata, groupby="leiden": [
            AnnotationCall(
                cluster="0",
                label="PopA",
                confidence=0.9,
                reference_dataset="decoupler ORA vs PanglaoDB (human, canonical markers)",
                ontology_term_id=None,
            ),
            AnnotationCall(
                cluster="1",
                label="PopB",
                confidence=0.85,
                reference_dataset="decoupler ORA vs PanglaoDB (human, canonical markers)",
                ontology_term_id=None,
            ),
        ],
    )


def test_annotate_returns_baseline_when_fm_call_fails(clustered_dataset, monkeypatch):
    _mock_baseline(monkeypatch)
    monkeypatch.setattr(
        pipeline,
        "call_scgpt_annotate",
        lambda *a, **k: (_ for _ in ()).throw(RuntimeError("no checkpoint")),
    )

    dataset_id, summary = pipeline.annotate("pilot", store_root=str(clustered_dataset))

    assert dataset_id == "pilot@(latest)"
    assert summary["fm_calls"] == []
    assert len(summary["baseline_calls"]) == 2
    assert summary["baseline_calls"][0]["label"] == "PopA"
    assert summary["fm_model"]
    assert summary["baseline_method"]


def test_annotate_includes_fm_calls_on_success(clustered_dataset, monkeypatch):
    _mock_baseline(monkeypatch)
    canned_fm_calls = [
        AnnotationCall(
            cluster="0",
            label="T cell",
            confidence=0.91,
            reference_dataset="cellxgene-census: tissue=blood, n=3000",
            ontology_term_id="CL:0000084",
        )
    ]
    monkeypatch.setattr(
        pipeline, "call_scgpt_annotate", lambda *a, **k: canned_fm_calls
    )

    dataset_id, summary = pipeline.annotate("pilot", store_root=str(clustered_dataset))

    assert dataset_id == "pilot@(latest)"
    assert summary["fm_calls"] == [
        {
            "cluster": "0",
            "label": "T cell",
            "confidence": 0.91,
            "reference_dataset": "cellxgene-census: tissue=blood, n=3000",
            "ontology_term_id": "CL:0000084",
        }
    ]
    assert len(summary["baseline_calls"]) == 2


def test_annotate_explicit_version_in_dataset_id(clustered_dataset, monkeypatch):
    _mock_baseline(monkeypatch)
    monkeypatch.setattr(pipeline, "call_scgpt_annotate", lambda *a, **k: [])

    dataset_id, _ = pipeline.annotate(
        "pilot", version=1, store_root=str(clustered_dataset)
    )

    assert dataset_id == "pilot@1"


def test_annotate_unknown_name_raises_keyerror(clustered_dataset, monkeypatch):
    _mock_baseline(monkeypatch)
    monkeypatch.setattr(pipeline, "call_scgpt_annotate", lambda *a, **k: [])

    with pytest.raises(KeyError):
        pipeline.annotate("does-not-exist", store_root=str(clustered_dataset))
