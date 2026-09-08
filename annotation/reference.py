"""cellxgene-census-sourced reference embedding index for FM-side annotation.

`build_reference_index()` is a one-time (or occasionally re-run manually)
build step -- it is NOT queried live on every `annotate_cell_type` call. Per
04-RESEARCH.md Open Question 4, the reference is deliberately small and
single-tissue: a static `.h5ad` file that `bio_fm_worker/run_scgpt_embed.py`
embeds once and reuses for zero-shot nearest-reference-cell-type mapping.

`cell_type` and `cell_type_ontology_term_id` are CELLxGENE-schema-enforced
fields on every census cell (see 04-RESEARCH.md's Don't Hand-Roll section) --
this is what makes census a reference source instead of hand-rolling an
ontology mapping. A cell missing either field would indicate a query mistake
(e.g. querying a non-census-data modality), not an expected data gap, so
`build_reference_index()` asserts rather than silently drops.

To rebuild the reference file (e.g. a different tissue or larger sample):
`uv run python -c "from annotation.reference import build_reference_index; print(build_reference_index())"`
"""

from __future__ import annotations

import time
from pathlib import Path

import cellxgene_census
import numpy as np
import tiledbsoma

from annotation.fm_client import ensure_worker_compatible_h5ad

ORGANISM = "Homo sapiens"
CENSUS_VERSION = "2025-11-08"  # pinned for reproducibility; see release.json

# Two live attempts (2026-09-07) against the default config both died on the
# same giant X/raw fragment file with a curl "operation too slow" timeout --
# not random flakiness, but this connection choking on tiledbsoma's default
# high fan-out of parallel scattered byte-range S3 reads. Throttling
# concurrency and lengthening timeouts trades peak throughput for actually
# completing over a slow/unstable link.
S3_TILEDB_CONFIG = {
    "vfs.s3.max_parallel_ops": "4",
    "vfs.s3.connect_timeout_ms": "30000",
    "vfs.s3.request_timeout_ms": "120000",
    "sm.io_concurrency_level": "4",
}


def build_reference_index(
    tissue: str = "blood",
    n_cells: int = 3000,
    out_path: str | Path = "bio_fm_worker/reference/reference.h5ad",
    seed: int = 0,
    max_retries: int = 3,
):
    """Query the public `cellxgene-census` API (no authentication required)
    for `n_cells` cells from `tissue`, write the result to `out_path` as an
    `.h5ad`, and return the `Path` written.

    Cells are taken as a contiguous (not scattered-random) slice of
    soma_joinids within the filtered/labeled population, since a fully
    random scatter forces the underlying TileDB fragment reads into many
    more, smaller, independent S3 byte-range requests -- the direct cause of
    the timeouts observed on 2026-09-07 (see S3_TILEDB_CONFIG comment). This
    is still a randomly *positioned* window (seeded), just not a scattered
    sample -- fine for a reference set, where cell-type diversity within the
    window matters more than global uniform sampling.

    Every returned cell is guaranteed to have non-null `cell_type` and
    `cell_type_ontology_term_id` in `.obs` -- if that guarantee doesn't hold,
    it means the query itself is wrong, so this raises `AssertionError`
    rather than dropping/re-sampling cells to mask the mistake.
    """
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    last_exc: Exception | None = None
    for attempt in range(1, max_retries + 1):
        try:
            adata = _fetch(tissue, n_cells, seed)
            last_exc = None
            break
        except tiledbsoma.SOMAError as exc:
            last_exc = exc
            if attempt < max_retries:
                wait_s = 10 * attempt
                print(
                    f"build_reference_index: attempt {attempt}/{max_retries} "
                    f"failed ({exc}); retrying in {wait_s}s"
                )
                time.sleep(wait_s)
    if last_exc is not None:
        raise last_exc

    assert adata.n_obs == n_cells, f"expected {n_cells} cells, got {adata.n_obs}"
    assert adata.obs["cell_type"].notna().all(), "every cell must have cell_type"
    assert (
        adata.obs["cell_type_ontology_term_id"].notna().all()
    ), "every cell must have cell_type_ontology_term_id"

    ensure_worker_compatible_h5ad(adata)
    adata.write_h5ad(out_path)
    return out_path


def _fetch(tissue: str, n_cells: int, seed: int):
    census = cellxgene_census.open_soma(
        census_version=CENSUS_VERSION, tiledb_config=S3_TILEDB_CONFIG
    )
    try:
        obs = cellxgene_census.get_obs(
            census,
            ORGANISM,
            value_filter=(
                f"tissue_general == '{tissue}' and is_primary_data == True"
            ),
            column_names=["soma_joinid", "cell_type", "cell_type_ontology_term_id"],
        )
        obs = obs.dropna(subset=["cell_type", "cell_type_ontology_term_id"])
        if len(obs) < n_cells:
            raise ValueError(
                f"tissue={tissue!r} only has {len(obs)} labeled cells in "
                f"census {CENSUS_VERSION}, need n_cells={n_cells}"
            )

        obs = obs.sort_values("soma_joinid").reset_index(drop=True)
        rng = np.random.default_rng(seed)
        start = int(rng.integers(0, len(obs) - n_cells + 1))
        sampled_joinids = obs["soma_joinid"].to_numpy()[start : start + n_cells].tolist()

        return cellxgene_census.get_anndata(
            census,
            ORGANISM,
            obs_coords=sampled_joinids,
            obs_column_names=["cell_type", "cell_type_ontology_term_id"],
        )
    finally:
        census.close()
