"""Smoke tests proving the synthetic fixtures in conftest.py are
structurally valid, network-free inputs.

These tests exist so every later plan can build on `tiny_mtx_dir`,
`tiny_h5_file`, `synthetic_adata`, and `structured_adata` with confidence,
without re-verifying fixture shape/content themselves.
"""

import numpy as np
import scanpy as sc
from scipy import sparse


def test_tiny_mtx_dir_reads_with_scanpy(tiny_mtx_dir):
    adata = sc.read_10x_mtx(
        tiny_mtx_dir,
        var_names="gene_symbols",
        make_unique=True,
        gex_only=True,
        cache=False,
    )

    assert adata.n_obs > 0
    assert adata.n_vars > 0

    mt_genes = [name for name in adata.var_names if name.startswith("MT-")]
    assert len(mt_genes) >= 2

    # the duplicated gene symbol should be resolved to two distinct unique
    # names by make_unique=True (e.g. "GENE", "GENE-1")
    assert any(name.endswith("-1") for name in adata.var_names)


def test_tiny_h5_file_reads_with_scanpy(tiny_h5_file):
    adata = sc.read_10x_h5(tiny_h5_file)

    assert adata.n_obs > 0
    assert adata.n_vars > 0
    # var_names dedup is NOT automatic for this reader -- not asserted here,
    # that's Plan 01-02's (loaders.py) job.


def test_synthetic_adata_structure(synthetic_adata):
    adata = synthetic_adata

    assert sparse.issparse(adata.X)
    assert isinstance(adata.X, sparse.csr_matrix)

    dense = adata.X.toarray()
    assert np.array_equal(dense, dense.astype(int)), "X must be integer-valued"

    mt_genes = [name for name in adata.var_names if name.startswith("MT-")]
    assert len(mt_genes) >= 3

    cell_sums = np.asarray(adata.X.sum(axis=1)).ravel()
    gene_sums = np.asarray(adata.X.sum(axis=0)).ravel()
    assert (cell_sums == 0).any(), "expected at least one all-zero cell"
    assert (gene_sums == 0).any(), "expected at least one all-zero gene"


def test_structured_adata_structure(structured_adata):
    adata = structured_adata

    assert adata.shape == (200, 80)

    assert sparse.issparse(adata.X)
    dense = adata.X.toarray()
    assert np.array_equal(dense, dense.astype(int)), "X must be integer-valued"

    assert set(adata.obs["true_population"].unique()) == {"A", "B"}

    pop_a_mask = (adata.obs["true_population"] == "A").to_numpy()
    pop_b_mask = (adata.obs["true_population"] == "B").to_numpy()

    marker_genes = dense[:, 0:15]
    mean_a = marker_genes[pop_a_mask].mean()
    mean_b = marker_genes[pop_b_mask].mean()
    assert mean_a > 2 * mean_b, (
        "expected genes 0-14 to be meaningfully elevated in population A "
        "vs. population B, proving the fixture has separable structure"
    )
