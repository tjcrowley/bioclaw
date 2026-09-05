"""Tests for agent/tools.py: ingest_10x_tool/analyze_dataset_tool @tool
handlers, called directly as plain async functions (bypassing the SDK/LLM
entirely, per 03-RESEARCH.md Pitfall 4).

Note: `@tool`-decorated functions become `claude_agent_sdk.SdkMcpTool`
instances, not directly callable -- the actual async handler lives on
`.handler`. Tests invoke `<tool>.handler(args)`; `agent/server.py` (Task 2)
passes the `SdkMcpTool` instances themselves to `create_sdk_mcp_server`.

`tiny_mtx_dir` (18 genes) is used for the plain ingest test, matching the
plan's spec. It is deliberately NOT reused for the ingest->analyze round
trip: `ingest.qc.QCConfig`'s default `min_genes_per_cell=200` filters every
cell out of an 18-gene dataset (no cell can ever have >=200 detected genes
when there are only 18 genes total), and `ingest_10x_tool`'s schema
intentionally doesn't expose `qc_config` as a tool-input override (Phase 1's
own `tests/test_pipeline.py` always overrides `qc_config` for this exact
reason when running the full pipeline on `tiny_mtx_dir`). The round-trip
test below builds its own larger, real-structure 10x MEX directory
(`analyzable_mtx_dir`, 300 genes x 60 cells, two marker-gene pseudo
populations) that survives default QC and produces genuine cluster
structure, so `analyze_dataset_tool` is exercised with real default
settings end to end.
"""

import asyncio
import gzip
import json
from pathlib import Path

import numpy as np
import pytest
from scipy import sparse
from scipy.io import mmwrite

import agent.tools as agent_tools
from agent.tools import analyze_dataset_tool, ingest_10x_tool

FEATURE_TYPE = "Gene Expression"


def _write_gz_lines(path: Path, lines) -> None:
    with gzip.open(path, "wt") as fh:
        for line in lines:
            fh.write(f"{line}\n")


@pytest.fixture
def analyzable_mtx_dir(tmp_path) -> Path:
    """A 10x MEX directory large/structured enough to survive default QC
    (`min_genes_per_cell=200`) and produce genuine cluster structure for
    `analyze_dataset_tool`'s round-trip test -- unlike `tiny_mtx_dir`, which
    is deliberately too small for a default-config full pipeline run (see
    module docstring).
    """
    n_genes, n_cells, n_pop = 300, 60, 30
    rng = np.random.default_rng(42)

    counts = rng.poisson(lam=3, size=(n_cells, n_genes)).astype(np.int64)
    counts[0:n_pop, 0:15] = rng.poisson(lam=20, size=(n_pop, 15)).astype(np.int64)
    counts[n_pop : 2 * n_pop, 15:30] = rng.poisson(lam=20, size=(n_pop, 15)).astype(
        np.int64
    )
    matrix = sparse.csr_matrix(counts.T)  # genes x cells, MatrixMarket convention

    mtx_dir = tmp_path / "analyzable_mtx"
    mtx_dir.mkdir()

    gene_ids = [f"ENSG{i:011d}" for i in range(n_genes)]
    gene_symbols = ["MT-CO1", "MT-ND1"] + [f"GENE{i:03d}" for i in range(2, n_genes)]
    barcodes = [f"BARCODE{i:04d}-1" for i in range(n_cells)]

    _write_gz_lines(
        mtx_dir / "features.tsv.gz",
        (f"{gid}\t{sym}\t{FEATURE_TYPE}" for gid, sym in zip(gene_ids, gene_symbols)),
    )
    _write_gz_lines(mtx_dir / "barcodes.tsv.gz", barcodes)

    tmp_mtx = mtx_dir / "matrix.mtx"
    mmwrite(str(tmp_mtx), matrix)
    with open(tmp_mtx, "rb") as f_in, gzip.open(mtx_dir / "matrix.mtx.gz", "wb") as f_out:
        f_out.write(f_in.read())
    tmp_mtx.unlink()

    return mtx_dir


def test_ingest_10x_tool_returns_dataset_id(tmp_path, tiny_mtx_dir, monkeypatch):
    monkeypatch.setattr(agent_tools, "STORE_ROOT", str(tmp_path))

    result = asyncio.run(
        ingest_10x_tool.handler({"path": str(tiny_mtx_dir), "name": "pilot"})
    )

    assert result["is_error"] is False
    assert len(result["content"]) == 1
    block = result["content"][0]
    assert block["type"] == "text"
    payload = json.loads(block["text"])
    assert payload == {"dataset_id": "pilot@1"}


def test_analyze_dataset_tool_round_trip(tmp_path, analyzable_mtx_dir, monkeypatch):
    monkeypatch.setattr(agent_tools, "STORE_ROOT", str(tmp_path))

    asyncio.run(
        ingest_10x_tool.handler({"path": str(analyzable_mtx_dir), "name": "pilot"})
    )

    result = asyncio.run(analyze_dataset_tool.handler({"name": "pilot"}))

    assert result["is_error"] is False
    payload = json.loads(result["content"][0]["text"])
    assert payload["dataset_id"] == "pilot@2"
    assert set(["preprocess", "cluster", "de"]) <= set(payload.keys())
    assert payload["de"] is None


def test_analyze_dataset_tool_schema_omits_version():
    schema = analyze_dataset_tool.input_schema
    assert "version" not in schema
    assert "name" in schema


def test_analyze_dataset_tool_unknown_name_returns_error_result(tmp_path, monkeypatch):
    monkeypatch.setattr(agent_tools, "STORE_ROOT", str(tmp_path))

    result = asyncio.run(analyze_dataset_tool.handler({"name": "does-not-exist"}))

    assert result["is_error"] is True


def test_bioclaw_server_imports_and_wraps_both_tools():
    from agent.server import bioclaw_server  # noqa: F401 -- import must not raise
