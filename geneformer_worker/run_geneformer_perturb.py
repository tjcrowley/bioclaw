"""CLI script run inside the isolated geneformer_worker/.venv (FM-02).

Invoked as:
    geneformer_worker/.venv/bin/python geneformer_worker/run_geneformer_perturb.py \
        --query <path.h5ad> --target-gene <symbol> --target-ensembl-id <id> \
        --model-dir <checkpoint dir> [--work-dir <dir>]

Runs Geneformer's real four-step in-silico-perturbation pipeline (per
13-RESEARCH.md Pattern 3):
    1. TranscriptomeTokenizer.tokenize_data()  -- h5ad -> tokenized .dataset
    2. EmbExtractor.extract_embs()             -- baseline cell embeddings
    3. InSilicoPerturber.perturb_data()        -- delete target gene, re-embed
    4. InSilicoPerturberStats.get_stats()      -- aggregate cosine shifts per
       affected gene, comparing perturbed vs. original embeddings

and prints a single JSON object (not an array -- one target gene per call)
to stdout on success, matching perturbation/summary.py's
`GeneformerPerturbationCall` field names exactly:
    {"target_gene": ..., "target_ensembl_id": ..., "match_rate": ...,
     "ranked_genes": [{"gene": ..., "ensembl_id": ..., "cosine_shift": ...}]}

`perturbation/geneformer_client.py` (in the main venv) shells out to this
script and parses its stdout -- it never imports this module or
`geneformer` directly, mirroring `bio_fm_worker/run_scgpt_embed.py`'s
established subprocess-worker shape for scGPT.

Verified (2026-09-17) against the real installed `geneformer` package via
`inspect.signature`/`inspect.getsource` on all four pipeline classes, per
this plan's task instructions. Two real drifts from 13-RESEARCH.md
Pattern 3's documented shapes were found and are called out inline below:

1. `model_input_size`/`special_token` are NOT free parameters when
   `model_version="V1"` is passed to `TranscriptomeTokenizer` --
   `TranscriptomeTokenizer.__init__` unconditionally overrides
   `self.model_input_size = 2048` and `self.special_token = False` in that
   branch (V1 models have no <cls>/<eos> tokens, unlike V2's 4096/True).
   Pattern 3's snippet showed `model_input_size=4096` which is the V2
   default -- passing it explicitly is harmless (it gets overridden) but
   this script passes the correct V1 value (2048) for clarity. Likewise
   `EmbExtractor`, `InSilicoPerturber`, and `InSilicoPerturberStats` all
   auto-swap their `token_dictionary_file`/`gene_median_file`/
   `gene_mapping_file`/`gene_name_id_dictionary_file` defaults to the
   `_30M` (V1) pickle variants purely from `model_version="V1"` -- this
   script never needs to pass those paths explicitly.

2. `InSilicoPerturberStats.get_stats(mode="aggregate_gene_shifts")`'s
   returned DataFrame columns are NOT `Gene, Gene_name, Ensembl_ID,
   N_Detections, Cosine_sim_mean, Cosine_sim_stdev` as Pattern 3's comment
   suggested. Read via `inspect.getsource` on
   `geneformer.in_silico_perturber_stats.isp_aggregate_gene_shifts`: the
   real columns are `Perturbed, Gene_name, Ensembl_ID` (all three describing
   the *perturbed* gene -- constant across every row, since this script only
   ever perturbs one gene) plus `Affected, Affected_gene_name,
   Affected_Ensembl_ID, Cosine_sim_mean, Cosine_sim_stdev, N_Detections`
   describing each *affected* gene's (or "cell_emb"'s) response. The ranked
   gene list this script reports must read `Affected_gene_name`/
   `Affected_Ensembl_ID`, not `Gene_name`/`Ensembl_ID` -- using the latter
   would report the same (perturbed) gene name for every ranked row. Rows
   where `Affected == "cell_emb"` (the whole-cell embedding shift, not a
   specific gene) are excluded from `ranked_genes` per this script's
   documented "ranked gene list" contract.
"""

import argparse
import json
import pickle
import sys
import tempfile
from pathlib import Path


def _load_adata(path):
    import scanpy as sc

    return sc.read_h5ad(path)


def _resolve_v1_token_dictionary_file():
    """Path to Geneformer's V1 (30M-cell) token dictionary pickle.

    Same file all four pipeline classes auto-select internally when given
    `model_version="V1"` (see module docstring drift note 1) -- resolved
    here independently so this script can compute the real vocabulary
    match_rate before committing to the (expensive) tokenize/embed/perturb
    steps.
    """
    from geneformer import TOKEN_DICTIONARY_FILE_30M

    return TOKEN_DICTIONARY_FILE_30M


def _compute_match_rate(adata, token_dictionary_file):
    with open(token_dictionary_file, "rb") as fh:
        token_dict = pickle.load(fh)

    ensembl_ids = list(adata.var["ensembl_id"])
    if not ensembl_ids:
        return 0.0
    n_matched = sum(1 for gene_id in ensembl_ids if gene_id in token_dict)
    return n_matched / len(ensembl_ids)


def _run_pipeline(query_path, target_gene, target_ensembl_id, model_dir, work_dir):
    from geneformer import (
        EmbExtractor,
        InSilicoPerturber,
        InSilicoPerturberStats,
        TranscriptomeTokenizer,
    )

    # tokenize_data() scans a *directory* for *.h5ad files (per
    # TranscriptomeTokenizer.tokenize_files -- confirmed via inspect.getsource),
    # not a single file path -- symlink the query h5ad into its own dedicated
    # directory so no unrelated .h5ad files in the same parent get picked up.
    data_dir = work_dir / "data_input"
    data_dir.mkdir(parents=True, exist_ok=True)
    query_link = data_dir / "query.h5ad"
    query_link.symlink_to(Path(query_path).resolve())

    tokenized_dir = work_dir / "tokenized"
    tokenized_dir.mkdir(parents=True, exist_ok=True)
    tokenizer = TranscriptomeTokenizer(model_input_size=2048, model_version="V1")
    tokenizer.tokenize_data(
        data_directory=data_dir,
        output_directory=tokenized_dir,
        output_prefix="query",
        file_format="h5ad",
    )
    tokenized_dataset = tokenized_dir / "query.dataset"

    embs_dir = work_dir / "embs"
    embs_dir.mkdir(parents=True, exist_ok=True)
    extractor = EmbExtractor(model_type="Pretrained", emb_mode="cls", model_version="V1")
    extractor.extract_embs(
        model_directory=str(model_dir),
        input_data_file=str(tokenized_dataset),
        output_directory=str(embs_dir),
        output_prefix="query_emb",
    )

    perturb_out_dir = work_dir / "perturb_out"
    perturb_out_dir.mkdir(parents=True, exist_ok=True)
    isp = InSilicoPerturber(
        perturb_type="delete",
        genes_to_perturb=[target_ensembl_id],
        emb_mode="cell_and_gene",
        model_type="Pretrained",
        model_version="V1",
        forward_batch_size=100,
    )
    isp.perturb_data(
        model_directory=str(model_dir),
        input_data_file=str(tokenized_dataset),
        output_directory=str(perturb_out_dir),
        output_prefix="query_perturb",
    )

    stats_out_dir = work_dir / "stats_out"
    stats_out_dir.mkdir(parents=True, exist_ok=True)
    stats = InSilicoPerturberStats(
        mode="aggregate_gene_shifts",
        genes_perturbed=[target_ensembl_id],
        model_version="V1",
    )
    result_df = stats.get_stats(
        input_data_directory=str(perturb_out_dir),
        null_dist_data_directory=None,
        output_directory=str(stats_out_dir),
        output_prefix="query_stats",
    )
    return result_df


def _build_ranked_genes(result_df):
    # Exclude the whole-cell-embedding shift row -- this script reports a
    # ranked *gene* list (see module docstring drift note 2).
    gene_rows = result_df[result_df["Affected"] != "cell_emb"].copy()
    gene_rows["_abs_shift"] = gene_rows["Cosine_sim_mean"].abs()
    gene_rows = gene_rows.sort_values("_abs_shift", ascending=False)
    return [
        {
            "gene": row.Affected_gene_name,
            "ensembl_id": row.Affected_Ensembl_ID,
            "cosine_shift": float(row.Cosine_sim_mean),
        }
        for row in gene_rows.itertuples()
    ]


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--query", required=True)
    parser.add_argument("--target-gene", required=True)
    parser.add_argument("--target-ensembl-id", required=True)
    parser.add_argument(
        "--model-dir",
        default="geneformer_worker/src/Geneformer-V1-10M",
    )
    parser.add_argument("--work-dir", default=None)
    args = parser.parse_args(argv)

    work_dir = Path(args.work_dir) if args.work_dir else Path(tempfile.mkdtemp())
    work_dir.mkdir(parents=True, exist_ok=True)

    try:
        adata = _load_adata(args.query)

        # Defensive re-check -- perturbation/ensembl.py::validate_ensembl_ids()
        # should already have run in the main venv before this h5ad was
        # written, but this worker is the last chance to catch it before
        # tokenize_data()'s silent zero-length-token failure mode
        # (13-RESEARCH.md Pitfall 2).
        if "ensembl_id" not in adata.var.columns:
            print(
                "run_geneformer_perturb.py failed: query h5ad missing "
                "adata.var['ensembl_id'] -- run "
                "perturbation.ensembl.validate_ensembl_ids() before calling "
                "this worker.",
                file=sys.stderr,
            )
            return 1
        if "n_counts" not in adata.obs.columns:
            print(
                "run_geneformer_perturb.py failed: query h5ad missing "
                "adata.obs['n_counts'], required by Geneformer's tokenizer.",
                file=sys.stderr,
            )
            return 1

        token_dictionary_file = _resolve_v1_token_dictionary_file()
        match_rate = _compute_match_rate(adata, token_dictionary_file)
        if match_rate < 0.5:
            print(
                f"run_geneformer_perturb.py failed: vocabulary match_rate "
                f"{match_rate:.3f} is below the 0.5 threshold -- refusing to "
                f"tokenize (13-RESEARCH.md Pitfall 2: low match rate silently "
                f"produces degenerate zero/near-zero-length tokenized "
                f"sequences rather than raising).",
                file=sys.stderr,
            )
            return 1

        try:
            result_df = _run_pipeline(
                args.query,
                args.target_gene,
                args.target_ensembl_id,
                args.model_dir,
                work_dir,
            )
        except Exception as exc:  # noqa: BLE001 - pipeline boundary: report, don't crash bare
            print(
                f"run_geneformer_perturb.py failed during pipeline execution "
                f"(intermediate files left in {work_dir} for debugging): {exc}",
                file=sys.stderr,
            )
            return 1

        ranked_genes = _build_ranked_genes(result_df)
    except Exception as exc:  # noqa: BLE001 - CLI boundary: report, never partial stdout
        print(f"run_geneformer_perturb.py failed: {exc}", file=sys.stderr)
        return 1

    print(
        json.dumps(
            {
                "target_gene": args.target_gene,
                "target_ensembl_id": args.target_ensembl_id,
                "match_rate": match_rate,
                "ranked_genes": ranked_genes,
            }
        )
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
