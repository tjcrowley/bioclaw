"""Tests for perturbation/ensembl.py -- validate_ensembl_ids().

Covers the four resolution paths (gene_ids, gene_ids-with-version-suffix,
feature_id, var_names-shaped-like-Ensembl-IDs) plus the failure path (no
usable source found -> ValueError mentioning "Ensembl").

Builds tiny AnnData objects directly, no ingest pipeline needed -- this is a
presence/shape check only, not a real vocabulary match rate (that requires
the `geneformer` package, only importable inside the isolated
geneformer_worker/.venv; see perturbation/ensembl.py's docstring).
"""

import anndata as ad
import numpy as np
import pandas as pd
import pytest

from perturbation.ensembl import validate_ensembl_ids


def _make_adata(var: pd.DataFrame, var_names: list[str]) -> ad.AnnData:
    var = var.copy()
    var.index = pd.Index(var_names)
    n_obs = 3
    n_var = len(var_names)
    X = np.zeros((n_obs, n_var), dtype=float)
    return ad.AnnData(X=X, var=var)


def test_gene_ids_present_plain():
    """adata.var["gene_ids"] present with plain IDs -> ensembl_id column created,
    equal to gene_ids."""
    var_names = ["CD3D", "CD3E", "CD8A"]
    gene_ids = ["ENSG00000167286", "ENSG00000198851", "ENSG00000153563"]
    adata = _make_adata(pd.DataFrame({"gene_ids": gene_ids}), var_names)

    validate_ensembl_ids(adata)

    assert "ensembl_id" in adata.var.columns
    assert list(adata.var["ensembl_id"]) == gene_ids


def test_gene_ids_present_with_version_suffix_stripped():
    """adata.var["gene_ids"] present with .N version suffixes -> suffixes stripped."""
    var_names = ["CD3D", "CD3E", "CD8A"]
    gene_ids = [
        "ENSG00000167286.5",
        "ENSG00000198851.12",
        "ENSG00000153563.21",
    ]
    adata = _make_adata(pd.DataFrame({"gene_ids": gene_ids}), var_names)

    validate_ensembl_ids(adata)

    assert list(adata.var["ensembl_id"]) == [
        "ENSG00000167286",
        "ENSG00000198851",
        "ENSG00000153563",
    ]


def test_feature_id_fallback_when_no_gene_ids():
    """No gene_ids, but adata.var["feature_id"] present -> aliased from feature_id."""
    var_names = ["CD3D", "CD3E", "CD8A"]
    feature_ids = ["ENSG00000167286", "ENSG00000198851", "ENSG00000153563"]
    adata = _make_adata(pd.DataFrame({"feature_id": feature_ids}), var_names)

    validate_ensembl_ids(adata)

    assert "ensembl_id" in adata.var.columns
    assert list(adata.var["ensembl_id"]) == feature_ids


def test_var_names_ensembl_shaped_fallback():
    """No gene_ids/feature_id, but adata.var_names look like Ensembl IDs ->
    aliased from var_names."""
    var_names = ["ENSG00000141510", "ENSG00000167286", "ENSG00000198851"]
    adata = _make_adata(pd.DataFrame(index=var_names), var_names)

    validate_ensembl_ids(adata)

    assert "ensembl_id" in adata.var.columns
    assert list(adata.var["ensembl_id"]) == var_names


def test_no_usable_source_raises_value_error_mentioning_ensembl():
    """None of the above (plain gene-symbol var_names, no gene_ids/feature_id
    columns) -> raises ValueError whose message contains "Ensembl"."""
    var_names = ["CD3D", "CD3E", "CD8A"]
    adata = _make_adata(pd.DataFrame(index=var_names), var_names)

    with pytest.raises(ValueError, match="Ensembl"):
        validate_ensembl_ids(adata)
