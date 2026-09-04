"""Tests for ingest/contract.py -- the raw-counts immutability contract
(INGEST-02).
"""

import numpy as np
import pytest
import scanpy as sc

from ingest.contract import set_counts_layer, verify_counts_integrity
from ingest.loaders import load


def test_set_counts_layer_copies_original_x(tiny_mtx_dir):
    adata = load(tiny_mtx_dir)
    original = adata.X.toarray().copy() if hasattr(adata.X, "toarray") else adata.X.copy()

    set_counts_layer(adata)

    assert "counts" in adata.layers
    stored = adata.layers["counts"]
    stored_dense = stored.toarray() if hasattr(stored, "toarray") else stored
    np.testing.assert_array_equal(stored_dense, original)


def test_counts_immutable_after_normalize(tiny_mtx_dir):
    adata = load(tiny_mtx_dir)
    set_counts_layer(adata)

    original_counts = adata.layers["counts"].copy()
    if hasattr(original_counts, "toarray"):
        original_dense = original_counts.toarray()
    else:
        original_dense = original_counts

    # Simulate a later pipeline step mutating .X.
    sc.pp.normalize_total(adata)
    sc.pp.log1p(adata)

    stored = adata.layers["counts"]
    stored_dense = stored.toarray() if hasattr(stored, "toarray") else stored

    np.testing.assert_array_equal(stored_dense, original_dense)
    assert verify_counts_integrity(adata) is True


def test_direct_write_to_frozen_layer_raises(tiny_mtx_dir):
    adata = load(tiny_mtx_dir)
    set_counts_layer(adata)

    counts = adata.layers["counts"]
    with pytest.raises(ValueError):
        if hasattr(counts, "data"):
            counts.data[0] = 999
        else:
            counts[0, 0] = 999


def test_hostile_full_array_reassignment_detected_by_checksum(tiny_mtx_dir):
    adata = load(tiny_mtx_dir)
    set_counts_layer(adata)

    assert verify_counts_integrity(adata) is True

    # Bypass the write-lock entirely via full-array reassignment -- the
    # writeable flag alone does not catch this; the checksum must.
    other = adata.layers["counts"].copy()
    if hasattr(other, "data"):
        other.data.flags.writeable = True
        other.data[0] = 999
    else:
        other.flags.writeable = True
        other[0, 0] = 999
    adata.layers["counts"] = other

    assert verify_counts_integrity(adata) is False
