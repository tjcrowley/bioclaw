"""Ensembl-ID presence validator -- required guard before any Geneformer call.

Per 13-RESEARCH.md Pitfall 2, Geneformer's tokenizer vocabulary is keyed by
unversioned Ensembl gene IDs. If `adata.var` lacks a usable Ensembl-ID-shaped
column, the tokenizer does NOT raise -- genes simply fail to tokenize
silently, producing degenerate-but-exception-free results. This module is the
loud, fail-fast guard the roadmap's "validated... before inference runs"
wording requires.

Per Don't Hand-Roll (13-RESEARCH.md): for MTX/.h5-sourced datasets,
ingest/loaders.py's sc.read_10x_mtx(var_names="gene_symbols")/sc.read_10x_h5()
already populate adata.var["gene_ids"] with Ensembl IDs from the 10x
features.tsv.gz -- no external mapping service needed for that path. This
does NOT hold for arbitrary .h5ad uploads or census-fetched data --
validate_ensembl_ids() checks and fails loudly rather than assuming.

IMPORTANT -- this is a presence/shape check only. It does NOT compute a real
vocabulary match rate against Geneformer's token dictionary (that requires
the `geneformer` package, only importable inside the isolated
geneformer_worker/.venv, which this main-venv module cannot import). The real
match rate is computed by geneformer_worker/run_geneformer_perturb.py
(Plan 13-03) and reported back as GeneformerPerturbationCall.match_rate.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from anndata import AnnData

# Matches unversioned or versioned Ensembl gene IDs, e.g. "ENSG00000141510"
# or "ENSG00000141510.21" (species-prefix letters after "ENS" are optional,
# covering non-human Ensembl IDs like "ENSMUSG...").
_ENSEMBL_ID_RE = re.compile(r"^ENS[A-Z]*G\d+")

# Strips a trailing ".N" version suffix, e.g. "ENSG00000141510.21" ->
# "ENSG00000141510".
_VERSION_SUFFIX_RE = re.compile(r"\.\d+$")


def _strip_version_suffix(value: str) -> str:
    return _VERSION_SUFFIX_RE.sub("", str(value))


def validate_ensembl_ids(adata: "AnnData") -> None:
    """Validate and alias Ensembl gene IDs into adata.var["ensembl_id"] in place.

    Presence/shape check only -- does not validate against Geneformer's real
    token vocabulary (see module docstring).

    Resolution order:
      1. adata.var["gene_ids"] (10x MTX/.h5 ingest path -- see Don't Hand-Roll
         above): alias adata.var["ensembl_id"] = adata.var["gene_ids"].
      2. adata.var["feature_id"] (plausible census/.h5ad-upload column name):
         alias from that.
      3. adata.var_names themselves match the Ensembl ID shape (regex on a
         majority of entries): alias adata.var["ensembl_id"] = adata.var_names.
      4. None of the above: raise ValueError.

    In all three success paths, strips any ".N" version suffix (e.g.
    "ENSG00000141510.21" -> "ENSG00000141510") from every value in the new
    "ensembl_id" column, per Pitfall 2's version-suffix mismatch warning.

    Args:
        adata: AnnData whose `.var` is mutated in place, adding an
            "ensembl_id" column.

    Raises:
        ValueError: if no Ensembl-ID-shaped column or index is found.
    """
    if "gene_ids" in adata.var.columns:
        source = adata.var["gene_ids"]
    elif "feature_id" in adata.var.columns:
        source = adata.var["feature_id"]
    else:
        var_names = list(adata.var_names)
        matches = sum(1 for name in var_names if _ENSEMBL_ID_RE.match(str(name)))
        if var_names and matches > len(var_names) / 2:
            source = adata.var_names.to_series()
        else:
            raise ValueError(
                "No Ensembl-ID-shaped gene identifier column found in "
                "adata.var (checked 'gene_ids', 'feature_id', and "
                "adata.var_names). Geneformer requires Ensembl IDs -- gene "
                "symbols alone are insufficient (13-RESEARCH.md Pitfall 2). "
                "Populate adata.var['gene_ids'] or adata.var['feature_id'] "
                "with Ensembl gene IDs before calling Geneformer inference."
            )

    adata.var["ensembl_id"] = [_strip_version_suffix(v) for v in source]
