"""Unit tests for GET /api/export/csv endpoint (EXPORT-01, Phase 11 Plan 03).

Tests cover:
- ZIP response with clusters.csv, de_genes.csv, annotations.csv
- Correct cluster assignments content
- Graceful handling of missing leiden / missing DE data
- Auth gate (401 without credentials)
- 404 for unknown dataset
- 422 for malformed dataset_id
"""

import io
import zipfile

import numpy as np
import pandas as pd
import pytest
from anndata import AnnData
from fastapi.testclient import TestClient
from scipy import sparse

import agent.tools as agent_tools
from ingest.store import DatasetStore
from webapp.backend import deps
from webapp.backend.main import app


# ─── Fixtures ────────────────────────────────────────────────────────────────


@pytest.fixture
def analyzed_dataset(tmp_path, monkeypatch):
    """Minimal AnnData with leiden obs + rank_genes_groups uns, saved to a
    DatasetStore. Monkeypatches STORE_ROOT so the endpoint can load it.
    Returns (client, dataset_id)."""
    n_cells, n_genes = 20, 10
    X = sparse.csr_matrix(np.ones((n_cells, n_genes), dtype=np.float32))
    obs = pd.DataFrame(
        {"leiden": ["0"] * 10 + ["1"] * 10},
        index=[f"C{i}" for i in range(n_cells)],
    )
    var = pd.DataFrame(index=[f"G{i}" for i in range(n_genes)])
    adata = AnnData(X=X, obs=obs, var=var)

    # Minimal rank_genes_groups structure compatible with sc.get.rank_genes_groups_df
    adata.uns["rank_genes_groups"] = {
        "names": np.array(
            [("G0", "G1"), ("G1", "G0")],
            dtype=[("0", "U10"), ("1", "U10")],
        ),
        "scores": np.array(
            [(1.0, 0.5), (0.5, 1.0)],
            dtype=[("0", float), ("1", float)],
        ),
        "pvals": np.array(
            [(0.01, 0.05), (0.05, 0.01)],
            dtype=[("0", float), ("1", float)],
        ),
        "pvals_adj": np.array(
            [(0.02, 0.1), (0.1, 0.02)],
            dtype=[("0", float), ("1", float)],
        ),
        "logfoldchanges": np.array(
            [(1.5, -1.5), (-1.5, 1.5)],
            dtype=[("0", float), ("1", float)],
        ),
        "params": {"groupby": "leiden", "method": "wilcoxon", "reference": "rest"},
    }

    store_root = tmp_path / "store"
    store = DatasetStore(root=store_root)
    # DatasetStore.save(name, adata, ...) — name first, adata second
    version = store.save("test-dataset", adata)
    dataset_id = f"test-dataset@{version}"

    monkeypatch.setattr(agent_tools, "STORE_ROOT", str(store_root))

    # Override password auth for test client
    monkeypatch.setenv("BIOCLAW_WEB_PASSWORD", "testpass")
    client = TestClient(app, cookies={"session": "testpass"})

    return client, dataset_id


@pytest.fixture
def dataset_no_leiden(tmp_path, monkeypatch):
    """AnnData without leiden obs column."""
    n_cells, n_genes = 10, 5
    X = sparse.csr_matrix(np.ones((n_cells, n_genes), dtype=np.float32))
    obs = pd.DataFrame(index=[f"C{i}" for i in range(n_cells)])
    var = pd.DataFrame(index=[f"G{i}" for i in range(n_genes)])
    adata = AnnData(X=X, obs=obs, var=var)

    store_root = tmp_path / "store"
    store = DatasetStore(root=store_root)
    version = store.save("no-leiden", adata)
    dataset_id = f"no-leiden@{version}"

    monkeypatch.setattr(agent_tools, "STORE_ROOT", str(store_root))
    monkeypatch.setenv("BIOCLAW_WEB_PASSWORD", "testpass")
    client = TestClient(app, cookies={"session": "testpass"})

    return client, dataset_id


@pytest.fixture
def dataset_no_de(tmp_path, monkeypatch):
    """AnnData with leiden obs but no rank_genes_groups."""
    n_cells, n_genes = 10, 5
    X = sparse.csr_matrix(np.ones((n_cells, n_genes), dtype=np.float32))
    obs = pd.DataFrame(
        {"leiden": ["0"] * 5 + ["1"] * 5},
        index=[f"C{i}" for i in range(n_cells)],
    )
    var = pd.DataFrame(index=[f"G{i}" for i in range(n_genes)])
    adata = AnnData(X=X, obs=obs, var=var)

    store_root = tmp_path / "store"
    store = DatasetStore(root=store_root)
    version = store.save("no-de", adata)
    dataset_id = f"no-de@{version}"

    monkeypatch.setattr(agent_tools, "STORE_ROOT", str(store_root))
    monkeypatch.setenv("BIOCLAW_WEB_PASSWORD", "testpass")
    client = TestClient(app, cookies={"session": "testpass"})

    return client, dataset_id


# ─── Tests ────────────────────────────────────────────────────────────────────


def test_export_csv_returns_zip(analyzed_dataset):
    """GET /api/export/csv returns HTTP 200 with content-type application/zip."""
    client, dataset_id = analyzed_dataset
    resp = client.get(f"/api/export/csv?dataset_id={dataset_id}")
    assert resp.status_code == 200
    assert "application/zip" in resp.headers["content-type"]


def test_export_csv_zip_contains_expected_files(analyzed_dataset):
    """ZIP contains clusters.csv, de_genes.csv, and annotations.csv."""
    client, dataset_id = analyzed_dataset
    resp = client.get(f"/api/export/csv?dataset_id={dataset_id}")
    assert resp.status_code == 200

    zf = zipfile.ZipFile(io.BytesIO(resp.content))
    names = zf.namelist()
    assert "clusters.csv" in names
    assert "de_genes.csv" in names
    assert "annotations.csv" in names


def test_export_csv_contains_cluster_assignments(analyzed_dataset):
    """clusters.csv has header row (cell_barcode,cluster) and at least one data row."""
    client, dataset_id = analyzed_dataset
    resp = client.get(f"/api/export/csv?dataset_id={dataset_id}")
    assert resp.status_code == 200

    zf = zipfile.ZipFile(io.BytesIO(resp.content))
    clusters_csv = zf.read("clusters.csv").decode()
    lines = [l for l in clusters_csv.strip().splitlines() if l]
    assert lines[0] == "cell_barcode,cluster"
    assert len(lines) > 1  # at least one data row


def test_export_csv_handles_missing_leiden(dataset_no_leiden):
    """Dataset with no leiden key returns clusters.csv with placeholder, not 500."""
    client, dataset_id = dataset_no_leiden
    resp = client.get(f"/api/export/csv?dataset_id={dataset_id}")
    assert resp.status_code == 200

    zf = zipfile.ZipFile(io.BytesIO(resp.content))
    clusters_csv = zf.read("clusters.csv").decode()
    assert "(no cluster data)" in clusters_csv


def test_export_csv_handles_missing_de(dataset_no_de):
    """Dataset with no rank_genes_groups returns de_genes.csv with placeholder, not 500."""
    client, dataset_id = dataset_no_de
    resp = client.get(f"/api/export/csv?dataset_id={dataset_id}")
    assert resp.status_code == 200

    zf = zipfile.ZipFile(io.BytesIO(resp.content))
    de_csv = zf.read("de_genes.csv").decode()
    assert "(no DE data)" in de_csv


def test_export_csv_requires_auth(tmp_path, monkeypatch):
    """GET /api/export/csv without auth cookie returns 401."""
    monkeypatch.setenv("BIOCLAW_WEB_PASSWORD", "testpass")
    # No session cookie
    client = TestClient(app, raise_server_exceptions=False)
    resp = client.get("/api/export/csv?dataset_id=anything@1")
    assert resp.status_code == 401


def test_export_csv_unknown_dataset_returns_404(tmp_path, monkeypatch):
    """GET /api/export/csv?dataset_id=noexist@1 returns 404."""
    store_root = tmp_path / "store"
    DatasetStore(root=store_root)  # create empty store

    monkeypatch.setattr(agent_tools, "STORE_ROOT", str(store_root))
    monkeypatch.setenv("BIOCLAW_WEB_PASSWORD", "testpass")
    client = TestClient(app, cookies={"session": "testpass"})

    resp = client.get("/api/export/csv?dataset_id=noexist@1")
    assert resp.status_code == 404


def test_export_csv_invalid_dataset_id_format(tmp_path, monkeypatch):
    """GET /api/export/csv?dataset_id=noatsign returns 422."""
    monkeypatch.setenv("BIOCLAW_WEB_PASSWORD", "testpass")
    client = TestClient(app, cookies={"session": "testpass"})

    resp = client.get("/api/export/csv?dataset_id=noatsign")
    assert resp.status_code == 422


def test_export_csv_content_disposition_filename(analyzed_dataset):
    """Content-Disposition header includes a .zip filename."""
    client, dataset_id = analyzed_dataset
    resp = client.get(f"/api/export/csv?dataset_id={dataset_id}")
    assert resp.status_code == 200

    cd = resp.headers.get("content-disposition", "")
    assert "attachment" in cd
    assert ".zip" in cd
