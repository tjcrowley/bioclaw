"""DATA-01 network round-trip smoke test for the census fetch tool.

Gated by the `census_data` pytest marker and the CENSUS_DATA environment
variable. Never runs in fast/CI mode. Requires real S3 access to
cellxgene-census and a live `fetch_census_dataset_tool` (plan 02).
"""

import json
import os

import pytest

import agent.tools as agent_tools
from ingest.store import DatasetStore


@pytest.mark.census_data
@pytest.mark.skipif(
    not os.environ.get("CENSUS_DATA"),
    reason="Set CENSUS_DATA=1 to run real census network round-trip tests",
)
def test_census_real_fetch_returns_cells(tmp_path, monkeypatch):
    """Real census fetch with a tight filter returns at least one cell.

    Uses a filter that returns a small but non-empty result to keep the
    round-trip fast: blood primary cells from Homo sapiens is a stable,
    small-ish slice of the census.

    Asserts:
    - Tool returns no error
    - dataset_id is of form 'name@N'
    - Loaded dataset has n_obs >= 1 and layers['counts'] present
    """
    import asyncio  # noqa: PLC0415

    from agent.tools import fetch_census_dataset_tool  # noqa: PLC0415

    store_root = tmp_path / "store"
    monkeypatch.setattr(agent_tools, "STORE_ROOT", str(store_root))
    monkeypatch.setenv("BIOCLAW_WEB_PASSWORD", "testpass")

    result = asyncio.run(
        fetch_census_dataset_tool.handler(
            {
                "organism": "Homo sapiens",
                "obs_value_filter": "tissue_general == 'blood' and is_primary_data == True",
                "name": "smoke-blood",
            }
        )
    )

    assert not result.get("is_error"), f"Tool returned error: {result}"
    dataset_id = json.loads(result["content"][0]["text"])["dataset_id"]
    assert "@" in dataset_id, f"Unexpected dataset_id format: {dataset_id!r}"

    name, version = dataset_id.split("@")
    store = DatasetStore(root=store_root)
    adata = store.load(name, int(version))
    assert adata.n_obs >= 1, "Census fetch returned 0 cells"
    assert "counts" in adata.layers, "layers['counts'] missing after ingest"
