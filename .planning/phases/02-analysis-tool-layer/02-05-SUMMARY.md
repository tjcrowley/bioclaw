---
phase: 02-analysis-tool-layer
plan: 05
subsystem: analysis
tags: [scanpy, anndata, sqlite, pipeline, dataclasses]

# Dependency graph
requires:
  - phase: 02-analysis-tool-layer
    provides: "preprocess() (02-02), cluster() (02-03), differential_expression() (02-04), bounded-summary dataclasses (02-01)"
  - phase: 01-ingest-qc-pipeline
    provides: "DatasetStore.load/save, ingest.contract.verify_counts_integrity(), ingest/pipeline.py::ingest_10x as the style precedent"
provides:
  - "analysis/pipeline.py::analyze(name, version=None, config=None, store_root='data') -> (new_dataset_id, summary_dict) -- the Wave 2 entrypoint Phase 3's agent tool wrapper will call"
  - "AnalysisConfig dataclass logged verbatim to adata.uns['analysis'], mirroring QCConfig/adata.uns['qc']"
affects: [03-agent-orchestration-wiring]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Coarse-grained pipeline entrypoint composes Wave 1 module functions by unpacking one config dataclass into each function's plain kwargs, mirroring ingest/pipeline.py::ingest_10x"
    - "verify_counts_integrity() called both immediately after store.load() and immediately before store.save() -- the load-bearing defense against Pitfall 6 (write-lock does not survive an h5ad round-trip)"
    - "dataclasses.replace(summary, dataset_id=new_id) to patch the store-assigned id into summaries built before the id was known"

key-files:
  created:
    - analysis/pipeline.py
    - tests/test_analysis_pipeline.py
  modified: []

key-decisions:
  - "Task 1 implemented analyze() without the DE branch (de_summary hardcoded to None, run_de/de_* fields accepted but unused) so the core load->verify->preprocess->cluster->verify->save flow could be committed and verified independently of DE, per the plan's task split"
  - "Task 2 added DE composition as a pure extension (no changes to the already-committed core flow) -- config.run_de gates a de_groupby/de_group1 presence check (ValueError if missing) before calling differential_expression(), then patches dataset_id into the DE summary alongside preprocess/cluster"
  - "All 7 tests (covering both Task 1 and Task 2 behavior) were written up front in a single RED commit, since both tasks share one test file and one behavior contract -- test-per-task granularity was preserved at the implementation-commit level instead"

patterns-established:
  - "Pipeline entrypoints (ingest/pipeline.py, analysis/pipeline.py) never mutate the caller's AnnData directly -- they thread the return value from load() through each composed function's own copy-on-call-boundary convention (preprocess/cluster/differential_expression already .copy() internally)"

requirements-completed: ["ANLYS-01", "ANLYS-02", "ANLYS-03", "ANLYS-04"]

# Metrics
duration: 5min
completed: 2026-09-04
---

# Phase 2 Plan 05: analyze() Pipeline Integration Summary

**Wave 2 entrypoint composing preprocess -> cluster -> optional Wilcoxon DE on top of Phase 1's DatasetStore, with verify_counts_integrity() enforced both immediately after load and immediately before save to close the Pitfall 6 round-trip gap.**

## Performance

- **Duration:** ~5 min
- **Started:** 2026-09-04T20:24:00Z (approx, first commit of this plan)
- **Completed:** 2026-09-04T20:29:00Z
- **Tasks:** 2 completed
- **Files modified:** 2 (analysis/pipeline.py created, tests/test_analysis_pipeline.py created)

## Accomplishments
- `analysis/pipeline.py::analyze()` loads a named/versioned dataset from `DatasetStore`, verifies the raw-counts contract, runs `preprocess -> cluster -> optional differential_expression`, verifies the contract again, saves as a new store version, and returns `(new_dataset_id, summary_dict)` -- never a raw matrix or per-cell array.
- `AnalysisConfig` dataclass (mirroring `QCConfig`) is the single source of all analysis parameters, logged verbatim into `adata.uns["analysis"]`.
- `verify_counts_integrity()` is enforced at both pipeline boundaries (immediately after `store.load()`, immediately before `store.save()`), raising a clear `RuntimeError` naming the dataset on failure -- closes Pitfall 6 (the counts-layer write-lock does not survive a `write_h5ad`/`read_h5ad` round-trip; only the checksum comparison remains once a dataset is store-loaded).
- Optional DE composition (`config.run_de`) validates `de_groupby`/`de_group1` are both set before calling `differential_expression`, raising `ValueError` naming the missing field(s) rather than guessing an implicit comparison.
- All three summary dataclasses (`PreprocessSummary`, `ClusterSummary`, `DESummary`) have their `dataset_id` patched to the new store-assigned id via `dataclasses.replace`, then flattened via `dataclasses.asdict` into the returned `summary_dict`.
- Full test suite (Phase 1 + Phase 2 combined): 58 tests passing.

## Task Commits

Each task was committed atomically (plus a preceding shared RED commit covering both tasks' behavior):

1. **RED: failing tests for analyze()** - `a1d2648` (test)
2. **Task 1: analyze() -- load, verify, compose preprocess+cluster, verify, save** - `f633ae8` (feat)
3. **Task 2: Optional DE composition + full regression** - `83d6a09` (feat)

**Plan metadata:** (this commit, immediately following)

_Note: both tasks' `<behavior>` was written as one test file up front (7 tests), since the plan's two tasks share a single test module and the DE tests naturally extend the same fixtures/helpers as the core tests. Task 1's implementation commit deliberately hardcoded `de_summary = None` (deferring the DE branch to Task 2, per the plan's explicit instruction), so `uv run pytest tests/test_analysis_pipeline.py -q -k "not de"` was used to verify Task 1's scope in isolation before committing, then the full file (`-x -q`, all 7 tests) was verified green after Task 2's commit._

## Files Created/Modified
- `analysis/pipeline.py` - `AnalysisConfig` dataclass + `analyze()` entrypoint composing preprocess/cluster/diffexp on top of DatasetStore, with the two `verify_counts_integrity()` checkpoints
- `tests/test_analysis_pipeline.py` - 7 integration tests covering new-version creation, round-trip checksum integrity, logged config, bounded/patched summaries, `KeyError` propagation, optional DE composition, and DE misconfiguration `ValueError`

## Decisions Made
- Task-split implementation: Task 1's commit contains the core flow with `de_summary` hardcoded to `None` (DE branch deferred exactly as the plan specified); Task 2's commit is a pure additive diff introducing the `config.run_de` branch. No changes were needed to Task 1's code when adding Task 2.
- Reordered summary-patching to happen after `store.save()` for all three summaries (`preprocess`, `cluster`, `de`) uniformly, since `new_id` is only known post-save -- matches the plan's Task 2 note to "reorder step 8 if needed."
- Kept the RuntimeError messages self-contained (naming which checkpoint failed and the dataset id) rather than a single generic message, so a future agent/caller can distinguish "corrupted at rest" from "corrupted by this pipeline run" without additional debugging.

## Deviations from Plan

None - plan executed exactly as written. `AnalysisConfig` fields, `analyze()` signature, verification checkpoints, and DE validation all match the plan's `<action>` specification verbatim.

## Issues Encountered

None. All 7 tests passed on first implementation attempt for both tasks; no auto-fixes, no blocking issues, no auth gates.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

Phase 2 (Analysis Tool Layer) is now complete: all 5 plans executed, `ANLYS-01` through `ANLYS-04` demonstrated end to end through `analyze()` on top of Phase 1's `DatasetStore`, with the raw-counts contract intact across the full round trip. `analysis/pipeline.py::analyze()` is the single entrypoint Phase 3's agent tool wrapper will call, mirroring `ingest/pipeline.py::ingest_10x()`'s shape exactly (`(name, ...) -> new_dataset_id` plus a bounded summary here). No blockers for Phase 3.

---
*Phase: 02-analysis-tool-layer*
*Completed: 2026-09-04*

## Self-Check: PASSED

- FOUND: analysis/pipeline.py
- FOUND: tests/test_analysis_pipeline.py
- FOUND: .planning/phases/02-analysis-tool-layer/02-05-SUMMARY.md
- FOUND commit: a1d2648
- FOUND commit: f633ae8
- FOUND commit: 83d6a09
