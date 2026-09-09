---
phase: 05-perturbation-response-tool-vcc-benchmark-harness
plan: "05"
subsystem: benchmark
tags: [benchmark, vcc, cell-eval, perturbation, report, metrics]

# Dependency graph
requires:
  - phase: 05-04
    provides: run_vcc_eval() returning predictor_metrics + baseline_metrics + dataset_id + target_genes
  - phase: 05-01
    provides: benchmark/ package skeleton, DatasetStore, perturbation_adata fixture

provides:
  - benchmark/report.py::build_benchmark_report() -- VCC-03 structurally baseline-enforced report builder
  - benchmark/report.py::run_full_benchmark() -- single top-level orchestration entrypoint for Plan 05-06
  - benchmark/report.py::to_markdown() -- human-readable predictor vs baseline comparison table
  - benchmark/report.py::DEFAULT_QC_PROVENANCE_NOTE -- importable constant for test assertions

affects:
  - 05-06 (real VCC data smoke test calls run_full_benchmark() directly)
  - agent/tools.py predict_perturbation_tool (may call run_full_benchmark or to_markdown for display)

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Structural enforcement of baseline presence: raise ValueError at report construction time, not at documentation layer"
    - "Plain dict report shape (not dataclass) -- trivially JSON-serializable, no import dependency at call sites"
    - "DEFAULT_QC_PROVENANCE_NOTE exported as module-level constant so tests can assert exact text without hardcoding"

key-files:
  created:
    - benchmark/report.py
    - tests/test_vcc_report.py
  modified: []

key-decisions:
  - "Plain dict (not dataclass) for the report shape -- downstream plans only access by key; trivially serializable for checkpoint display and agent tool output"
  - "ValueError raised for BOTH predictor_metrics AND baseline_metrics being None/empty/incomplete (not just baseline) -- a report missing the predictor's own scores is equally broken"
  - "DEFAULT_QC_PROVENANCE_NOTE exported as module constant so tests import and assert exact text rather than hardcoding the string in test files"

patterns-established:
  - "run_full_benchmark() is the Plan 05-06 entrypoint: store.save(name, adata) then run_full_benchmark(name, target_genes, store_root=...) -- no additional wiring"
  - "to_markdown(report) produces predictor vs baseline table with QC provenance trailing line -- checkpoint display pattern"

requirements-completed: ["VCC-03"]

# Metrics
duration: 3min
completed: "2026-09-09"
---

# Phase 5 Plan 05: build_benchmark_report / run_full_benchmark Summary

**VCC-03 closed: build_benchmark_report() structurally refuses None/empty/incomplete baseline (or predictor) metrics via ValueError, and run_full_benchmark() gives Plan 05-06 a single top-level entrypoint (name + target_genes in, complete report out)**

## Performance

- **Duration:** ~3 min
- **Started:** 2026-09-09T22:29:08Z
- **Completed:** 2026-09-09T22:31:54Z
- **Tasks:** 2 (Task 1 TDD with RED+GREEN commits; Task 2 covered by same test file)
- **Files modified:** 2

## Accomplishments

- `build_benchmark_report()` enforces baseline presence at construction time -- raises ValueError for `None`, `{}`, or any missing key in either `predictor_metrics` or `baseline_metrics`
- `run_full_benchmark()` composes `run_vcc_eval()` + `build_benchmark_report()` into one call, giving Plan 05-06 exactly one function to call against the real VCC dataset
- `to_markdown(report)` renders a predictor vs baseline metric table with the QC provenance note as a trailing line, ready for Plan 05-06's checkpoint display
- 15 new tests all pass; full test suite 136 passed (zero regressions)

## Task Commits

Each task was committed atomically:

1. **Task 1 RED: failing tests for build_benchmark_report and run_full_benchmark** - `5fc8cfe` (test)
2. **Task 1+2 GREEN: implement build_benchmark_report and run_full_benchmark** - `e516463` (feat)

**Plan metadata:** (this commit)

_Note: TDD task 1 produced two commits (RED test file then GREEN implementation). Task 2 tests were included in the same test file and passed with the GREEN implementation._

## Files Created/Modified

- `benchmark/report.py` - build_benchmark_report(), run_full_benchmark(), to_markdown(), _validate_metrics(), DEFAULT_QC_PROVENANCE_NOTE
- `tests/test_vcc_report.py` - 15 tests covering both tasks (validation errors, full metric coverage, end-to-end via perturbation_adata fixture)

## Decisions Made

- **Plain dict for report shape**: downstream plans only access by key; trivially JSON-serializable for checkpoint display and agent tool output, no import dependency at call sites
- **ValueError on predictor_metrics too**: a report missing the predictor's own scores is equally broken as a missing baseline -- symmetric validation prevents subtly broken reports
- **DEFAULT_QC_PROVENANCE_NOTE exported**: test files import the constant rather than hardcoding the string, ensuring tests and implementation stay in sync

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- VCC-03 is closed. Plan 05-06 (real VCC dataset smoke test) can call `run_full_benchmark("vcc-dataset", target_genes, store_root=...)` after saving the downloaded dataset to a DatasetStore.
- `to_markdown(report)` is ready for the Plan 05-06 checkpoint display to the user.
- No blockers. Plan 05-06 is the final plan in Phase 5 and ends in a `checkpoint:human-verify` task (one-time authenticated download of the VCC public dataset).

---
*Phase: 05-perturbation-response-tool-vcc-benchmark-harness*
*Completed: 2026-09-09*
