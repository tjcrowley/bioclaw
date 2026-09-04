"""Tests for ingest/store.py: DatasetStore save/load/list."""

import numpy as np
import pytest

from ingest.store import DatasetStore


def test_save_load_roundtrip(tmp_path, synthetic_adata):
    store = DatasetStore(root=tmp_path)

    version = store.save("demo", synthetic_adata)
    assert version == 1

    loaded = store.load("demo")
    assert loaded.n_obs == synthetic_adata.n_obs
    assert loaded.n_vars == synthetic_adata.n_vars
    np.testing.assert_array_equal(
        np.asarray(loaded.X.todense()), np.asarray(synthetic_adata.X.todense())
    )

    loaded_v1 = store.load("demo", version=1)
    np.testing.assert_array_equal(
        np.asarray(loaded_v1.X.todense()), np.asarray(synthetic_adata.X.todense())
    )


def test_versioning(tmp_path, synthetic_adata):
    store = DatasetStore(root=tmp_path)

    v1 = store.save("demo", synthetic_adata)
    assert v1 == 1

    modified = synthetic_adata.copy()
    modified.X = modified.X * 2
    v2 = store.save("demo", modified)
    assert v2 == 2

    latest = store.load("demo")
    np.testing.assert_array_equal(
        np.asarray(latest.X.todense()), np.asarray(modified.X.todense())
    )

    original = store.load("demo", version=1)
    np.testing.assert_array_equal(
        np.asarray(original.X.todense()), np.asarray(synthetic_adata.X.todense())
    )


def test_load_missing_name_raises_keyerror(tmp_path):
    store = DatasetStore(root=tmp_path)
    with pytest.raises(KeyError):
        store.load("does-not-exist")


def test_list_returns_records_ordered_by_version(tmp_path, synthetic_adata):
    store = DatasetStore(root=tmp_path)
    store.save("demo", synthetic_adata)
    store.save("demo", synthetic_adata)

    records = store.list("demo")
    assert len(records) == 2
    assert [r["version"] for r in records] == [1, 2]
    for r in records:
        assert set(["name", "version", "path", "created_at", "source_path", "qc_config"]) <= set(
            r.keys()
        )


def test_list_no_name_returns_all(tmp_path, synthetic_adata):
    store = DatasetStore(root=tmp_path)
    store.save("demo", synthetic_adata)
    store.save("other", synthetic_adata)

    records = store.list()
    names = {r["name"] for r in records}
    assert names == {"demo", "other"}


def test_list_missing_name_returns_empty_list(tmp_path):
    store = DatasetStore(root=tmp_path)
    assert store.list("does-not-exist") == []


def test_list_roundtrips_source_path_and_qc_config(tmp_path, synthetic_adata):
    store = DatasetStore(root=tmp_path)
    qc_config = {"min_genes_per_cell": 200}
    store.save(
        "demo",
        synthetic_adata,
        source_path="/some/10x/dir",
        qc_config=qc_config,
    )

    records = store.list("demo")
    assert len(records) == 1
    record = records[0]
    assert record["source_path"] == "/some/10x/dir"
    assert record["qc_config"] == qc_config
