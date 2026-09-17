"""CLI script run inside the isolated bio_fm_worker/.venv (ANNOT-01).

Invoked as:
    bio_fm_worker/.venv/bin/python bio_fm_worker/run_scgpt_embed.py \
        --query <path.h5ad> --reference <path.h5ad> --model-dir <checkpoint dir>

Embeds `query` and `reference` cells via scGPT's zero-shot embedding, then
reference-maps each query cell to its nearest reference cell by cosine
similarity, aggregates to one call per `query.obs["leiden"]` group, and
prints a JSON array of per-cluster calls to stdout. `annotation/fm_client.py`
(in the main venv) shells out to this script and parses its stdout -- it
never imports this module or `scgpt` directly.

Verified (2026-09-07) against the real installed `scgpt` API via
`inspect.signature`/`inspect.getsource` on `scgpt.tasks.embed_data`, once
the torch/torchtext ABI mismatch blocking `import scgpt` was fixed (see
README.md). One real bug found and fixed by that verification:
`embed_data(..., return_new_adata=False)` (the default) returns the input
`AnnData` with embeddings written to `.obsm["X_scGPT"]`, NOT a bare
embedding matrix -- `_embed()` below extracts that key explicitly.
`device` defaults to `"cuda"` but auto-falls-back to CPU when unavailable,
and `use_fast_transformer=True` similarly auto-falls-back to the plain
PyTorch attention path when `flash_attn` isn't installed (both confirmed
via source read, not just docs) -- neither needs an explicit override on
this CPU-only worker.
"""

import argparse
import hashlib
import json
import os
import sys
from pathlib import Path

import numpy as np

# `os.sched_getaffinity` is Linux-only; scgpt/tasks/cell_emb.py calls it
# unconditionally (no `hasattr` guard) to determine DataLoader num_workers via
# `min(len(os.sched_getaffinity(0)), batch_size)`. Returning an empty set
# makes that expression evaluate to 0, keeping the DataLoader in-process
# (num_workers=0). That's required on macOS anyway -- scgpt's DataLoader uses
# a local `Dataset` class that Python's pickle can't serialize for subprocess
# workers, so num_workers > 0 raises "Can't pickle local object" on macOS.
if not hasattr(os, "sched_getaffinity"):
    os.sched_getaffinity = lambda pid: set()


def _load_adata(path):
    import anndata

    return anndata.read_h5ad(path)


def _embed(adata, model_dir, gene_col="feature_name"):
    """Embed cells via scGPT, using raw counts (not log-normalized .X).

    Query AnnData (from ingest/loaders.py) has raw counts in layers["counts"]
    and log-normalized data in .X -- scGPT's binning expects raw counts, so we
    swap .X to the counts layer. Reference AnnData (from cellxgene-census via
    annotation/reference.py) stores raw counts directly in .X with no layers
    key, so the swap is skipped for it -- `layers.get` returns None, and we
    leave .X as-is.
    """
    import scgpt as scg

    prepped = adata.copy()
    raw = prepped.layers.get("counts")
    if raw is not None:
        prepped.X = raw
    # Use existing feature_name column (reference: census var has gene-symbol
    # feature_name; var_names are integer soma joinids). For query AnnData,
    # feature_name is absent and var_names are already gene symbols.
    if "feature_name" not in prepped.var.columns:
        prepped.var["feature_name"] = prepped.var_names

    embedded = scg.tasks.embed_data(prepped, model_dir=model_dir, gene_col=gene_col)
    return embedded.obsm["X_scGPT"]


def _reference_embed_cache_path(reference_path, model_dir):
    """Cache path for a reference's embedding, keyed on both the reference
    file and the model checkpoint dir (a different checkpoint invalidates a
    prior embedding, since the embedding space itself changes).
    """
    key = f"{Path(reference_path).resolve()}::{Path(model_dir).resolve()}"
    digest = hashlib.sha256(key.encode()).hexdigest()[:16]
    return Path(reference_path).with_suffix(f".{digest}.scgpt_emb.npy")


def _embed_reference_cached(reference, reference_path, model_dir):
    """As `_embed()`, but memoized to disk next to `reference_path`.

    Real reference embedding (3000 cells, CPU) took ~38 minutes in
    verification (2026-09-07) -- reference.py's own docstring says the
    reference is meant to be "embedded once and reused", but nothing
    previously implemented that reuse, so every `annotate_cell_type` call
    silently re-paid the full 38 minutes. This cache is what makes that
    "once" claim true. Invalidated by reference-file mtime, so rebuilding
    the reference (see reference.py's module docstring) transparently
    recomputes the embedding on the next call.
    """
    cache_path = _reference_embed_cache_path(reference_path, model_dir)
    if (
        cache_path.exists()
        and cache_path.stat().st_mtime >= Path(reference_path).stat().st_mtime
    ):
        return np.load(cache_path)

    embed = _embed(reference, model_dir)
    np.save(cache_path, embed)
    return embed


def _cosine_similarity_matrix(a, b):
    a_norm = a / np.linalg.norm(a, axis=1, keepdims=True)
    b_norm = b / np.linalg.norm(b, axis=1, keepdims=True)
    return a_norm @ b_norm.T


def _match_and_aggregate(
    query, query_embed, reference, reference_embed, reference_dataset, k: int = 15
):
    """k-NN vote-fraction match per query cell, aggregated to one call per leiden group.

    For each query cell, finds its `k` nearest reference neighbors by cosine
    similarity, takes the majority label among those `k` neighbors, and sets
    that cell's confidence to the vote fraction (count of majority-label
    neighbors / k) -- the same technique scArches' WKNN label-transfer
    classifier and popV's consensus voting use. This replaces a prior top-1
    cosine-similarity confidence, which gave no sense of neighborhood
    consistency (a single, possibly noisy, nearest neighbor could disagree
    with the broader local consensus). Per-cluster aggregation (majority
    label across the group's cells, mean confidence among cells agreeing
    with the group majority, majority label's ontology id) is unchanged.
    """
    sims = _cosine_similarity_matrix(query_embed, reference_embed)
    k = min(k, sims.shape[1])

    ref_cell_type = reference.obs["cell_type"].to_numpy()
    ref_ontology_id = reference.obs["cell_type_ontology_term_id"].to_numpy()

    # Per-query-cell k-NN vote fraction: for each row, find the k nearest
    # reference neighbors (argpartition is O(n) vs argsort's O(n log n), and
    # we don't need the within-k order, only membership), then take the
    # majority label among those k neighbors and the fraction of neighbors
    # agreeing with it.
    topk_idx = np.argpartition(-sims, kth=k - 1, axis=1)[:, :k]
    topk_labels = ref_cell_type[topk_idx]

    matched_labels = np.empty(sims.shape[0], dtype=object)
    matched_ontology_ids = np.empty(sims.shape[0], dtype=object)
    cell_confidence = np.empty(sims.shape[0], dtype=float)
    for i in range(sims.shape[0]):
        values, counts = np.unique(topk_labels[i], return_counts=True)
        majority_label = values[counts.argmax()]
        vote_fraction = float(counts.max()) / k
        # ontology id for this cell's vote: first neighbor among its k that
        # carries the majority label.
        neighbor_labels = ref_cell_type[topk_idx[i]]
        neighbor_ontology_ids = ref_ontology_id[topk_idx[i]]
        ontology_term_id = neighbor_ontology_ids[neighbor_labels == majority_label][0]

        matched_labels[i] = majority_label
        matched_ontology_ids[i] = ontology_term_id
        cell_confidence[i] = vote_fraction

    calls = []
    for cluster in sorted(query.obs["leiden"].unique(), key=str):
        mask = (query.obs["leiden"] == cluster).to_numpy()
        if not mask.any():
            continue

        group_labels = matched_labels[mask]
        group_ontology_ids = matched_ontology_ids[mask]
        group_confidence = cell_confidence[mask]

        values, counts = np.unique(group_labels, return_counts=True)
        majority_label = values[counts.argmax()]
        majority_mask = group_labels == majority_label
        confidence = float(group_confidence[majority_mask].mean())
        ontology_term_id = group_ontology_ids[majority_mask][0]

        calls.append(
            {
                "cluster": str(cluster),
                "label": str(majority_label),
                "confidence": confidence,
                "reference_dataset": reference_dataset,
                "ontology_term_id": (
                    None if ontology_term_id is None else str(ontology_term_id)
                ),
            }
        )
    return calls


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--query", required=True)
    parser.add_argument("--reference", required=True)
    parser.add_argument("--model-dir", required=True)
    args = parser.parse_args(argv)

    try:
        query = _load_adata(args.query)
        reference = _load_adata(args.reference)

        if "leiden" not in query.obs.columns:
            raise ValueError("query AnnData missing required obs['leiden'] column")
        for col in ("cell_type", "cell_type_ontology_term_id"):
            if col not in reference.obs.columns:
                raise ValueError(f"reference AnnData missing required obs['{col}'] column")

        query_embed = _embed(query, args.model_dir)
        reference_embed = _embed_reference_cached(
            reference, args.reference, args.model_dir
        )

        reference_dataset = f"cellxgene-census reference index: {args.reference}"
        calls = _match_and_aggregate(
            query, query_embed, reference, reference_embed, reference_dataset
        )
    except Exception as exc:  # noqa: BLE001 - CLI boundary: report, never partial stdout
        print(f"run_scgpt_embed.py failed: {exc}", file=sys.stderr)
        return 1

    print(json.dumps(calls))
    return 0


if __name__ == "__main__":
    sys.exit(main())
