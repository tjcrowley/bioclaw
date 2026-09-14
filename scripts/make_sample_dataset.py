"""Generate a small, synthetic 10x MEX-format demo dataset.

Standalone CLI script (no pytest dependency) that writes a synthetic 10x
Genomics MEX-format directory (matrix.mtx.gz, barcodes.tsv.gz,
features.tsv.gz) with real marker-gene structure, mirroring
tests/conftest.py::analyzable_mtx_dir's generation approach (300 genes x 60
cells, two marker-gene pseudo populations at Poisson lam=20 vs. lam=3
background) but writing to a real filesystem path instead of pytest's
tmp_path, so the output survives outside a test session for manual
upload-flow verification (see Plan 10-02).

Usage:
    python scripts/make_sample_dataset.py              # writes to data/demo_10x/
    python scripts/make_sample_dataset.py --out PATH    # writes to PATH
    python scripts/make_sample_dataset.py --force       # overwrite existing non-empty dir
"""

import argparse
import gzip
from pathlib import Path

import numpy as np
from scipy import sparse
from scipy.io import mmwrite

FEATURE_TYPE = "Gene Expression"
GENOME = "GRCh38"

DEFAULT_OUT_DIR = Path("data/demo_10x")


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


def generate_sample_dataset(out_dir: Path) -> None:
    """Generate a synthetic 10x MEX-format directory at ``out_dir``.

    300 genes x 60 cells, two marker-gene pseudo populations (cells 0-29
    elevated on genes 0-14, cells 30-59 elevated on genes 15-29) against a
    Poisson lam=3 background, so downstream QC/clustering/DE all find real
    structure -- mirrors tests/conftest.py::analyzable_mtx_dir.
    """
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    n_genes, n_cells, n_pop = 300, 60, 30
    rng = np.random.default_rng(42)

    counts = rng.poisson(lam=3, size=(n_cells, n_genes)).astype(np.int64)
    counts[0:n_pop, 0:15] = rng.poisson(lam=20, size=(n_pop, 15)).astype(np.int64)
    counts[n_pop : 2 * n_pop, 15:30] = rng.poisson(lam=20, size=(n_pop, 15)).astype(
        np.int64
    )
    matrix = sparse.csr_matrix(counts.T)  # genes x cells, MatrixMarket convention

    gene_ids = [f"ENSG{i:011d}" for i in range(n_genes)]
    gene_symbols = ["MT-CO1", "MT-ND1"] + [f"GENE{i:03d}" for i in range(2, n_genes)]
    barcodes = [f"BARCODE{i:04d}-1" for i in range(n_cells)]

    _write_gz_lines(
        out_dir / "features.tsv.gz",
        (f"{gid}\t{sym}\t{FEATURE_TYPE}" for gid, sym in zip(gene_ids, gene_symbols)),
    )
    _write_gz_lines(out_dir / "barcodes.tsv.gz", barcodes)
    _write_mtx_gz(out_dir / "matrix.mtx.gz", matrix)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate a synthetic 10x MEX-format demo dataset for "
        "manual bioclaw webapp upload-flow verification."
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=DEFAULT_OUT_DIR,
        help=f"Output directory (default: {DEFAULT_OUT_DIR})",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite an existing non-empty output directory",
    )
    args = parser.parse_args()

    out_dir: Path = args.out
    if out_dir.exists() and any(out_dir.iterdir()) and not args.force:
        raise SystemExit(
            f"Refusing to overwrite non-empty directory: {out_dir} "
            "(pass --force to overwrite)"
        )

    generate_sample_dataset(out_dir)
    print(f"Wrote synthetic 10x MEX dataset to {out_dir}")


if __name__ == "__main__":
    main()
