"""Format-detecting 10x Genomics loader (INGEST-01).

Turns a 10x MEX-format directory (`matrix.mtx.gz` + `barcodes.tsv.gz` +
`features.tsv.gz`) or a Cell Ranger `.h5` feature-barcode matrix file into a
valid, var_names-deduplicated AnnData.

Per 01-RESEARCH.md Pitfall 5: `sc.read_10x_mtx`'s `make_unique=True` default
already dedupes var_names, but `sc.read_10x_h5` does NOT -- this module calls
`adata.var_names_make_unique()` explicitly on that path so both entry points
behave identically.

Per 01-RESEARCH.md Pitfall 4: `gex_only=True` (the default, kept here to
match this project's scRNA-seq-only v1 scope) silently drops any
non-Gene-Expression features (e.g. Antibody Capture / CRISPR Guide Capture).
This module logs which feature types were present in the source data and how
many non-Gene-Expression features were dropped, so that's visible rather than
silent.
"""

from __future__ import annotations

import logging
from collections import Counter
from pathlib import Path

import scanpy as sc
from anndata import AnnData

logger = logging.getLogger(__name__)

_GEX_FEATURE_TYPE = "Gene Expression"


def _log_feature_type_drop(feature_types) -> None:
    """Logs which feature types were present in the source data and how many
    non-Gene-Expression features were dropped by gex_only=True.
    """
    counts = Counter(feature_types)
    n_dropped = sum(n for ft, n in counts.items() if ft != _GEX_FEATURE_TYPE)
    logger.info(
        "10x source feature types: %s; %d non-Gene-Expression feature(s) dropped "
        "by gex_only=True",
        dict(counts),
        n_dropped,
    )


def load(path: str | Path) -> AnnData:
    """Format-detects a directory (MEX/.mtx), a .h5 file, or a .h5ad file.

    Directories are read via `sc.read_10x_mtx` (var_names deduplicated via
    `make_unique=True`); `.h5` files are read via `sc.read_10x_h5` followed by
    an explicit `var_names_make_unique()` call, since `read_10x_h5` does not
    dedupe automatically; `.h5ad` files are read via `sc.read_h5ad` directly
    (no var_names_make_unique() call -- a well-formed .h5ad is assumed to
    already have valid var_names, per 05-RESEARCH.md Pattern 2, VCC-01).

    Raises `ValueError` on any other input (nonexistent path, or a file that
    isn't a `.h5` or `.h5ad`).
    """
    p = Path(path)

    if p.is_dir():
        adata = sc.read_10x_mtx(
            p, var_names="gene_symbols", make_unique=True, gex_only=True, cache=False
        )
        feature_types = adata.var.get("feature_types")
        if feature_types is None:
            # gex_only=True already filtered to Gene Expression only; read the
            # raw features file to report what was present/dropped.
            feature_types = _read_feature_types_from_mtx_dir(p)
        _log_feature_type_drop(feature_types)
        return adata

    if p.suffix == ".h5":
        if not p.exists():
            raise ValueError(f"Unrecognized 10x input: {path} (file does not exist)")
        adata = sc.read_10x_h5(p)
        feature_types = adata.var.get("feature_types")
        if feature_types is not None:
            _log_feature_type_drop(feature_types)
        adata.var_names_make_unique()  # read_10x_h5 does NOT auto-dedupe (Pitfall 5)
        return adata

    if p.suffix == ".h5ad":
        # VCC-01: AnnData's own serialization format (used by the VCC public dataset).
        # No var_names_make_unique() needed -- a well-formed .h5ad already has valid
        # var_names, unlike the raw 10x .h5/.mtx formats above.
        return sc.read_h5ad(p)

    raise ValueError(
        f"Unrecognized 10x input: {path} (expected a .mtx directory, .h5, or .h5ad file)"
    )


def _read_feature_types_from_mtx_dir(mtx_dir: Path) -> list[str]:
    """Reads the raw feature_types column directly from features.tsv.gz,
    since gex_only=True strips non-Gene-Expression rows (and the
    feature_types column itself) before we ever see the loaded AnnData.
    """
    import gzip

    features_path = mtx_dir / "features.tsv.gz"
    if not features_path.exists():
        return [_GEX_FEATURE_TYPE]

    feature_types = []
    with gzip.open(features_path, "rt") as fh:
        for line in fh:
            fields = line.rstrip("\n").split("\t")
            if len(fields) >= 3:
                feature_types.append(fields[2])
            else:
                feature_types.append(_GEX_FEATURE_TYPE)
    return feature_types
