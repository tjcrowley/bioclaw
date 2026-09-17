"""EXPORT-02 test scaffold for GET /api/export/script endpoint (plan 12-03 implements).

These tests are RED until plan 03 adds:
  - GET /api/export/script?dataset_id=... to webapp/backend/main.py
  - A script generator that reads adata.uns['qc'] and adata.uns['analysis']
    and reconstructs the pipeline (census fetch for census-source datasets,
    sc.read_h5ad for file-source datasets).

This file is the Nyquist scaffold: every named test here corresponds to a
validation checkpoint in 12-VALIDATION.md and must pass once plan 03 is done.

Fixtures follow the same pattern as test_webapp_export.py:
  - TestClient with cookies={"session": "testpass"}
  - monkeypatch agent_tools.STORE_ROOT to a tmp_path store
  - monkeypatch BIOCLAW_WEB_PASSWORD="testpass"

Two fixture variants:
  - census_dataset: source_path is a cellxgene-census provenance string
  - file_dataset: source_path is a plain filesystem path string
  - no_analysis_dataset: dataset saved without adata.uns['analysis']
"""

from __future__ import annotations

from dataclasses import asdict

import numpy as np
import pandas as pd
import pytest
from anndata import AnnData
from fastapi.testclient import TestClient
from scipy import sparse

import agent.tools as agent_tools
from analysis.pipeline import AnalysisConfig
from ingest.qc import QCConfig
from ingest.store import DatasetStore
from webapp.backend.main import app


# ─── AnnData builder ──────────────────────────────────────────────────────────


def _build_adata(n_cells: int = 20, n_genes: int = 15) -> AnnData:
    """Minimal sparse AnnData without obs/var extras."""
    rng = np.random.default_rng(0)
    X = sparse.csr_matrix(
        rng.integers(1, 10, size=(n_cells, n_genes)).astype(np.float32)
    )
    obs = pd.DataFrame(index=[f"C{i}" for i in range(n_cells)])
    var = pd.DataFrame(index=[f"G{i}" for i in range(n_genes)])
    return AnnData(X=X, obs=obs, var=var)


def _add_qc_uns(adata: AnnData, cfg: QCConfig | None = None) -> AnnData:
    """Populate adata.uns['qc'] in the same shape that qc.run() writes."""
    cfg = cfg or QCConfig()
    adata.uns["qc"] = {
        "config": asdict(cfg),
        "n_cells_before": adata.n_obs,
        "n_cells_after": adata.n_obs,
        "removed_by_reason": {"low_gene_count": 0, "high_mito": 0, "doublet": 0},
    }
    return adata


def _add_analysis_uns(adata: AnnData, cfg: AnalysisConfig | None = None) -> AnnData:
    """Populate adata.uns['analysis'] in the same shape that analyze() writes."""
    cfg = cfg or AnalysisConfig()
    adata.uns["analysis"] = asdict(cfg)
    return adata


# ─── Fixtures ─────────────────────────────────────────────────────────────────


@pytest.fixture
def census_dataset(tmp_path, monkeypatch):
    """AnnData saved with a cellxgene-census provenance source_path.

    Returns (client, dataset_id) — ready to hit GET /api/export/script.
    """
    adata = _build_adata()
    analysis_cfg = AnalysisConfig(random_state=42)
    _add_qc_uns(adata)
    _add_analysis_uns(adata, analysis_cfg)

    census_source = "cellxgene-census:stable:Homo sapiens:tissue_general == 'lung'"
    store_root = tmp_path / "store"
    store = DatasetStore(root=store_root)
    version = store.save("census-lung", adata, source_path=census_source)
    dataset_id = f"census-lung@{version}"

    monkeypatch.setattr(agent_tools, "STORE_ROOT", str(store_root))
    monkeypatch.setenv("BIOCLAW_WEB_PASSWORD", "testpass")
    client = TestClient(app, cookies={"session": "testpass"})
    return client, dataset_id


@pytest.fixture
def file_dataset(tmp_path, monkeypatch):
    """AnnData saved with a plain filesystem source_path.

    Returns (client, dataset_id).
    """
    adata = _build_adata()
    _add_qc_uns(adata)
    _add_analysis_uns(adata)

    file_source = "/data/raw/my_sample.h5ad"
    store_root = tmp_path / "store"
    store = DatasetStore(root=store_root)
    version = store.save("file-dataset", adata, source_path=file_source)
    dataset_id = f"file-dataset@{version}"

    monkeypatch.setattr(agent_tools, "STORE_ROOT", str(store_root))
    monkeypatch.setenv("BIOCLAW_WEB_PASSWORD", "testpass")
    client = TestClient(app, cookies={"session": "testpass"})
    return client, dataset_id


@pytest.fixture
def no_analysis_dataset(tmp_path, monkeypatch):
    """AnnData saved WITHOUT adata.uns['analysis'] — only QC uns present.

    Returns (client, dataset_id).
    """
    adata = _build_adata()
    _add_qc_uns(adata)
    # Intentionally skip _add_analysis_uns() — no 'analysis' key

    store_root = tmp_path / "store"
    store = DatasetStore(root=store_root)
    version = store.save("no-analysis", adata, source_path="/data/no_analysis.h5ad")
    dataset_id = f"no-analysis@{version}"

    monkeypatch.setattr(agent_tools, "STORE_ROOT", str(store_root))
    monkeypatch.setenv("BIOCLAW_WEB_PASSWORD", "testpass")
    client = TestClient(app, cookies={"session": "testpass"})
    return client, dataset_id


# ─── Tests ────────────────────────────────────────────────────────────────────


def test_export_script_returns_py(file_dataset):
    """GET /api/export/script returns 200, content-type text/x-python, body starts
    with a comment header and contains 'import scanpy'.
    """
    client, dataset_id = file_dataset
    resp = client.get(f"/api/export/script?dataset_id={dataset_id}")
    assert resp.status_code == 200
    assert "text/x-python" in resp.headers.get("content-type", "")
    body = resp.text
    assert body.strip().startswith("#"), "Script body must start with a comment header"
    assert "import scanpy" in body


def test_script_contains_qc_thresholds(file_dataset):
    """Generated script text contains the QC threshold values from adata.uns['qc'].

    Checks for min_genes_per_cell, min_cells_per_gene, and max_pct_mt values
    that were stored in adata.uns['qc']['config'] at save time.
    """
    client, dataset_id = file_dataset
    resp = client.get(f"/api/export/script?dataset_id={dataset_id}")
    assert resp.status_code == 200
    body = resp.text

    cfg = QCConfig()  # defaults used in the file_dataset fixture
    assert str(cfg.min_genes_per_cell) in body, (
        f"min_genes_per_cell={cfg.min_genes_per_cell} not found in script"
    )
    assert str(cfg.min_cells_per_gene) in body, (
        f"min_cells_per_gene={cfg.min_cells_per_gene} not found in script"
    )
    assert str(cfg.max_pct_mt) in body or str(int(cfg.max_pct_mt)) in body, (
        f"max_pct_mt={cfg.max_pct_mt} not found in script"
    )


def test_script_contains_random_state(file_dataset):
    """Generated script contains 'random_state=0' from adata.uns['analysis']."""
    client, dataset_id = file_dataset
    resp = client.get(f"/api/export/script?dataset_id={dataset_id}")
    assert resp.status_code == 200
    body = resp.text

    cfg = AnalysisConfig()  # default random_state=0
    assert f"random_state={cfg.random_state}" in body, (
        f"random_state={cfg.random_state} not found in script body"
    )


def test_script_census_source(census_dataset):
    """For a census-source dataset, the generated script uses cellxgene_census.open_soma
    (not sc.read_h5ad) and includes the obs_value_filter string.
    """
    client, dataset_id = census_dataset
    resp = client.get(f"/api/export/script?dataset_id={dataset_id}")
    assert resp.status_code == 200
    body = resp.text

    assert "cellxgene_census.open_soma" in body, (
        "Census-source script must use cellxgene_census.open_soma"
    )
    assert "tissue_general == 'lung'" in body, (
        "obs_value_filter from the census provenance string must appear in the script"
    )
    assert "sc.read_h5ad" not in body, (
        "Census-source script must not use sc.read_h5ad"
    )


def test_script_export_requires_auth(tmp_path, monkeypatch):
    """GET /api/export/script without a session cookie returns 401."""
    monkeypatch.setenv("BIOCLAW_WEB_PASSWORD", "testpass")
    client = TestClient(app, raise_server_exceptions=False)
    resp = client.get("/api/export/script?dataset_id=anything@1")
    assert resp.status_code == 401


def test_script_no_analysis_graceful(no_analysis_dataset):
    """Dataset saved without adata.uns['analysis'] returns 200 and includes a
    '# No analysis was run' comment — not a 500/KeyError.
    """
    client, dataset_id = no_analysis_dataset
    resp = client.get(f"/api/export/script?dataset_id={dataset_id}")
    assert resp.status_code == 200
    body = resp.text
    assert "# No analysis was run" in body, (
        "Script for dataset without analysis must include '# No analysis was run' comment"
    )
