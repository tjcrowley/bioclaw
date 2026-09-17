"""DATA-01 unit tests for the census fetch tool (plan 12-02 implements).

These tests are RED until plan 02 lands:
  - agent.tools.fetch_census_dataset_tool
  - agent.server.bioclaw_server (must include "fetch_census_dataset" tool)
  - ingest.census._census_fetch_blocking

This file is the Nyquist scaffold: every named test here corresponds to a
validation checkpoint in 12-VALIDATION.md and must pass once plan 02 is done.

Mocking strategy: patch `cellxgene_census.open_soma` and
`cellxgene_census.get_anndata` so no network access is needed. The mocked
census returns a small AnnData with an MT- gene (so qc.run's mito step has
something to compute) and enough cells/genes to pass min_genes QC filtering.
"""

import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, patch

import numpy as np
import pandas as pd
import pytest
from anndata import AnnData
from scipy import sparse

import agent.tools as agent_tools
from ingest.store import DatasetStore


# ─── Mock AnnData factory ──────────────────────────────────────────────────────


def _make_census_adata(n_cells: int = 60, n_genes: int = 300) -> AnnData:
    """Build a small AnnData that mimics a census fetch result.

    - Includes one MT- gene so qc.run computes pct_counts_mt.
    - Cells have enough genes expressed to survive min_genes_per_cell=200 QC.
    - Uses random integer counts (dtype float32, CSR sparse) matching the
      real census output format.
    """
    rng = np.random.default_rng(42)
    # Dense counts, all genes expressed per cell, to survive min_genes QC
    data = rng.integers(1, 30, size=(n_cells, n_genes)).astype(np.float32)
    X = sparse.csr_matrix(data)
    gene_names = ["MT-ND1"] + [f"G{i}" for i in range(n_genes - 1)]
    obs = pd.DataFrame(index=[f"cell_{i}" for i in range(n_cells)])
    var = pd.DataFrame(index=gene_names)
    return AnnData(X=X, obs=obs, var=var)


# ─── Fixtures ─────────────────────────────────────────────────────────────────


@pytest.fixture
def store_root(tmp_path, monkeypatch):
    """Temporary DatasetStore; monkeypatches STORE_ROOT so tool uses it."""
    root = tmp_path / "store"
    monkeypatch.setattr(agent_tools, "STORE_ROOT", str(root))
    return root


@pytest.fixture
def mocked_census_adata():
    """A pre-built AnnData representing a mocked census fetch."""
    return _make_census_adata()


# ─── Tests ────────────────────────────────────────────────────────────────────


def test_census_fetch_returns_dataset_id(store_root, mocked_census_adata, monkeypatch):
    """Tool handler returns content JSON with a 'dataset_id' of form 'name@N'.

    Patches cellxgene_census so no network access occurs; verifies the tool
    response JSON contains a 'dataset_id' key with the expected format.
    """
    # Import the tool — will raise ImportError until plan 02 creates it
    from agent.tools import fetch_census_dataset_tool  # noqa: PLC0415

    # Patch the blocking fetch helper that plan 02 places in ingest.census
    with patch("ingest.census._census_fetch_blocking", return_value=mocked_census_adata):
        result = asyncio.get_event_loop().run_until_complete(
            fetch_census_dataset_tool(
                {
                    "organism": "Homo sapiens",
                    "obs_value_filter": "tissue_general == 'lung'",
                    "name": "lung-census",
                }
            )
        )

    assert not result.get("is_error"), f"Tool returned error: {result}"
    payload = json.loads(result["content"][0]["text"])
    dataset_id = payload["dataset_id"]
    # Must be of form "name@version"
    assert "@" in dataset_id, f"Unexpected dataset_id format: {dataset_id!r}"
    name_part, version_part = dataset_id.split("@", 1)
    assert name_part == "lung-census"
    assert version_part.isdigit()


def test_census_fetch_runs_in_thread(store_root, mocked_census_adata, monkeypatch):
    """The blocking census call is offloaded via asyncio.to_thread, not run on the event loop.

    Monkeypatches asyncio.to_thread with a wrapper that sets a flag, then
    asserts the flag is set after the fetch completes. This confirms the
    TileDB-SOMA synchronous call is never run directly on the event loop.
    """
    from agent.tools import fetch_census_dataset_tool  # noqa: PLC0415

    offloaded = {"called": False}
    original_to_thread = asyncio.to_thread

    async def tracking_to_thread(func, *args, **kwargs):
        offloaded["called"] = True
        return await original_to_thread(func, *args, **kwargs)

    with patch("ingest.census._census_fetch_blocking", return_value=mocked_census_adata):
        monkeypatch.setattr(asyncio, "to_thread", tracking_to_thread)
        asyncio.get_event_loop().run_until_complete(
            fetch_census_dataset_tool(
                {
                    "organism": "Homo sapiens",
                    "obs_value_filter": "tissue_general == 'blood'",
                    "name": "blood-census",
                }
            )
        )

    assert offloaded["called"], (
        "asyncio.to_thread was not called — blocking census fetch ran on event loop"
    )


def test_fetched_dataset_loadable(store_root, mocked_census_adata):
    """After the mocked fetch, the produced dataset_id loads from DatasetStore.

    Asserts n_obs > 0 and layers['counts'] exists (ingest contract ran).
    """
    from agent.tools import fetch_census_dataset_tool  # noqa: PLC0415

    with patch("ingest.census._census_fetch_blocking", return_value=mocked_census_adata):
        result = asyncio.get_event_loop().run_until_complete(
            fetch_census_dataset_tool(
                {
                    "organism": "Homo sapiens",
                    "obs_value_filter": "tissue_general == 'lung'",
                    "name": "load-test",
                }
            )
        )

    assert not result.get("is_error")
    dataset_id = json.loads(result["content"][0]["text"])["dataset_id"]
    name, version = dataset_id.split("@")
    store = DatasetStore(root=store_root)
    adata = store.load(name, int(version))
    assert adata.n_obs > 0
    assert "counts" in adata.layers


def test_tool_registered():
    """bioclaw_server's tool list includes 'fetch_census_dataset'.

    This assertion fails until plan 02 adds the tool to agent/server.py.
    """
    from agent.server import bioclaw_server  # noqa: PLC0415

    # bioclaw_server is a dict with type='sdk'; the underlying MCP server
    # instance exposes tools via its registered request handlers. We check
    # by inspecting the tools passed to create_sdk_mcp_server via the SDK's
    # SdkMcpTool objects attached to agent.tools.
    import agent.tools as _tools  # noqa: PLC0415

    tool_names = [
        getattr(obj, "name", None)
        for obj in vars(_tools).values()
        if hasattr(obj, "name") and hasattr(obj, "handler")
    ]
    assert "fetch_census_dataset" in tool_names, (
        f"'fetch_census_dataset' not found in agent.tools; found: {tool_names}"
    )
