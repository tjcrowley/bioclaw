"""Real, unmocked end-to-end Geneformer in-silico-perturbation test (Plan 13-04 Task 2/3).

Requires a real `Geneformer-V1-10M` checkpoint and the isolated
`geneformer_worker/.venv` -- neither is guaranteed to exist in CI, hence the
`geneformer_smoke` marker excluding this from the fast/default test run (see
pyproject.toml's `markers` and tests/test_agent_tools.py's fully-mocked
`test_predict_perturbation_geneformer_tool_round_trip` for the CI-safe
equivalent).

Unlike that mocked test, nothing here is monkeypatched:
`perturbation.pipeline.predict_geneformer()` runs for real, including the
real subprocess call into `geneformer_worker/.venv` that loads the
Geneformer checkpoint, tokenizes, embeds, perturbs, and aggregates cosine
shifts (FM-02).
"""

import asyncio
import time
from pathlib import Path

import numpy as np
import pytest
from anndata import AnnData

from ingest.store import DatasetStore
from perturbation.pipeline import predict_geneformer
from perturbation.summary import GeneShift

pytestmark = pytest.mark.geneformer_smoke

GENEFORMER_WORKER_PYTHON = Path("geneformer_worker/.venv/bin/python")

# Real, well-known human housekeeping/marker genes with their canonical
# (unversioned) Ensembl gene IDs -- an unmocked Geneformer run needs genes
# that actually exist in Geneformer's token vocabulary, not placeholder
# symbols like test_agent_tools.py's "GENE00"/"ENSG00000000000".
REAL_GENES = {
    "ACTB": "ENSG00000075624",
    "GAPDH": "ENSG00000111640",
    "B2M": "ENSG00000166710",
    "TUBB": "ENSG00000196230",
    "RPL13A": "ENSG00000142541",
    "EEF1A1": "ENSG00000156508",
    "PPIA": "ENSG00000196262",
    "YWHAZ": "ENSG00000164924",
    "HPRT1": "ENSG00000165704",
    "TBP": "ENSG00000112592",
    "PGK1": "ENSG00000102144",
    "SDHA": "ENSG00000073578",
    "POLR2A": "ENSG00000181222",
    "GUSB": "ENSG00000169919",
    "UBC": "ENSG00000150991",
    "ACTG1": "ENSG00000184009",
    "MYC": "ENSG00000136997",
    "TP53": "ENSG00000141510",
}

TARGET_GENE = "ACTB"


@pytest.fixture
def real_gene_adata() -> AnnData:
    """A small, real-gene AnnData: 24 cells x 18 genes, integer counts,
    obs["n_counts"] set (raw count sums per cell, required by Geneformer's
    tokenizer), and var["gene_ids"] populated with real Ensembl IDs so
    validate_ensembl_ids() succeeds against genuinely tokenizable genes.
    """
    rng = np.random.default_rng(13)
    gene_symbols = list(REAL_GENES.keys())
    n_cells, n_genes = 24, len(gene_symbols)
    X = rng.poisson(lam=5.0, size=(n_cells, n_genes)).astype(np.float32)

    adata = AnnData(X=X)
    adata.var_names = gene_symbols
    adata.var["gene_ids"] = [REAL_GENES[g] for g in gene_symbols]
    adata.obs_names = [f"cell{i}" for i in range(n_cells)]
    adata.obs["n_counts"] = X.sum(axis=1)
    return adata


def test_predict_geneformer_real_end_to_end(tmp_path, real_gene_adata):
    if not GENEFORMER_WORKER_PYTHON.exists():
        pytest.skip(
            f"{GENEFORMER_WORKER_PYTHON} does not exist -- geneformer_worker/ "
            "environment not set up on this machine (see geneformer_worker/README.md)"
        )

    store = DatasetStore(root=tmp_path)
    store.save("geneformer-pilot", real_gene_adata)

    start = time.monotonic()
    dataset_id, summary = asyncio.run(
        predict_geneformer("geneformer-pilot", TARGET_GENE, store_root=tmp_path)
    )
    latency = time.monotonic() - start
    print(f"\npredict_geneformer real end-to-end latency: {latency:.1f}s")

    call = summary["call"]
    assert call["method"] == "geneformer"
    assert call["target_gene"] == TARGET_GENE
    assert call["target_ensembl_id"] == REAL_GENES[TARGET_GENE]
    assert isinstance(call["match_rate"], float)
    assert 0.0 <= call["match_rate"] <= 1.0

    ranked_genes = call["ranked_genes"]
    assert len(ranked_genes) > 0
    for gene in ranked_genes:
        assert isinstance(gene["gene"], str)
        assert isinstance(gene["cosine_shift"], float)
    # Not every affected gene's cosine_shift should be exactly 0.0 -- an
    # all-zero result would indicate the silent-tokenization-failure mode
    # from 13-RESEARCH.md Pitfall 2, even if the assertions above technically
    # pass on type alone.
    assert any(gene["cosine_shift"] != 0.0 for gene in ranked_genes)

    # Proves the two model outputs are genuinely distinct end to end, not
    # just in their Python type signatures: GeneformerPerturbationCall has
    # no predicted_expression field at all.
    assert "predicted_expression" not in call
