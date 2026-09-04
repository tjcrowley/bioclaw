"""Tests for analysis/cluster.py -- neighbor graph, Leiden (igraph flavor),
UMAP, size guards, and ClusterSummary construction (ANLYS-02).

Uses the structured_adata fixture (~200 cells x ~80 genes, genuine
cluster structure) for the main behavior assertions, PCA'd directly in
test setup (not via analysis.preprocess, per plan spec), and Phase 1's
synthetic_adata fixture (20 genes x 50 cells) for the small-input size
guard.
"""

from dataclasses import asdict

import scanpy as sc

from analysis import cluster
from analysis.summary import ClusterSummary


def _pca(adata, n_comps=10):
    """Minimal normalize -> log1p -> pca setup, standalone from
    analysis.preprocess per the plan's test-isolation instruction."""
    adata = adata.copy()
    sc.pp.normalize_total(adata)
    sc.pp.log1p(adata)
    n_comps = min(n_comps, adata.n_obs - 1, adata.n_vars - 1)
    sc.pp.pca(adata, n_comps=n_comps)
    return adata


def test_cluster_finds_multiple_clusters_and_umap(structured_adata):
    """cluster() on a PCA'd structured_adata produces >=2 Leiden clusters
    and a 2D UMAP embedding (ANLYS-02)."""
    adata = _pca(structured_adata)

    result, _ = cluster.cluster(adata, resolution=1.0, n_neighbors=15, random_state=0)

    assert "leiden" in result.obs
    assert result.obs["leiden"].nunique() >= 2

    assert "X_umap" in result.obsm
    assert result.obsm["X_umap"].shape == (result.n_obs, 2)


def test_cluster_never_passes_directed_true(structured_adata):
    """Regression guard for Pitfall 2: flavor="igraph" must never be
    called with directed=True, or sc.tl.leiden raises ValueError.
    Calling cluster() successfully (no ValueError) is the assertion."""
    adata = _pca(structured_adata)

    # If cluster() ever passed directed=True internally, this call would
    # raise ValueError: "Cannot use igraph's leiden implementation with a
    # directed graph."
    result, _ = cluster.cluster(adata, resolution=1.0, n_neighbors=15, random_state=0)
    assert "leiden" in result.obs


def test_cluster_leiden_labels_deterministic(structured_adata):
    """Running cluster() twice with the same random_state on the same
    PCA'd input produces identical Leiden label assignments. UMAP
    coordinate equality is deliberately NOT asserted (Pitfall 5)."""
    adata = _pca(structured_adata)

    result1, _ = cluster.cluster(adata, resolution=1.0, n_neighbors=15, random_state=0)
    result2, _ = cluster.cluster(adata, resolution=1.0, n_neighbors=15, random_state=0)

    assert list(result1.obs["leiden"]) == list(result2.obs["leiden"])


def test_cluster_small_input_size_guard(synthetic_adata):
    """cluster() on a small PCA'd fixture (50 cells) with default-sized
    n_neighbors=15 does not raise -- internal clamping
    (min(n_neighbors, n_obs - 1)) keeps the neighbor search within
    bounds."""
    adata = _pca(synthetic_adata, n_comps=10)

    result, summary = cluster.cluster(adata, n_neighbors=15, random_state=0)

    assert "leiden" in result.obs
    assert isinstance(summary, ClusterSummary)


def test_cluster_returns_bounded_summary(structured_adata):
    """cluster() returns (adata, ClusterSummary) with fields matching the
    actual Leiden output and post-clamping config values (ANLYS-04)."""
    adata = _pca(structured_adata)

    result, summary = cluster.cluster(adata, resolution=1.0, n_neighbors=15, random_state=0)

    assert isinstance(summary, ClusterSummary)
    assert summary.n_clusters == result.obs["leiden"].nunique()

    expected_sizes = {
        str(k): int(v) for k, v in result.obs["leiden"].value_counts().items()
    }
    assert summary.cluster_sizes == expected_sizes

    assert summary.resolution == 1.0
    assert summary.umap_computed is True
    assert summary.dataset_id is None

    assert summary.config["resolution"] == 1.0
    assert summary.config["n_neighbors"] == 15
    assert summary.config["random_state"] == 0


def test_cluster_summary_is_bounded(structured_adata):
    """dataclasses.asdict(summary) contains no field of length O(n_cells)
    -- cluster_sizes is O(n_clusters), never a per-cell array."""
    adata = _pca(structured_adata)

    _, summary = cluster.cluster(adata, resolution=1.0, n_neighbors=15, random_state=0)

    data = asdict(summary)
    assert len(data["cluster_sizes"]) == summary.n_clusters
    for key, value in data.items():
        if isinstance(value, (list, dict)):
            assert len(value) < adata.n_obs, f"field {key} scales with n_cells"
