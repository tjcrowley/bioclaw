---
phase: 13-real-fm-inference-scgpt-then-geneformer
plan: 03
subsystem: bio-fm-inference
tags: [geneformer, subprocess-worker, in-silico-perturbation, tdd, python3.10-venv]

# Dependency graph
requires:
  - phase: 13-real-fm-inference-scgpt-then-geneformer (Plan 13-02)
    provides: GeneShift/GeneformerPerturbationCall dataclasses, validate_ensembl_ids(), geneformer_smoke pytest marker, verified geneformer_worker/.venv (Python 3.10, transformers==4.46 repin)
  - phase: 04-annotation-real-fm (annotation/fm_client.py)
    provides: subprocess/JSON-over-stdout dispatch contract this plan reuses verbatim
provides:
  - "geneformer_worker/run_geneformer_perturb.py: real four-step Geneformer pipeline CLI (tokenize -> extract embeddings -> perturb -> aggregate/rank by cosine shift) with an independent hard match-rate guard"
  - "perturbation/geneformer_client.py::call_geneformer_perturb(): main-venv subprocess shim to the isolated geneformer_worker/.venv, mirroring call_scgpt_annotate()'s contract"
  - "tests/test_perturbation_geneformer_client.py: mocked-subprocess unit tests requiring no isolated venv"
affects: [13-04-predict-geneformer-tool-wiring]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Geneformer's model_version='V1' auto-overrides model_input_size/special_token/token_dictionary_file/gene_median_file/gene_mapping_file internally across all four pipeline classes -- callers should not pass V2 defaults (model_input_size=4096) expecting them to matter"
    - "InSilicoPerturberStats aggregate_gene_shifts output must be read via Affected_gene_name/Affected_Ensembl_ID (the perturbation's target), not Gene_name/Ensembl_ID (the perturbed gene, constant across all rows)"

key-files:
  created:
    - geneformer_worker/run_geneformer_perturb.py
    - perturbation/geneformer_client.py
    - tests/test_perturbation_geneformer_client.py
  modified: []

key-decisions:
  - "TranscriptomeTokenizer called with model_input_size=2048 (not Pattern 3's 4096) to match the real, live-introspected V1 default rather than the V2 value the research doc's snippet showed"
  - "ranked_genes built from Affected_gene_name/Affected_Ensembl_ID/Cosine_sim_mean, excluding rows where Affected == 'cell_emb' -- the real get_stats() column names differ from 13-RESEARCH.md Pattern 3's documented Gene_name/Ensembl_ID"
  - "call_geneformer_perturb() timeout defaults to 7200s (2h), double call_scgpt_annotate()'s 3600s, per Pitfall 3's four-step-pipeline wall-clock warning"
  - "Query h5ad is symlinked into a dedicated work_dir/data_input/ directory before tokenize_data(), since TranscriptomeTokenizer.tokenize_files() globs an entire directory for *.h5ad rather than accepting a single file path"

patterns-established:
  - "Subprocess worker scripts (bio_fm_worker/run_scgpt_embed.py, geneformer_worker/run_geneformer_perturb.py) always print exactly one JSON value to stdout on success and a one-line stderr message + non-zero exit on any failure; main-venv clients scan stdout in reverse for the JSON line, never assume the last line of stdout is always JSON (log noise may follow)"

requirements-completed: [FM-02]

# Metrics
duration: 25min
completed: 2026-09-17
---

# Phase 13 Plan 03: Geneformer Four-Step Pipeline Worker + Subprocess Client Summary

**Real Geneformer in-silico-perturbation pipeline (tokenize -> embed -> perturb -> aggregate cosine-shift stats) running inside the isolated Python 3.10 geneformer_worker/.venv, dispatched from the main venv via a subprocess/JSON contract that mirrors call_scgpt_annotate() exactly.**

## Performance

- **Duration:** ~25 min
- **Started:** 2026-09-17T21:20:00Z (approx.)
- **Completed:** 2026-09-17T21:53:00Z
- **Tasks:** 2 completed
- **Files modified:** 3 (all new)

## Accomplishments
- `geneformer_worker/run_geneformer_perturb.py` implements the real four-step pipeline (`TranscriptomeTokenizer` -> `EmbExtractor` -> `InSilicoPerturber` -> `InSilicoPerturberStats`) against the actual installed `geneformer` package API (verified via live `inspect.signature`/`inspect.getsource`, not just docs), with a hard vocabulary match-rate guard (<50% -> exit 1) computed independently from Plan 13-02's presence-only validator.
- Found and corrected two real drifts from 13-RESEARCH.md Pattern 3 during the mandated live-introspection step: (1) V1's `model_input_size`/`special_token` are unconditionally overridden inside `TranscriptomeTokenizer.__init__` when `model_version="V1"`, not free parameters; (2) `InSilicoPerturberStats.get_stats(mode="aggregate_gene_shifts")`'s real output columns are `Affected_gene_name`/`Affected_Ensembl_ID` for the ranked/affected genes, not `Gene_name`/`Ensembl_ID` (which describe the constant perturbed gene).
- `perturbation/geneformer_client.py::call_geneformer_perturb()` shells out to the worker exactly like `call_scgpt_annotate()`, built test-first (TDD), and never lets a subprocess failure/timeout escape as anything but `RuntimeError`.

## Task Commits

Each task was committed atomically:

1. **Task 1: geneformer_worker/run_geneformer_perturb.py -- four-step pipeline CLI** - `1fe534d` (feat)
2. **Task 2: perturbation/geneformer_client.py subprocess shim + tests** - `a67b8a0` (test, RED) then `abbd7f1` (feat, GREEN)

**Plan metadata:** (this commit, docs: complete plan)

_Note: Task 2 was TDD -- RED then GREEN commits, no separate refactor commit needed._

## Files Created/Modified
- `geneformer_worker/run_geneformer_perturb.py` - CLI entrypoint for the real four-step Geneformer pipeline; runs inside `geneformer_worker/.venv` only
- `perturbation/geneformer_client.py` - `call_geneformer_perturb()`, the main-venv subprocess shim
- `tests/test_perturbation_geneformer_client.py` - 4 mocked-subprocess unit tests (success parse, non-zero exit, timeout, exact command shape)

## Decisions Made
- Confirmed via live `inspect.signature`/`inspect.getsource` on the real installed `geneformer` package (per the task's mandated re-verification step) that all four pipeline classes auto-select their V1-specific dictionary file paths (`*_30M.pkl` variants) purely from `model_version="V1"` -- this script never passes `token_dictionary_file`/`gene_median_file`/`gene_mapping_file`/`gene_name_id_dictionary_file` explicitly.
- The worker computes `match_rate` itself by loading `geneformer.TOKEN_DICTIONARY_FILE_30M` directly (the same file `TranscriptomeTokenizer`/`InSilicoPerturber`/`InSilicoPerturberStats` resolve internally for `model_version="V1"`), so the guard runs before the expensive tokenize/embed/perturb steps, not after.
- `ranked_genes` excludes the `Affected == "cell_emb"` row from `get_stats()`'s output -- that row represents the whole-cell embedding shift, not a specific gene, and would not fit `GeneShift`'s per-gene contract.
- Intermediate `work_dir` (tokenized/embs/perturb_out/stats_out subdirectories) is never cleaned up, per the plan's explicit instruction mirroring Pitfall 3's debugging-visibility guidance.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Corrected TranscriptomeTokenizer's model_input_size from Pattern 3's 4096 to the real V1 value 2048**
- **Found during:** Task 1, mandated live-introspection step (`inspect.signature`/`inspect.getsource` on the real installed `geneformer` package)
- **Issue:** 13-RESEARCH.md Pattern 3's interface snippet showed `TranscriptomeTokenizer(model_input_size=4096, model_version="V1")` -- but `model_input_size=4096`/`special_token=True` are V2's defaults; reading `TranscriptomeTokenizer.__init__`'s source confirmed that when `model_version="V1"` is passed, the constructor unconditionally sets `self.model_input_size = 2048` and `self.special_token = False` regardless of what was passed in, and swaps in the `_30M` dictionary file variants. Passing 4096 would have been silently overridden (harmless) but was misleading and worth correcting for a script that will be read/maintained.
- **Fix:** Call `TranscriptomeTokenizer(model_input_size=2048, model_version="V1")`, with an inline code comment (and this SUMMARY/module docstring) explaining the override behavior.
- **Files modified:** geneformer_worker/run_geneformer_perturb.py
- **Verification:** Confirmed via live `inspect.getsource(geneformer.TranscriptomeTokenizer.__init__)` reading the actual override branch (`elif self.model_version == "V1": self.model_input_size = 2048; self.special_token = False`).
- **Committed in:** 1fe534d (Task 1 commit)

**2. [Rule 1 - Bug] Corrected ranked_genes column mapping to Affected_gene_name/Affected_Ensembl_ID, not Gene_name/Ensembl_ID**
- **Found during:** Task 1, same live-introspection step, reading `geneformer.in_silico_perturber_stats.isp_aggregate_gene_shifts`'s source
- **Issue:** 13-RESEARCH.md Pattern 3's interface comment documented `get_stats()`'s output columns as `Gene, Gene_name, Ensembl_ID, N_Detections, Cosine_sim_mean, Cosine_sim_stdev` and the plan's literal task instructions said to build `ranked_genes` from `row.Gene_name`/`row.Ensembl_ID`. Reading the actual aggregation function's source showed `Gene_name`/`Ensembl_ID` describe the single *perturbed* gene (constant across every row, since this script only ever perturbs one target gene) -- the per-row *affected*-gene identity these ranked results need to report is in `Affected_gene_name`/`Affected_Ensembl_ID` instead. Following the plan's literal instruction would have produced a ranked list where every entry showed the target gene's own name.
- **Fix:** Build `ranked_genes` from `row.Affected_gene_name`/`row.Affected_Ensembl_ID`/`row.Cosine_sim_mean`, and filter out the `Affected == "cell_emb"` row (the whole-cell-embedding-shift summary row, not a gene).
- **Files modified:** geneformer_worker/run_geneformer_perturb.py
- **Verification:** Confirmed via live `inspect.getsource(geneformer.in_silico_perturber_stats.isp_aggregate_gene_shifts)` reading the DataFrame column assignments directly.
- **Committed in:** 1fe534d (Task 1 commit)

---

**Total deviations:** 2 auto-fixed (both Rule 1 - bugs caught by the plan's own mandated live-introspection step before they could ship as silently-wrong output)
**Impact on plan:** Both corrections are exactly what the plan's Task 1 introspection instruction was designed to catch ("note any drift from Pattern 3 in a code comment"). No scope creep -- same files, same task, no architectural change.

## Issues Encountered
Full-suite verification (`uv run pytest tests/ -q -m "not live_llm and not bio_fm_smoke and not vcc_data and not census_data"`) surfaces 14 pre-existing failures in `tests/test_vcc_eval.py`/`tests/test_vcc_report.py` caused by cross-test global numba-threadpool-count pollution (`numba.set_num_threads` receiving `n=0`), unrelated to this plan's files. Confirmed pre-existing by reproducing identically with `--ignore=tests/test_perturbation_geneformer_client.py`. Root cause narrowed down further than Plan 13-02's earlier note (which suspected polars string-cache) and logged to `.planning/phases/13-real-fm-inference-scgpt-then-geneformer/deferred-items.md`. Not fixed (out of scope -- files not in this plan's `files_modified`). All 249 tests outside those two files pass; `tests/test_perturbation_geneformer_client.py`'s 4 new tests pass both in isolation and as part of the full suite.

## User Setup Required
None - no external service configuration required. `geneformer_worker/.venv` and the `Geneformer-V1-10M` checkpoint were already set up and verified working in Plan 13-02.

## Next Phase Readiness
`geneformer_worker/run_geneformer_perturb.py` and `perturbation/geneformer_client.py::call_geneformer_perturb()` are ready for Plan 13-04 to wire into a `predict_geneformer()` composition function and an agent tool layer (`predict_perturbation_geneformer_tool`), plus a `checkpoint:human-verify` real end-to-end smoke test against the actual `geneformer_worker/.venv` and `Geneformer-V1-10M` checkpoint (this plan's own live pipeline run was not executed end-to-end -- only syntax-validated and unit-tested with mocked subprocess calls, per this plan's scope).

---
*Phase: 13-real-fm-inference-scgpt-then-geneformer*
*Completed: 2026-09-17*

## Self-Check: PASSED

All created files and commit hashes verified present on disk / in git log.
