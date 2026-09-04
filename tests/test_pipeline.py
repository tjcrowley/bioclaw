"""Integration tests for ingest/pipeline.py -- proves loaders.py,
contract.py, qc.py, and store.py wire together correctly end to end
(INGEST-01/02/03, QC-01/02, composed rather than tested in isolation).
"""

from ingest import pipeline
from ingest.contract import verify_counts_integrity
from ingest.qc import QCConfig
from ingest.store import DatasetStore


def test_ingest_10x_mtx_end_to_end(tiny_mtx_dir, tmp_path):
    """A single ingest_10x() call on a .mtx directory produces a dataset
    that is loadable, has an intact counts contract, and has a logged QC
    run -- every Wave 1 module's output present on the stored result."""
    store_root = tmp_path / "store"

    dataset_id = pipeline.ingest_10x(
        str(tiny_mtx_dir),
        "demo",
        qc_config=QCConfig(min_genes_per_cell=1),
        store_root=str(store_root),
    )

    assert dataset_id == "demo@1"

    adata = DatasetStore(root=str(store_root)).load("demo")

    assert "counts" in adata.layers
    assert verify_counts_integrity(adata) is True

    expected_cols = [
        "pct_counts_mt",
        "n_genes_by_counts",
        "total_counts",
        "doublet_score",
        "predicted_doublet",
    ]
    for col in expected_cols:
        assert col in adata.obs.columns

    assert "qc" in adata.uns
    assert adata.uns["qc"]["config"]["min_genes_per_cell"] == 1


def test_ingest_10x_h5_end_to_end(tiny_h5_file, tmp_path):
    """Equivalent end-to-end behavior for the .h5 input path."""
    store_root = tmp_path / "store"

    dataset_id = pipeline.ingest_10x(
        str(tiny_h5_file),
        "demo-h5",
        qc_config=QCConfig(min_genes_per_cell=1),
        store_root=str(store_root),
    )

    assert dataset_id == "demo-h5@1"

    adata = DatasetStore(root=str(store_root)).load("demo-h5")

    assert "counts" in adata.layers
    assert verify_counts_integrity(adata) is True
    assert "qc" in adata.uns
    assert adata.uns["qc"]["config"]["min_genes_per_cell"] == 1


def test_qc_config_threads_through_pipeline(tiny_mtx_dir, tmp_path):
    """A custom qc_config changes n_cells_after relative to the default
    config, proving the config actually threads through the whole
    pipeline (not just qc.run() in isolation)."""
    store_root = tmp_path / "store"

    pipeline.ingest_10x(str(tiny_mtx_dir), "default-cfg", store_root=str(store_root))
    pipeline.ingest_10x(
        str(tiny_mtx_dir),
        "lenient-cfg",
        qc_config=QCConfig(min_genes_per_cell=1),
        store_root=str(store_root),
    )

    default_adata = DatasetStore(root=str(store_root)).load("default-cfg")
    lenient_adata = DatasetStore(root=str(store_root)).load("lenient-cfg")

    assert (
        lenient_adata.uns["qc"]["n_cells_after"]
        != default_adata.uns["qc"]["n_cells_after"]
    )
