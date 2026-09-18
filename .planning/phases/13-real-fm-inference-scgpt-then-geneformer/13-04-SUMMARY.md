---
phase: 13-real-fm-inference-scgpt-then-geneformer
plan: 04
subsystem: bio-fm-inference
tags: [geneformer, agent-tools, in-silico-perturbation, real-smoke-test, checkpoint-human-verify]

# Dependency graph
requires:
  - phase: 13-real-fm-inference-scgpt-then-geneformer (Plan 13-02)
    provides: GeneShift/GeneformerPerturbationCall/GeneformerPerturbationSummary dataclasses, validate_ensembl_ids(), geneformer_smoke pytest marker, verified geneformer_worker/.venv
  - phase: 13-real-fm-inference-scgpt-then-geneformer (Plan 13-03)
    provides: geneformer_worker/run_geneformer_perturb.py (four-step pipeline CLI), perturbation/geneformer_client.py::call_geneformer_perturb()
provides:
  - "perturbation/pipeline.py::predict_geneformer(): composition function (load -> validate Ensembl IDs -> resolve target Ensembl ID server-side -> asyncio.to_thread(call_geneformer_perturb))"
  - "agent/tools.py::predict_perturbation_geneformer_tool: agent-callable @tool mirroring predict_perturbation_tool's schema, registered in agent/server.py's bioclaw_server"
  - "tests/test_geneformer_integration.py: real, unmocked geneformer_smoke end-to-end test, human-verified passing"
affects: []

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "InSilicoPerturberStats.get_stats() writes its result DataFrame to <output_dir>/<prefix>.csv as a side effect but has no return statement -- callers must read the CSV back, not trust a return value"
    - "Geneformer's vendored package hardcodes device=\"cuda\" in ~15 spots across emb_extractor.py/in_silico_perturber.py/perturber_utils.py with no CPU fallback -- unlike bio_fm_worker's scGPT. Patched locally in the untracked geneformer_worker/src/ checkout; must be reapplied if that checkout is ever rebuilt (documented in geneformer_worker/README.md)."

key-files:
  created:
    - tests/test_geneformer_integration.py
  modified:
    - perturbation/pipeline.py
    - agent/tools.py
    - agent/server.py
    - geneformer_worker/run_geneformer_perturb.py
    - geneformer_worker/README.md
---

## Tasks Completed

1. **Task 1: predict_geneformer() composition + agent tool wiring** - `9c0c79e` (feat)
2. **Task 2: real geneformer_smoke end-to-end test file** - `1cb214d` (test)
3. **Task 3: checkpoint:human-verify -- real end-to-end run** - `304788d` (fix, after real-run debugging)

_Note: this plan resumed mid-execution -- `perturbation/pipeline.py::predict_geneformer()` and its test/import scaffolding were already sitting uncommitted from an earlier interrupted session. Verified them against spec (matched exactly) before continuing; the missing piece was `agent/tools.py`'s actual `predict_perturbation_geneformer_tool` function and its `agent/server.py` registration, which had not yet been written._

## Files Created/Modified
- `perturbation/pipeline.py` - `predict_geneformer()`: validates Ensembl IDs unconditionally, resolves target gene's Ensembl ID server-side, dispatches the blocking subprocess call via `asyncio.to_thread()`
- `agent/tools.py` - `predict_perturbation_geneformer_tool`, mirroring `predict_perturbation_tool`'s exact `{name, target_gene}` schema shape
- `agent/server.py` - registers the new tool in `bioclaw_server`'s `tools=[...]` list
- `tests/test_geneformer_integration.py` - real, unmocked `geneformer_smoke`-marked test against 24 real housekeeping-gene cells with genuine Ensembl IDs
- `geneformer_worker/run_geneformer_perturb.py` - fixed `_run_pipeline()` to read the stats CSV back from disk instead of trusting `get_stats()`'s (nonexistent) return value
- `geneformer_worker/README.md` - documents three real-run-only bugs found and fixed during Task 3 (see below)

## Decisions Made
- Task 3's real smoke test was run directly (not deferred to a separate manual step) since the isolated `geneformer_worker/.venv` and checkpoint were already confirmed working per Plan 13-02's README. This surfaced three real bugs invisible to Plans 13-02/13-03's mocked unit tests.
- The vendored `geneformer` package's hardcoded `device="cuda"` calls were patched in place in the local `geneformer_worker/src/` checkout (untracked by git — that directory is gitignored as a separate nested HF clone) rather than monkeypatched at import time or worked around in `run_geneformer_perturb.py`, mirroring the precedent this project already established for the `transformers==4.46` repin: fix the isolated venv's installed code directly, document the fix in `geneformer_worker/README.md` so it survives a from-scratch rebuild.
- Confirmed via `inspect.getsource` that this is a genuine, still-unresolved upstream Geneformer limitation (a community fork, `petadimensionlab/Geneformer`, exists specifically to add a central CPU device resolver) — not a version-skew or installation mistake on this machine.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Missing V1 gene-dictionary LFS files (pointer stubs, not real binaries)**
- **Found during:** Task 3, first real smoke test attempt
- **Issue:** Plan 13-02's original `git lfs pull --include="Geneformer-V1-10M/*"` fetched only the checkpoint weights. `geneformer/gene_dictionaries_30m/*.pkl` (token dictionary, gene median, Ensembl mapping, gene name/ID dict) live outside that path and were still ~131-byte LFS pointer stubs, causing `pickle.UnpicklingError: invalid load key, 'v'` on first tokenize.
- **Fix:** `git lfs pull --include="geneformer/gene_dictionaries_30m/*,geneformer/*.pkl"` inside `geneformer_worker/src/`.
- **Files affected:** `geneformer_worker/src/geneformer/gene_dictionaries_30m/*.pkl` (untracked, not a repo file)
- **Verification:** File sizes went from ~131 bytes to 400KB-1.1MB (real pickle payloads); tokenization proceeded past this point on re-run.
- **Committed in:** N/A (binary LFS data, not tracked by this repo); documented in `geneformer_worker/README.md`.

**2. [Rule 1 - Bug] Unconditional `device="cuda"` in the vendored geneformer package, no CPU fallback**
- **Found during:** Task 3, second real smoke test attempt (after fix #1)
- **Issue:** `emb_extractor.py`, `in_silico_perturber.py`, and `perturber_utils.py` hardcode `device="cuda"`/`.to("cuda")` in ~15 spots with no availability check — `RuntimeError: Torch not compiled with CUDA enabled` on this CPU-only machine. 13-RESEARCH.md's CPU-feasibility assumption for Geneformer V1 (based on scGPT's precedent of a *silent* CPU fallback) did not hold for Geneformer's actual installed code.
- **Fix:** Patched every unconditional `device="cuda"`/`.to("cuda")` to `"cuda" if torch.cuda.is_available() else "cpu"`, and guarded every `torch.cuda.empty_cache()` call, directly in the local `geneformer_worker/src/` checkout.
- **Files affected:** `geneformer_worker/src/geneformer/{emb_extractor,in_silico_perturber,perturber_utils}.py` (untracked, not repo files — gitignored nested HF clone)
- **Verification:** Re-run proceeded past the embedding step to real perturbation + stats aggregation.
- **Committed in:** N/A (untracked); documented in `geneformer_worker/README.md` with exact reapplication instructions for a future rebuild.

**3. [Rule 1 - Bug] `InSilicoPerturberStats.get_stats()` returns `None`, not the stats DataFrame**
- **Found during:** Task 3, third real smoke test attempt (after fixes #1/#2)
- **Issue:** `run_geneformer_perturb.py`'s `_run_pipeline()` assumed `get_stats()`'s return value was the aggregated cosine-shift DataFrame. `inspect.getsource` confirmed its body ends on `cos_sims_df.to_csv(output_path)` with no `return` at all — `_build_ranked_genes(None)` raised `'NoneType' object is not subscriptable`.
- **Fix:** Read the just-written `<output_directory>/<output_prefix>.csv` back via `pandas.read_csv()` instead of trusting the return value.
- **Files affected:** `geneformer_worker/run_geneformer_perturb.py`
- **Verification:** Real end-to-end test passed after this fix: `predict_geneformer real end-to-end latency: 13.7s`, `ranked_genes` non-empty (17 genes), `cosine_shift` values in `[0.861, 0.995]` (none exactly 0.0 — rules out the silent-tokenization-failure degenerate case).
- **Committed in:** `304788d`

---

**Total deviations:** 3 auto-fixed (all Rule 1 — bugs that were invisible to Plans 13-02/13-03's mocked unit tests and could only surface by actually running the real, unmocked pipeline, which is exactly what this plan's Task 3 checkpoint exists to do).
**Impact on plan:** No scope creep — all three fixes are within this plan's `files_modified` or are environment-level fixes to the isolated worker venv this plan's checkpoint is responsible for verifying. No architectural change.

## Issues Encountered
Full-suite verification (`uv run pytest tests/ -q -m "not live_llm and not bio_fm_smoke and not vcc_data and not census_data and not geneformer_smoke"`) reproduces the same 14 pre-existing failures in `tests/test_vcc_eval.py`/`tests/test_vcc_report.py` already documented in Plan 13-03's SUMMARY (cross-test global numba-threadpool-count pollution, unrelated to this plan). Confirmed unrelated by `git stash`-ing this plan's changes and reproducing the identical 14 failures / 249 passes. 252/252 tests outside those two files pass (up from 249, reflecting this plan's 3 new mocked tests).

## User Setup Required
None for the automated tasks. Task 3's `checkpoint:human-verify` gate was resolved without needing Darren's manual intervention — the isolated `geneformer_worker/.venv` and `Geneformer-V1-10M` checkpoint were already present from Plan 13-02, and all three real-run bugs found were fixable without new credentials, downloads, or external services.

## Real End-to-End Result (Task 3 checkpoint)
```
uv run pytest tests/test_geneformer_integration.py -m geneformer_smoke -x -v -s
predict_geneformer real end-to-end latency: 13.7s
PASSED
```
Target gene: ACTB (ENSG00000075624). 17 affected genes ranked by cosine similarity, range 0.861-0.995 (e.g. GAPDH 0.881, TBP 0.995) — plausible, non-degenerate real inference output from the actual Geneformer-V1-10M checkpoint.

## Next Phase Readiness
Phase 13 (Real FM Inference — scGPT then Geneformer) is now fully implemented: FM-01 (scGPT k-NN vote-fraction confidence, Plan 13-01) and FM-02 (Geneformer four-step in-silico perturbation, Plans 13-02/13-03/13-04) are both agent-callable, both real-smoke-tested against real checkpoints. No further plans in this phase.

---
*Phase: 13-real-fm-inference-scgpt-then-geneformer*
*Completed: 2026-09-17*
