---
phase: 01-ingest-qc-pipeline
plan: 05
subsystem: data
tags: [scanpy, anndata, sqlite, pytest, single-cell, ingest, qc]

# Dependency graph
requires:
  - phase: 01-ingest-qc-pipeline (01-02)
    provides: ingest/loaders.py (10x .mtx/.h5 -> AnnData), ingest/contract.py (counts-layer immutability)
  - phase: 01-ingest-qc-pipeline (01-03)
    provides: ingest/qc.py (QCConfig, metrics, filtering, audit log)
  - phase: 01-ingest-qc-pipeline (01-04)
    provides: ingest/store.py (DatasetStore save/load/list, versioned registry)
provides:
  - ingest/pipeline.py::ingest_10x(path, name, qc_config=None, store_root="data") -> dataset_id
  - The single coarse-grained Phase 1 entrypoint later phases (agent/tool wrapper, Phase 3) call
  - Discovery + fix of a checksum-invalidation gap between qc.py filtering and contract.py's write-lock
provides_context: [Phase 1 complete — all 5 plans done, full test suite green]
affects: [phase-02-analysis, phase-03-agent-wiring]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Coarse-grained deterministic pipeline behind one entrypoint (loaders -> contract -> qc -> store), no LLM/agent involvement in Phase 1"
    - "Re-freeze/re-checksum the immutable counts layer after any operation that resizes the AnnData (QC filtering), since slicing allocates a new writeable buffer"

key-files:
  created:
    - ingest/pipeline.py
    - tests/test_pipeline.py
  modified: []

key-decisions:
  - "Re-freeze layers['counts'] (contract.set_counts_layer) a second time immediately after qc.run(), because filter_cells/filter_genes and boolean-mask .copy() slicing allocate a new writeable sparse buffer whose shape reflects the post-filter dataset -- the original pre-filter checksum no longer matches. The write-lock/checksum's job is to protect counts *values* from corruption (e.g. accidental normalization), not to pin the pre-filter cell count, so re-freezing against the final persisted shape is correct, not a contract violation."
  - "store_root plumbed through as an explicit ingest_10x() kwarg (default 'data') so tests use tmp_path and never touch the real data/ directory."

patterns-established:
  - "Integration tests for coarse-grained entrypoints should call verify_counts_integrity() on the *stored and reloaded* result, not just the in-memory return value -- this is what caught the checksum gap module-level unit tests couldn't see."

requirements-completed: ["INGEST-01", "INGEST-02", "INGEST-03", "QC-01", "QC-02"]

duration: 9min
completed: 2026-09-04
---

# Phase 1 Plan 5: Pipeline Integration Summary

**Wired loaders/contract/qc/store into `ingest_10x(path, name, qc_config=None) -> dataset_id`, and in doing so found and fixed a real integration bug: QC filtering silently invalidated the raw-counts checksum by allocating a fresh writeable buffer.**

## Performance

- **Duration:** 9 min
- **Started:** 2026-09-04T15:01:17Z
- **Completed:** 2026-09-04T15:10:24Z
- **Tasks:** 2
- **Files modified:** 2 (both created)

## Accomplishments
- `ingest/pipeline.py::ingest_10x()` is now the single call a future agent tool wrapper needs: `loaders.load()` -> `contract.set_counts_layer()` -> `qc.run()` -> `store.save()`, returning `"{name}@{version}"`.
- Found (via RED test) and fixed an integration-only bug: `qc.run()`'s filtering (`filter_cells`/`filter_genes`, boolean-mask `.copy()` slicing) creates a new, writeable sparse buffer for `layers['counts']` whose checksum no longer matches the one computed before filtering. Fixed by re-calling `contract.set_counts_layer()` after `qc.run()` so the write-lock/checksum reflect what's actually persisted.
- Proved all five Phase 1 requirements (INGEST-01/02/03, QC-01/02) hold simultaneously on the *composed* pipeline output, not just within each module's own unit tests.
- Full Phase 1 test suite (fixtures, loaders, contract, qc, store, pipeline): **30 passed, 0 failed** — Phase 1 is now fully green end to end.

## Task Commits

Each task was committed atomically:

1. **Task 1: ingest_10x() entrypoint, wired end to end** - `a507754` (feat) — includes the checksum re-freeze fix, verified RED (without the fix) then GREEN (with it) before committing
2. **Task 2: Cross-module edge cases and full-suite verification** - `50ee90a` (test) — no pipeline.py changes needed; existing implementation already handled all three edge cases correctly

**Plan metadata:** (this commit)

_Note: Task 1 was developed test-first — the fix's necessity was proven by temporarily stripping it and confirming `verify_counts_integrity()` failed, then restoring it and confirming green, before the single feat commit was made._

## Files Created/Modified
- `ingest/pipeline.py` - `ingest_10x(path, name, qc_config=None, store_root="data") -> str`; composes the four Wave 1 modules, includes the post-QC re-freeze fix
- `tests/test_pipeline.py` - 6 integration tests: mtx end-to-end, h5 end-to-end, qc_config threading, re-ingest versioning, already-cell-called input, empty-result-after-filtering

## Decisions Made
- Re-freeze `layers['counts']` after `qc.run()` rather than changing `qc.py` or `contract.py` — keeps each Wave 1 module's existing, already-tested behavior intact and fixes the wiring gap at the integration seam where it actually belongs.
- Used `QCConfig(min_genes_per_cell=1)` (not 0) as the "lenient" config across most tests, since `tiny_mtx_dir`'s fixture-designed all-zero cell (column 0) should legitimately be filtered by any real QC pass — `min_genes_per_cell=1` cleanly separates "the one deliberately-empty test cell" from "everything else," matching `01-VALIDATION.md`'s already-cell-called edge case intent.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Checksum invalidation after QC filtering**
- **Found during:** Task 1 (writing the RED end-to-end test per `<behavior>`, which explicitly requires `verify_counts_integrity()` to return `True` on the stored/reloaded result)
- **Issue:** `ingest_10x()` set the counts-layer contract (copy + freeze + checksum) once, immediately after `loaders.load()`, per `01-RESEARCH.md` Pattern 1's example. But `qc.run()` filters cells/genes via `sc.pp.filter_cells`/`filter_genes` (in-place subsetting) and boolean-mask `.copy()` slices for mito/doublet filtering — both operations allocate a new underlying sparse `.data` array for every layer, including `counts`. The new array is writeable again (the original freeze no longer applies) and has a different byte content (fewer cells/genes) than what the pre-filter checksum was computed against. `verify_counts_integrity()` on the final stored/reloaded dataset returned `False`, not `True`.
- **Fix:** Call `contract.set_counts_layer(adata)` a second time, immediately after `qc.run()` returns, so the write-lock and checksum are established against the final, actually-persisted counts layer.
- **Files modified:** `ingest/pipeline.py`
- **Verification:** Confirmed by temporarily removing the second `set_counts_layer()` call and re-running `tests/test_pipeline.py` — `test_ingest_10x_mtx_end_to_end` failed with `AssertionError: assert False is True` on `verify_counts_integrity(adata)`, exactly as expected (RED). Restoring the fix returned the suite to green (GREEN). Full suite (`uv run pytest tests/ -q`) confirmed 30/30 passing afterward.
- **Committed in:** `a507754` (Task 1 commit)

---

**Total deviations:** 1 auto-fixed (1 bug fix, Rule 1)
**Impact on plan:** Necessary for correctness — without this fix, INGEST-02's "counts layer is provably intact" guarantee silently breaks for any dataset that QC actually filters (i.e., almost every real dataset). No scope creep; this is exactly the kind of integration-only gap this plan exists to surface, per its own objective statement.

## Issues Encountered
None beyond the deviation documented above.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness

Phase 1 (Ingest + QC Pipeline) is complete: all 5 plans (01-01 through 01-05) done, full test suite green (30 tests), and `ingest_10x(path, name, qc_config=None) -> dataset_id` is the stable, proven entrypoint Phase 3 (agent/MCP tool wiring) will call. `01-VALIDATION.md`'s phase-gate requirement (full suite green before `/gsd:verify-work`) is satisfied.

No blockers for Phase 2 (Analysis) from this plan. Carried-forward blockers from earlier in Phase 1 (Phase 4 bio-FM VRAM sizing, Phase 5 GEARS environment isolation, Phase 6 hallucination-mitigation pattern) remain open and unaffected by this plan — see STATE.md Blockers/Concerns.

---
*Phase: 01-ingest-qc-pipeline*
*Completed: 2026-09-04*

## Self-Check: PASSED

- FOUND: ingest/pipeline.py
- FOUND: tests/test_pipeline.py
- FOUND: .planning/phases/01-ingest-qc-pipeline/01-05-SUMMARY.md
- FOUND: a507754 (git log)
- FOUND: 50ee90a (git log)
