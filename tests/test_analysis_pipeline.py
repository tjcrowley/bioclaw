"""Integration tests for analysis/pipeline.py -- proves preprocess.py,
cluster.py, diffexp.py, and Phase 1's DatasetStore/contract wire together
correctly end to end (ANLYS-01/02/03/04, composed rather than tested in
isolation).
"""

import pytest

from analysis import pipeline
from analysis.pipeline import AnalysisConfig
from ingest import contract
from ingest.store import DatasetStore


def _seed_store(structured_adata, tmp_path):
    """Simulates a dataset that already went through ingest: sets the
    immutable counts-layer contract, saves as version 1 under "demo"."""
    store_root = tmp_path / "store"
    adata = structured_adata
    contract.set_counts_layer(adata)
    store = DatasetStore(root=str(store_root))
    store.save("demo", adata)
    return store_root


def test_analyze_creates_new_version_not_overwrite(structured_adata, tmp_path):
    store_root = _seed_store(structured_adata, tmp_path)

    new_id, summary = pipeline.analyze("demo", store_root=str(store_root))

    assert new_id == "demo@2"


def test_analyze_counts_integrity_survives_round_trip(structured_adata, tmp_path):
    store_root = _seed_store(structured_adata, tmp_path)

    pipeline.analyze("demo", store_root=str(store_root))

    adata2 = DatasetStore(root=str(store_root)).load("demo", version=2)
    assert contract.verify_counts_integrity(adata2) is True


def test_analyze_result_has_clustering_and_logged_config(structured_adata, tmp_path):
    store_root = _seed_store(structured_adata, tmp_path)

    pipeline.analyze("demo", store_root=str(store_root))

    adata2 = DatasetStore(root=str(store_root)).load("demo", version=2)

    assert "leiden" in adata2.obs
    assert adata2.obs["leiden"].nunique() >= 2
    assert "X_umap" in adata2.obsm
    assert "analysis" in adata2.uns
    assert isinstance(adata2.uns["analysis"], dict)


def test_analyze_returns_bounded_summary_with_patched_dataset_id(
    structured_adata, tmp_path
):
    store_root = _seed_store(structured_adata, tmp_path)

    new_id, summary = pipeline.analyze("demo", store_root=str(store_root))

    assert new_id == "demo@2"
    assert summary["preprocess"]["dataset_id"] == "demo@2"
    assert summary["cluster"]["dataset_id"] == "demo@2"
    assert summary["de"] is None


def test_analyze_nonexistent_name_raises_key_error(tmp_path):
    store_root = tmp_path / "store"

    with pytest.raises(KeyError):
        pipeline.analyze("nonexistent-name", store_root=str(store_root))


def test_analyze_with_de_returns_bounded_de_summary(structured_adata, tmp_path):
    store_root = _seed_store(structured_adata, tmp_path)

    new_id, summary = pipeline.analyze(
        "demo",
        config=AnalysisConfig(
            run_de=True,
            de_groupby="true_population",
            de_group1="A",
            de_group2="B",
            de_n_genes=10,
        ),
        store_root=str(store_root),
    )

    assert summary["de"] is not None
    assert summary["de"]["dataset_id"] == new_id
    assert len(summary["de"]["top_genes"]) <= 10


def test_analyze_run_de_without_groupby_raises_value_error(
    structured_adata, tmp_path
):
    store_root = _seed_store(structured_adata, tmp_path)

    with pytest.raises(ValueError):
        pipeline.analyze(
            "demo",
            config=AnalysisConfig(run_de=True),
            store_root=str(store_root),
        )
