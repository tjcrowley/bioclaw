"""Synthetic, in-repo, network-free fixtures shared across Phase 1 (ingest +
QC pipeline), Phase 2 (analysis), and Phase 5 (perturbation) tests.

Provides:
- tiny_mtx_dir: a tiny 10x MEX-format directory (matrix.mtx.gz,
  barcodes.tsv.gz, features.tsv.gz).
- tiny_h5_file: a tiny Cell Ranger-format HDF5 feature-barcode matrix file.
- synthetic_adata: an in-memory AnnData with raw integer counts in .X.
- structured_adata: an in-memory AnnData with genuine, testable
  cluster/population structure for Phase 2 clustering/DE tests.

The first three share the same "interesting" characteristics on purpose (MT-
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


@pytest.fixture
def structured_adata() -> AnnData:
    """Returns an in-memory AnnData (raw integer counts, sparse csr_matrix
    in .X) with genuine, testable cluster/population structure -- unlike
    `synthetic_adata`, which is deliberately too small/unstructured for
    clustering and DE (see Phase 2 research Pitfall 4).

    ~200 cells x ~80 genes, two well-separated pseudo-populations of ~100
    cells each:
    - Population "A" (cells 0-99): genes 0-14 elevated (Poisson lam=15)
      vs. background (lam=2) for all other genes.
    - Population "B" (cells 100-199): genes 15-29 elevated (Poisson lam=15)
      vs. the same background.
    - All other genes/cells: background lam=2 Poisson noise only.

    Ground truth population label is stored in `adata.obs["true_population"]`
    ("A"/"B") so Wave 1's `diffexp.py` tests can run DE directly against a
    known-correct grouping without depending on `cluster.py`'s output, and
    `cluster.py` tests can sanity-check that Leiden roughly recovers this
    structure.
    """
    n_genes, n_cells = 80, 200
    n_pop = 100
    rng = np.random.default_rng(3)

    background = rng.poisson(lam=2, size=(n_cells, n_genes)).astype(np.int64)

    marker_a = rng.poisson(lam=15, size=(n_pop, 15)).astype(np.int64)
    marker_b = rng.poisson(lam=15, size=(n_pop, 15)).astype(np.int64)

    counts = background
    counts[0:n_pop, 0:15] = marker_a
    counts[n_pop : 2 * n_pop, 15:30] = marker_b

    gene_names = [f"GENE{i:02d}" for i in range(n_genes)]
    cell_names = [f"CELL{i:04d}" for i in range(n_cells)]

    X = sparse.csr_matrix(counts)
    obs = pd.DataFrame(
        {"true_population": ["A"] * n_pop + ["B"] * (n_cells - n_pop)},
        index=cell_names,
    )
    adata = AnnData(
        X=X,
        obs=obs,
        var=pd.DataFrame(index=gene_names),
    )
    return adata


@pytest.fixture
def perturbation_adata() -> AnnData:
    """Returns an in-memory AnnData (raw integer counts, sparse csr_matrix
    in .X) for Phase 5 (perturbation-response) tests.

    Shape: 30 genes x 350 cells.

    obs["target_gene"] values:
    - "non-targeting" (control): 100 cells, background Poisson lam=2 counts only.
    - "GENE00" through "GENE04": 50 cells each (5 perturbations x 50 cells = 250 cells),
      each with a fixed deterministic additive shift on top of the control background.

    var_names: ["GENE00", "GENE01", ..., "GENE29"] (30 genes total).

    obs["target_gene"] and the control token "non-targeting" match cell-eval's
    DEFAULT_PERT_COL / DEFAULT_CTRL constants (05-RESEARCH.md Pitfall 4).
    Do NOT rename these without updating every Phase 5 test that depends on
    this fixture.

    Per-gene shift vectors (added on top of Poisson lam=2 background, clipped
    to non-negative integers):
    - "GENE00": shift +10 on gene index 0 only
    - "GENE01": shift +10 on gene index 1 only
    - "GENE02": shift +10 on gene index 2 only
    - "GENE03": shift +10 on gene index 3 only
    - "GENE04": shift +10 on gene index 4 only

    Each perturbed gene's shift is applied only to its own gene index so
    Plans 02/03's tests can assert per-gene discrimination: the mean expression
    of GENE00 in "GENE00"-perturbed cells is ~12, while the mean of GENE00 in
    any other condition's cells is ~2. This makes each perturbation's expected
    shift vector exactly recoverable.

    RNG seed: 4 (next unused after Phase 1-2's seeds 0/1/2/3).
    """
    n_genes, n_cells_control = 30, 100
    n_perts = 5  # GENE00..GENE04
    n_cells_per_pert = 50
    rng = np.random.default_rng(4)

    gene_names = [f"GENE{i:02d}" for i in range(n_genes)]

    # Build control cells: background Poisson lam=2 only.
    control_counts = rng.poisson(lam=2, size=(n_cells_control, n_genes)).astype(np.int64)
    control_labels = ["non-targeting"] * n_cells_control

    # Build perturbed cells: background + fixed additive shift on the target gene index.
    # shift[i] = +10 on gene index i only (all other genes: background only).
    # Document shifts verbatim so Plan 02/03 tests can assert exact recovery:
    #   GENE00 -> shift[0] = 10, GENE01 -> shift[1] = 10, ... GENE04 -> shift[4] = 10
    pert_counts_list = []
    pert_labels = []
    for pert_idx in range(n_perts):
        pert_gene = gene_names[pert_idx]  # "GENE00" through "GENE04"
        bg = rng.poisson(lam=2, size=(n_cells_per_pert, n_genes)).astype(np.int64)
        bg[:, pert_idx] += 10  # fixed +10 shift on the target gene only
        pert_counts_list.append(bg)
        pert_labels.extend([pert_gene] * n_cells_per_pert)

    # Concatenate: 100 control cells + 250 perturbed cells = 350 cells total.
    all_counts = np.concatenate([control_counts] + pert_counts_list, axis=0)
    all_labels = control_labels + pert_labels
    n_total = n_cells_control + n_perts * n_cells_per_pert  # 350

    cell_names = [f"CELL{i:04d}" for i in range(n_total)]

    X = sparse.csr_matrix(all_counts)
    obs = pd.DataFrame(
        {"target_gene": all_labels},
        index=cell_names,
    )
    adata = AnnData(
        X=X,
        obs=obs,
        var=pd.DataFrame(index=gene_names),
    )
    return adata
