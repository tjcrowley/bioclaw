"""Raw-counts immutability contract (INGEST-02).

Per 01-RESEARCH.md Pitfall 1/2: `adata.raw = adata` is a reference, not a
copy, and neither AnnData nor scipy.sparse matrices are immutable by
default. This module actively enforces the "raw counts never change after
load" guarantee with two complementary techniques:

1. Write-protect the underlying buffer (`.data.flags.writeable = False` for
   sparse matrices, `.flags.writeable = False` for dense arrays) so any
   later in-place write attempt raises `ValueError`.
2. Store a sha256 checksum of the raw bytes in `adata.uns['counts_checksum']`
   at load time, and expose `verify_counts_integrity()` so callers (tests,
   tool boundaries, other phases) can detect a full-array reassignment that
   bypasses the write-lock entirely -- the writeable flag alone won't catch
   that.

Must be called immediately after `loaders.load()`, before anything else
touches `.X`.
"""

from __future__ import annotations

import hashlib

from anndata import AnnData


def _raw_bytes(counts) -> bytes:
    """Returns the raw underlying bytes for either a sparse matrix (via its
    `.data` array) or a dense ndarray.
    """
    return counts.data.tobytes() if hasattr(counts, "data") else counts.tobytes()


def set_counts_layer(adata: AnnData) -> None:
    """In-place. Copies `adata.X` into `adata.layers['counts']`, freezes the
    underlying buffer (writeable=False), and stores a sha256 checksum of the
    frozen bytes in `adata.uns['counts_checksum']`.
    """
    adata.layers["counts"] = adata.X.copy()
    counts = adata.layers["counts"]

    if hasattr(counts, "data"):  # sparse (csr/csc)
        counts.data.flags.writeable = False
    else:  # dense ndarray
        counts.flags.writeable = False

    adata.uns["counts_checksum"] = hashlib.sha256(_raw_bytes(counts)).hexdigest()


def verify_counts_integrity(adata: AnnData) -> bool:
    """Recomputes the checksum of `adata.layers['counts']` and compares it to
    the checksum stored at load time. Returns False if they diverge --
    catches corruption the write-lock alone wouldn't (e.g. a full-array
    reassignment of `adata.layers['counts']`).
    """
    counts = adata.layers["counts"]
    current = hashlib.sha256(_raw_bytes(counts)).hexdigest()
    return current == adata.uns.get("counts_checksum")
