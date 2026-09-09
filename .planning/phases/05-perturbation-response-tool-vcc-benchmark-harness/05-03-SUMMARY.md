---
phase: 05-perturbation-response-tool-vcc-benchmark-harness
plan: "03"
subsystem: perturbation
tags: [cell_eval, perturbation, baseline, pipeline, mcp-tool, agent]

# Dependency graph
requires:
  - phase: 05-01
    provides: PerturbationCall/PerturbationSummary dataclass contracts, perturbation/ skeleton
  - phase: 05-02
    provides: LinearAdditivePerturbationModel, fit_from_adata
provides:
  - naive_baseline_predict() wrapping cell_eval.build_base_mean_adata (PERT-02 closed)
  - perturbation/pipeline.py::predict() composing model + baseline unconditionally (PERT-01/02 closed)
  - predict_perturbation_tool in agent/tools.py + agent/server.py (4-tool MCP server)
affects: [05-04, 05-05, 05-06]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "naive_baseline_predict delegates entirely to cell_eval.build_base_mean_adata with allow_discrete=True for raw count AnnDatas"
    - "pipeline.predict() calls naive_baseline_predict() UNCONDITIONALLY before returning (same code-order as annotate()'s unconditional baseline_annotate())"
    - "pandas Series must be .values before scipy sparse boolean indexing"
    - "DatasetStore.save() path used in perturbation tests (no ingest/QC needed when AnnData already has target_gene labels)"

key-files:
  created:
    - perturbation/baseline.py
    - perturbation/pipeline.py
    - tests/test_perturbation_baseline.py
  modified:
    - agent/tools.py
    - agent/server.py
    - tests/test_agent_tools.py

key-decisions:
  - "cell_eval.build_base_mean_adata returns a GLOBAL MEAN of all perturbation group means (not per-target-gene mean); plan's test spec wording 'close to GENE00-labeled cells mean' was inaccurate -- tests assert against actual build_base_mean_adata output"
  - "allow_discrete=True required for raw count AnnDatas; without it build_base_mean_adata applies normalize_total+log1p and produces inconsistent results"
  - "naive_baseline_predict validates target_gene presence BEFORE calling cell_eval to produce a clean ValueError rather than a cryptic downstream error"
  - "pandas boolean Series must be converted to numpy .values before scipy sparse matrix indexing (scipy rejects Series objects as indices)"

patterns-established:
  - "perturbation/pipeline.py::predict() mirrors annotation/pipeline.py::annotate() exactly: store.load -> dataset_id -> model call -> unconditional baseline call -> summary -> asdict"
  - "predict_perturbation_tool mirrors annotate_cell_type_tool shape: @tool with name/target_gene dict schema, try/except to is_error, JSON text block"

requirements-completed: [PERT-02, PERT-01]

# Metrics
duration: 6min
completed: 2026-09-09
---

# Phase 5 Plan 03: Perturbation Pipeline + Agent Tool Summary

**naive_baseline_predict() wrapping cell_eval.build_base_mean_adata + pipeline.predict() composing model+baseline unconditionally + predict_perturbation_tool as the 4th MCP tool**

## Performance

- **Duration:** ~6 min
- **Started:** 2026-09-09T15:47:22Z
- **Completed:** 2026-09-09T15:52:39Z
- **Tasks:** 2
- **Files modified:** 6

## Accomplishments

- PERT-02 closed: `naive_baseline_predict()` delegates entirely to Arc Institute's `cell_eval.build_base_mean_adata` -- no hand-rolled averaging; real API introspected and divergence from research sketch documented
- PERT-01 fully closed (composition point): `pipeline.predict()` always returns both model_call and baseline_call in a single call; no code path omits the baseline
- Phase 3/4 agent tool pattern extended: `predict_perturbation_tool` is the 4th MCP tool in `bioclaw_server`, registered alongside ingest/analyze/annotate

## Task Commits

1. **Task 1: naive_baseline_predict() (TDD)** - `9c4ce32` (feat)
2. **Task 2: pipeline.predict() + predict_perturbation_tool** - `006b54e` (feat)

**Plan metadata:** (see final commit below)

## Files Created/Modified

- `perturbation/baseline.py` - naive_baseline_predict() wrapping cell_eval.build_base_mean_adata; real API documented with divergence from research sketch
- `perturbation/pipeline.py` - predict() composing model+baseline; unconditional baseline call mirrors annotate()'s unconditional baseline_annotate()
- `agent/tools.py` - predict_perturbation_tool added matching annotate_cell_type_tool shape
- `agent/server.py` - predict_perturbation_tool registered as 4th tool in bioclaw_server
- `tests/test_perturbation_baseline.py` - 3 tests: happy-path PerturbationCall shape+value, ValueError for unknown gene, pipeline composition (both calls asserted)
- `tests/test_agent_tools.py` - 4 new tests: round-trip, unknown-name error, schema, 4-tool server check

## Decisions Made

- `cell_eval.build_base_mean_adata` returns a GLOBAL mean of all perturbation group means, NOT a per-target-gene mean; tests assert against actual `build_base_mean_adata` output rather than per-gene cell means (the plan's loose spec wording)
- `allow_discrete=True` passed to `build_base_mean_adata` for raw count AnnDatas; the function's `_convert_to_normlog` heuristic would otherwise apply normalize_total+log1p producing inaccurate results for integer fixtures
- Validation of target_gene presence done BEFORE calling cell_eval, so callers get a clear `ValueError` (not a cryptic cell_eval internal error)
- pandas Series `.values` required before scipy sparse boolean mask indexing -- scipy rejects pandas Series objects as index types

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] pandas Series rejected by scipy sparse boolean indexing**
- **Found during:** Task 1 (naive_baseline_predict implementation)
- **Issue:** `baseline_adata.X[mask]` where `mask` is a pandas boolean Series raises AttributeError ("'Series' object has no attribute 'nonzero'"); scipy sparse indexing requires numpy bool arrays
- **Fix:** Added `.values` conversion: `(baseline_adata.obs[pert_col] == target_gene).values` in both implementation and test reference
- **Files modified:** perturbation/baseline.py, tests/test_perturbation_baseline.py
- **Verification:** tests pass
- **Committed in:** 9c4ce32

**2. [Rule 1 - Bug / Research spec divergence] build_base_mean_adata returns global mean, not per-gene mean**
- **Found during:** Task 1 API introspection (by design -- plan explicitly required introspection before implementation)
- **Issue:** Plan spec said "close to the independently-computed mean of GENE00-labeled cells" but `build_base_mean_adata` computes the mean of ALL perturbation group means (a global value identical for every pert label); the per-GENE00 mean diverges significantly in a 5-perturbation fixture
- **Fix:** Tests assert against actual `build_base_mean_adata` output (correct ground truth); divergence documented in module docstring and test module header
- **Files modified:** perturbation/baseline.py (docstring), tests/test_perturbation_baseline.py (docstring + assertion)
- **Committed in:** 9c4ce32

---

**Total deviations:** 2 auto-fixed (1 scipy API bug, 1 research-spec divergence discovered by required introspection)
**Impact on plan:** Both auto-fixes essential for correctness. No scope creep.

## Issues Encountered

None beyond the two auto-fixed deviations above.

## Next Phase Readiness

- Plan 05-04 (`compute_vcc_metrics`/`run_vcc_eval`) can import `from perturbation.pipeline import predict` and `from perturbation.baseline import naive_baseline_predict` directly
- Plan 05-05 (`build_benchmark_report`/`run_full_benchmark`) has full model + baseline available
- 111 tests fully green

---
*Phase: 05-perturbation-response-tool-vcc-benchmark-harness*
*Completed: 2026-09-09*
