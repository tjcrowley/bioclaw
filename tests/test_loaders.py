"""Tests for ingest/loaders.py -- the format-detecting 10x loader (INGEST-01)."""

import logging

import pytest
from anndata import AnnData

from ingest.loaders import load


def test_load_mtx_dir(tiny_mtx_dir):
    adata = load(tiny_mtx_dir)

    assert isinstance(adata, AnnData)
    assert adata.n_obs == 40
    assert adata.n_vars == 18

    # The duplicated gene symbol (DUPGENE) resolves to two distinct var_names.
    dup_names = [n for n in adata.var_names if n.startswith("DUPGENE")]
    assert len(dup_names) == 2
    assert "DUPGENE" in dup_names
    assert "DUPGENE-1" in dup_names

    # var_names are unique overall.
    assert adata.var_names.is_unique


def test_load_h5(tiny_h5_file):
    adata = load(tiny_h5_file)

    assert isinstance(adata, AnnData)
    assert adata.n_obs > 0
    assert adata.n_vars > 0

    # read_10x_h5 does NOT dedupe automatically -- loaders.py must do it explicitly.
    assert adata.var_names.is_unique


def test_load_nonexistent_path_raises_value_error():
    with pytest.raises(ValueError, match=r"/some/nonexistent/path"):
        load("/some/nonexistent/path")


def test_load_unrecognized_file_raises_value_error(tmp_path):
    bad_file = tmp_path / "file.txt"
    bad_file.write_text("not a 10x file")

    with pytest.raises(ValueError, match=r"file\.txt"):
        load(bad_file)


def test_load_logs_feature_type_drop(tiny_mtx_dir, caplog):
    with caplog.at_level(logging.INFO, logger="ingest.loaders"):
        load(tiny_mtx_dir)

    assert any(
        "Gene Expression" in record.message or "feature type" in record.message.lower()
        for record in caplog.records
    )


def test_load_h5ad(tmp_path, synthetic_adata):
    """load() dispatches .h5ad files to sc.read_h5ad and returns a valid AnnData
    with matching n_obs/n_vars (VCC-01, 05-RESEARCH.md Pattern 2).
    """
    h5ad_path = tmp_path / "test.h5ad"
    synthetic_adata.write_h5ad(h5ad_path)

    result = load(h5ad_path)

    assert isinstance(result, AnnData)
    assert result.n_obs == synthetic_adata.n_obs
    assert result.n_vars == synthetic_adata.n_vars
