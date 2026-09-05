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

UNVERIFIED against the real scgpt API: this script is written against
04-RESEARCH.md Pattern 1's documented (LOW-MEDIUM confidence) sketch of
`scgpt.tasks.embed_data(...)`. The plan's intended verification step --
`python -c "import scgpt as scg; help(scg.tasks)"` -- could not be completed
because `import scgpt` currently fails in this environment with a
torch/torchtext ABI mismatch unrelated to this script (see README.md).
Plan 04-05 must re-verify this script's embedding calls against the actual
installed API once that import is repaired, before trusting its output.
"""

import argparse
import json
import sys

import numpy as np


def _load_adata(path):
    import anndata

    return anndata.read_h5ad(path)


def _embed(adata, model_dir, gene_col="feature_name"):
    """Embed cells via scGPT, using raw counts (not log-normalized .X).

    ingest/loaders.py sets an immutable adata.layers["counts"] (raw counts)
    separate from .X (log-normalized by analysis/preprocess.py). scGPT's
    own binning expects raw/count-like input, so a copy with .X swapped to
    the counts layer is passed to the embedding call, not adata.X directly.
    """
    import scgpt as scg

    prepped = adata.copy()
    prepped.X = prepped.layers["counts"]
    prepped.var["feature_name"] = prepped.var_names

    return scg.tasks.embed_data(prepped, model_dir=model_dir, gene_col=gene_col)


def _cosine_similarity_matrix(a, b):
    a_norm = a / np.linalg.norm(a, axis=1, keepdims=True)
    b_norm = b / np.linalg.norm(b, axis=1, keepdims=True)
    return a_norm @ b_norm.T


def _match_and_aggregate(query, query_embed, reference, reference_embed, reference_dataset):
    """Top-1 cosine match per query cell, aggregated to one call per leiden group."""
    sims = _cosine_similarity_matrix(query_embed, reference_embed)
    best_idx = sims.argmax(axis=1)
    best_sim = sims[np.arange(sims.shape[0]), best_idx]

    ref_cell_type = reference.obs["cell_type"].to_numpy()
    ref_ontology_id = reference.obs["cell_type_ontology_term_id"].to_numpy()

    matched_labels = ref_cell_type[best_idx]
    matched_ontology_ids = ref_ontology_id[best_idx]

    calls = []
    for cluster in sorted(query.obs["leiden"].unique(), key=str):
        mask = (query.obs["leiden"] == cluster).to_numpy()
        if not mask.any():
            continue

        group_labels = matched_labels[mask]
        group_ontology_ids = matched_ontology_ids[mask]
        group_sims = best_sim[mask]

        values, counts = np.unique(group_labels, return_counts=True)
        majority_label = values[counts.argmax()]
        majority_mask = group_labels == majority_label
        confidence = float(group_sims[majority_mask].mean())
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
        reference_embed = _embed(reference, args.model_dir)

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
