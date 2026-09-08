# Phase 04-05 Summary: Real scGPT Checkpoint + bio_fm_smoke Gate

**Completed:** 2026-09-08  
**Wall-clock latency (cache-hit run):** 31.2s end-to-end for `annotate_cell_type_tool`

## What Was Done

Phase 4's blocking human-verify checkpoint: demonstrated a real, unmocked end-to-end
`annotate_cell_type` tool call using the scGPT whole-human checkpoint and a
cellxgene-census reference embedding index. Six bugs found and fixed during verification:

### Bugs Fixed

1. **`IOSpec(encoding_type='nullable-string-array')`** — pandas 3.0 serializes string
   columns with `StringDtype`; anndata==0.10.9 (worker) has no reader for it.
   Fix: `ensure_worker_compatible_h5ad()` coerces index, columns, and Categorical
   category dtype to plain `object`.

2. **`IOSpec(encoding_type='null')` from `uns/analysis/...`** — analysis pipeline writes
   DE results into `adata.uns`; NaN-encoded values can't be decoded by anndata==0.10.9.
   Fix: `adata.uns.clear()` in `ensure_worker_compatible_h5ad()` — worker never reads uns.

3. **`module 'os' has no attribute 'sched_getaffinity'`** — scgpt/tasks/cell_emb.py calls
   `os.sched_getaffinity(0)` unconditionally; Linux-only.
   Fix: shim `os.sched_getaffinity = lambda pid: set()` so num_workers evaluates to 0.

4. **`Can't pickle local object 'get_batch_cell_embeddings.<locals>.Dataset'`** — same root
   cause (num_workers > 0 triggers subprocess pickling of a local class).
   Fix: same affinity shim.

5. **`KeyError: 'counts'` / `match 0/61497 genes`** — `_embed()` unconditionally set
   `feature_name` from `var_names`; for the reference, `var_names` are integer soma joinids,
   not gene symbols. The reference `var` already has the `feature_name` column.
   Fix: `if "feature_name" not in prepped.var.columns: prepped.var["feature_name"] = prepped.var_names`

6. **Reference embedding re-run on every call (~38 min)** — no caching. Fix:
   `_embed_reference_cached()` persists embedding as `.<hash>.scgpt_emb.npy` next to the
   reference file; invalidated by mtime. Subsequent calls complete in seconds.

7. **`JSONDecodeError` in `call_scgpt_annotate()`** — scGPT and PyTorch write log lines to
   stdout before the JSON array: "WARNING: CUDA is not available.", "scGPT - INFO - match N/M
   genes...". `json.loads(result.stdout)` fails because stdout starts with "W" not "[".
   Fix: scan `result.stdout.splitlines()` in reverse for the last line starting with `[`.

### Files Changed

- `annotation/fm_client.py` — `ensure_worker_compatible_h5ad()` extended; stdout JSON
  extraction fixed; timeout raised to 3600s (documents 38-min first-run cost).
- `bio_fm_worker/run_scgpt_embed.py` — `os.sched_getaffinity` shim; reference/query
  feature_name handling fixed; `_embed_reference_cached()` with disk cache.
- `annotation/pipeline.py` — calls `ensure_worker_compatible_h5ad()` before h5ad write.
- `annotation/baseline.py` — minor fixes from prior sub-phases.
- `annotation/reference.py` — minor fixes from prior sub-phases.
- `.gitignore` — added `*.scgpt_emb.npy`

### Checkpoint Directory

`gdown --folder` double-nests: `scGPT_human/scGPT_human/{args.json,best_model.pt,vocab.json}`.
Flattened to single-level `bio_fm_worker/checkpoints/scGPT_human/` so `pipeline.py`'s
default `model_dir` path resolves correctly.

## Verification Result

```
tests/test_bio_fm_integration.py::test_annotate_cell_type_tool_real_scgpt_and_baseline
annotate_cell_type_tool real end-to-end latency: 31.2s
PASSED
1 passed in 46.07s
```

Full fast suite: 98 passed, 0 failures (pre- and post-fix).

## Phase 4 Status

**Phase 4 (Bio-FM Tool Layer — Cell-Type Annotation) is COMPLETE.**  
All 5 plans (04-01 through 04-05) executed. All ANNOT requirements met.  
Next: Phase 5 (Perturbation + VCC).
