"""Synthetic, in-repo, network-free 10x-format fixtures shared across all
Phase 1 (ingest + QC pipeline) tests.

Provides:
- tiny_mtx_dir: a tiny 10x MEX-format directory (matrix.mtx.gz,
  barcodes.tsv.gz, features.tsv.gz).
- tiny_h5_file: a tiny Cell Ranger-format HDF5 feature-barcode matrix file.
- synthetic_adata: an in-memory AnnData with raw integer counts in .X.

All three share the same "interesting" characteristics on purpose (MT-
prefixed genes, a duplicated gene symbol, an all-zero cell, an all-zero
gene) so downstream loaders/QC/store code has real edge cases to handle.
"""

import gzip
from pathlib import Path

import h5py
import numpy as np
import pandas as pd
import pytest
from anndata import AnnData
from scipy import sparse
from scipy.io import mmwrite

FEATURE_TYPE = "Gene Expression"
GENOME = "GRCh38"


def _gene_symbols(n_genes: int) -> list[str]:
    """First few symbols are fixed (MT- genes + one duplicate + one
    designated all-zero gene); the rest are generic filler names.
    """
    symbols = ["MT-CO1", "MT-ND1", "DUPGENE", "DUPGENE", "ZEROGENE"]
    symbols += [f"GENE{i}" for i in range(len(symbols), n_genes)]
    return symbols[:n_genes]


def _write_gz_lines(path: Path, lines) -> None:
    with gzip.open(path, "wt") as fh:
        for line in lines:
            fh.write(f"{line}\n")


def _write_mtx_gz(dest_gz_path: Path, matrix) -> None:
    """Write a sparse matrix as gzip-compressed MatrixMarket (.mtx.gz)."""
    tmp_path = dest_gz_path.parent / dest_gz_path.stem  # strip ".gz"
    mmwrite(str(tmp_path), matrix)
    with open(tmp_path, "rb") as f_in, gzip.open(dest_gz_path, "wb") as f_out:
        f_out.write(f_in.read())
    tmp_path.unlink()


@pytest.fixture
def tiny_mtx_dir(tmp_path) -> Path:
    """Writes a tiny 10x MEX-format directory (matrix.mtx.gz,
    barcodes.tsv.gz, features.tsv.gz) and returns its Path.
    ~18 genes x 40 cells. Includes 2 MT- genes, one duplicated gene symbol
    (two Ensembl IDs), one all-zero cell, and one all-zero gene.
    """
    n_genes, n_cells = 18, 40
    rng = np.random.default_rng(0)

    counts = rng.poisson(lam=2, size=(n_genes, n_cells)).astype(np.int64)
    counts[4, :] = 0  # ZEROGENE: all-zero gene (row)
    counts[:, 0] = 0  # first barcode: all-zero cell (column)
    matrix = sparse.csr_matrix(counts)

    mtx_dir = tmp_path / "tiny_mtx"
    mtx_dir.mkdir()

    gene_ids = [f"ENSG{i:011d}" for i in range(n_genes)]
    gene_symbols = _gene_symbols(n_genes)
    barcodes = [f"BARCODE{i:04d}-1" for i in range(n_cells)]

    _write_gz_lines(
        mtx_dir / "features.tsv.gz",
        (f"{gid}\t{sym}\t{FEATURE_TYPE}" for gid, sym in zip(gene_ids, gene_symbols)),
    )
    _write_gz_lines(mtx_dir / "barcodes.tsv.gz", barcodes)
    _write_mtx_gz(mtx_dir / "matrix.mtx.gz", matrix)

    return mtx_dir


@pytest.fixture
def tiny_h5_file(tmp_path) -> Path:
    """Writes a tiny Cell Ranger-format HDF5 feature-barcode matrix file
    (/matrix/{data,indices,indptr,shape,barcodes},
    /matrix/features/{id,name,feature_type,genome}) and returns its Path.
    Independently constructed from tiny_mtx_dir; same shape/characteristics.
    """
    n_genes, n_cells = 18, 40
    rng = np.random.default_rng(1)

    counts = rng.poisson(lam=2, size=(n_genes, n_cells)).astype(np.int64)
    counts[4, :] = 0  # ZEROGENE: all-zero gene
    counts[:, 0] = 0  # first barcode: all-zero cell
    csc = sparse.csc_matrix(counts)  # CSC over cells, matching CellRanger H5 layout

    gene_ids = [f"ENSG{i:011d}" for i in range(n_genes)]
    gene_symbols = _gene_symbols(n_genes)
    barcodes = [f"BARCODE{i:04d}-1" for i in range(n_cells)]

    h5_path = tmp_path / "tiny_10x.h5"
    with h5py.File(h5_path, "w") as f:
        matrix_grp = f.create_group("matrix")
        matrix_grp.create_dataset("data", data=csc.data.astype(np.int32))
        matrix_grp.create_dataset("indices", data=csc.indices.astype(np.int32))
        matrix_grp.create_dataset("indptr", data=csc.indptr.astype(np.int32))
        matrix_grp.create_dataset("shape", data=np.array([n_genes, n_cells], dtype=np.int64))
        matrix_grp.create_dataset("barcodes", data=np.array(barcodes, dtype="S"))

        features_grp = matrix_grp.create_group("features")
        features_grp.create_dataset("id", data=np.array(gene_ids, dtype="S"))
        features_grp.create_dataset("name", data=np.array(gene_symbols, dtype="S"))
        features_grp.create_dataset(
            "feature_type", data=np.array([FEATURE_TYPE] * n_genes, dtype="S")
        )
        features_grp.create_dataset("genome", data=np.array([GENOME] * n_genes, dtype="S"))

    return h5_path


@pytest.fixture
def synthetic_adata() -> AnnData:
    """Returns an in-memory AnnData with raw integer counts already in .X
    (sparse csr_matrix), NOT yet through loaders.py or the counts-layer
    contract. 20 genes x 50 cells. Includes 3 MT- genes with meaningfully
    higher counts on a subset of cells, one all-zero cell, one all-zero
    gene, and enough spread in per-cell gene counts to visibly change
    filtering behavior under a min_genes_per_cell threshold.
    """
    n_genes, n_cells = 20, 50
    rng = np.random.default_rng(2)

    counts = rng.poisson(lam=2, size=(n_cells, n_genes)).astype(np.int64)

    mt_idx = [0, 1, 2]
    high_mt_cells = rng.choice(n_cells, size=10, replace=False)
    for gi in mt_idx:
        counts[high_mt_cells, gi] += rng.integers(20, 50, size=len(high_mt_cells))

    counts[:, 5] = 0  # all-zero gene
    counts[0, :] = 0  # all-zero cell (overrides any MT boost on cell 0)

    gene_names = ["MT-CO1", "MT-ND1", "MT-ND2"] + [f"GENE{i}" for i in range(3, n_genes)]
    cell_names = [f"CELL{i:04d}" for i in range(n_cells)]

    X = sparse.csr_matrix(counts)
    adata = AnnData(
        X=X,
        obs=pd.DataFrame(index=cell_names),
        var=pd.DataFrame(index=gene_names),
    )
    return adata
