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


def test_reingest_same_name_versions(tiny_mtx_dir, tmp_path):
    """Re-ingesting the same source path under the same name produces a
    new version, not a silent overwrite -- confirms INGEST-03 versioning
    increments at the full-pipeline level, not just inside store.py."""
    store_root = tmp_path / "store"

    first = pipeline.ingest_10x(
        str(tiny_mtx_dir),
        "demo",
        qc_config=QCConfig(min_genes_per_cell=1),
        store_root=str(store_root),
    )
    second = pipeline.ingest_10x(
        str(tiny_mtx_dir),
        "demo",
        qc_config=QCConfig(min_genes_per_cell=1),
        store_root=str(store_root),
    )

    assert first == "demo@1"
    assert second == "demo@2"


def test_already_cell_called_input_ingests_cleanly(tiny_mtx_dir, tmp_path):
    """A .mtx fixture representing an already-cell-called
    filtered_feature_bc_matrix-style input (all barcodes real cells, no
    empty droplets) ingests successfully with n_cells_after close to
    n_cells_before under lenient QC. tiny_mtx_dir has exactly one
    deliberately all-zero cell (simulating the one non-cell barcode);
    everything else should survive min_genes=1."""
    store_root = tmp_path / "store"

    dataset_id = pipeline.ingest_10x(
        str(tiny_mtx_dir),
        "filtered-like",
        qc_config=QCConfig(min_genes_per_cell=1, max_pct_mt=None),
        store_root=str(store_root),
    )

    adata = DatasetStore(root=str(store_root)).load("filtered-like")
    qc_log = adata.uns["qc"]

    assert dataset_id == "filtered-like@1"
    # Only the deliberately all-zero cell should be dropped by min_genes=1.
    assert qc_log["n_cells_after"] >= qc_log["n_cells_before"] - 1


def test_qc_config_removing_all_cells_does_not_raise(tiny_mtx_dir, tmp_path):
    """ingest_10x() with a qc_config strict enough to remove every cell
    does not raise -- it completes, and the stored/loaded result has
    n_obs == 0 with adata.uns['qc'] explaining the full removal (proves
    qc.py's empty-result handling survives the full pipeline, including
    the store.save()/write_h5ad() round trip of a 0-obs AnnData)."""
    store_root = tmp_path / "store"

    dataset_id = pipeline.ingest_10x(
        str(tiny_mtx_dir),
        "empty-result",
        qc_config=QCConfig(min_genes_per_cell=100_000),
        store_root=str(store_root),
    )

    assert dataset_id == "empty-result@1"

    adata = DatasetStore(root=str(store_root)).load("empty-result")

    assert adata.n_obs == 0
    assert adata.uns["qc"]["n_cells_after"] == 0
    assert adata.uns["qc"]["removed_by_reason"]["low_gene_count"] > 0
