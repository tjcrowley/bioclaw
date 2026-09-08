"""Real, unmocked end-to-end scGPT annotation test (Plan 04-05 Task 2/3).

Requires a real `bio_fm_worker/checkpoints/scGPT_human/` checkpoint and the
isolated `bio_fm_worker/.venv` -- neither exists in CI, hence the
`bio_fm_smoke` marker excluding this from the fast/default test run (see
pyproject.toml's `markers` and tests/test_agent_tools.py's fully-mocked
`test_annotate_cell_type_tool_round_trip` for the CI-safe equivalent).

Unlike that mocked test, nothing here is monkeypatched: `ingest_10x_tool`,
`analyze_dataset_tool`, and `annotate_cell_type_tool` all run for real,
including the real `dc.op.resource(name="PanglaoDB")` network fetch (ORA
baseline) and the real subprocess call into `bio_fm_worker/.venv` that
loads the scGPT checkpoint and embeds cells (FM side). `_marker_mtx_dir`
uses genuine, verified-in-vocab marker gene symbols (not the placeholder
`GENE003`-style names `analyzable_mtx_dir` in test_agent_tools.py uses) --
that fixture's fake symbols have no overlap with real marker/vocab
resources, which does not survive an unmocked run (see 04-05-SUMMARY.md
for the two real bugs this surfaced and fixed: decoupler's
`dc.op.resource()` output shape, and a pandas-3.0/anndata-0.13-vs-0.10.9
on-disk incompatibility across the venv boundary).
"""

import asyncio
import gzip
import json
import time
from pathlib import Path

import numpy as np
import pytest
from scipy import sparse
from scipy.io import mmwrite

import agent.tools as agent_tools
from agent.tools import analyze_dataset_tool, annotate_cell_type_tool, ingest_10x_tool

pytestmark = pytest.mark.bio_fm_smoke

FEATURE_TYPE = "Gene Expression"

# Real, canonical marker genes (all confirmed present in both PanglaoDB and
# the scGPT whole-human vocab) -- an unmocked ORA/scGPT run needs actual
# marker-gene signal, not placeholder symbols.
T_CELL_MARKERS = [
    "CD3D", "CD3E", "CD3G", "CD2", "CD5", "CD6", "TRAC", "IL7R", "LCK", "CD247",
]
MONOCYTE_MARKERS = [
    "CD14", "LYZ", "FCN1", "S100A8", "S100A9", "CD68", "CSF1R", "ITGAM", "FCGR3A", "VCAN",
]


def _write_gz_lines(path: Path, lines) -> None:
    with gzip.open(path, "wt") as fh:
        for line in lines:
            fh.write(f"{line}\n")


@pytest.fixture
def marker_mtx_dir(tmp_path) -> Path:
    """A 10x MEX directory with two real marker-gene populations (T cell,
    Monocyte), sized to survive default QC (`min_genes_per_cell=200`) and
    produce genuine cluster structure -- see module docstring for why this
    can't reuse `analyzable_mtx_dir`'s placeholder gene symbols.
    """
    n_genes, n_cells, n_pop = 300, 60, 30
    rng = np.random.default_rng(42)

    counts = rng.poisson(lam=3, size=(n_cells, n_genes)).astype(np.int64)
    counts[0:n_pop, 0:10] = rng.poisson(lam=20, size=(n_pop, 10)).astype(np.int64)
    counts[n_pop : 2 * n_pop, 10:20] = rng.poisson(lam=20, size=(n_pop, 10)).astype(
        np.int64
    )
    matrix = sparse.csr_matrix(counts.T)  # genes x cells, MatrixMarket convention

    mtx_dir = tmp_path / "marker_mtx"
    mtx_dir.mkdir()

    gene_symbols = (
        T_CELL_MARKERS + MONOCYTE_MARKERS + [f"GENE{i:03d}" for i in range(20, n_genes)]
    )
    gene_ids = [f"ENSG{i:011d}" for i in range(n_genes)]
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


def test_annotate_cell_type_tool_real_scgpt_and_baseline(
    tmp_path, marker_mtx_dir, monkeypatch
):
    """Full, unmocked ingest -> analyze -> annotate round trip. Measures
    wall-clock latency of the annotate call and asserts both the real
    scGPT (FM) and real decoupler ORA (baseline) sides returned a
    plausible, non-empty result.
    """
    monkeypatch.setattr(agent_tools, "STORE_ROOT", str(tmp_path))

    asyncio.run(
        ingest_10x_tool.handler({"path": str(marker_mtx_dir), "name": "pilot"})
    )
    asyncio.run(analyze_dataset_tool.handler({"name": "pilot"}))

    start = time.monotonic()
    result = asyncio.run(annotate_cell_type_tool.handler({"name": "pilot"}))
    elapsed = time.monotonic() - start
    print(f"\nannotate_cell_type_tool real end-to-end latency: {elapsed:.1f}s")

    assert result["is_error"] is False, result["content"]
    payload = json.loads(result["content"][0]["text"])

    assert payload["baseline_calls"], "real decoupler ORA baseline returned no calls"
    assert payload["fm_calls"], "real scGPT FM call returned no calls"

    for call in payload["fm_calls"]:
        assert call["label"], "scGPT call missing a label"
        assert call["ontology_term_id"], "scGPT call missing an ontology term id"
        assert 0.0 <= call["confidence"] <= 1.0
