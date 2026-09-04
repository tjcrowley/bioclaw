---
phase: 02-analysis-tool-layer
plan: 02
subsystem: analysis
tags: [scanpy, anndata, pca, hvg, preprocessing, dataclasses]

# Dependency graph
requires:
  - phase: 02-analysis-tool-layer (02-01)
    provides: igraph dependency, structured_adata fixture, analysis/summary.py bounded dataclasses (PreprocessSummary)
provides:
  - "analysis/preprocess.py::preprocess(adata, **config) -> (AnnData, PreprocessSummary)"
affects: [02-05 (analysis/pipeline.py orchestration entrypoint)]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Tool-boundary copy semantics: preprocess() copies adata first, never mutates caller's input"
    - "Size-guard clamping against *actual* post-selection dimensions (n_hvg), not just requested/raw n_vars, since HVG selection can itself return fewer genes than requested on small/edge-case inputs"
    - "PreprocessSummary.config logs post-clamping resolved values, not the caller's raw request, mirroring ingest/qc.py's QCConfig audit pattern"

key-files:
  created:
    - analysis/preprocess.py
    - tests/test_preprocess.py
  modified: []

key-decisions:
  - "Clamped n_pcs against the actual n_hvg count (post-HVG-selection), not the raw/requested n_top_genes or adata.n_vars -- sklearn's PCA arpack solver requires n_components strictly less than min(n_samples, n_features), and HVG selection can silently return fewer genes than requested on small fixtures (e.g. 19 genes selected when 20 were requested, due to too few genes with nonzero dispersion), which the plan's literal n_vars-1 clamp did not account for"

patterns-established:
  - "Two-stage size clamping: clamp n_top_genes against adata.n_vars before HVG selection, then re-derive the PCA n_comps clamp from the actual post-selection HVG count rather than the pre-selection request"

requirements-completed: ["ANLYS-01"]

# Metrics
duration: 8min
completed: 2026-09-04
---

# Phase 2 Plan 02: Preprocess (normalize/HVG/PCA) Summary

**`analysis/preprocess.py::preprocess()` runs normalize_total -> log1p -> highly_variable_genes -> pca deterministically, never mutates its input, and returns a bounded `PreprocessSummary` alongside the transformed AnnData.**

## Performance

- **Duration:** 8 min
- **Started:** 2026-09-04T20:21:00Z
- **Completed:** 2026-09-04T20:23:32Z
- **Tasks:** 2
- **Files modified:** 2

## Accomplishments
- `preprocess()` enforces the exact ANLYS-01 call order (normalize -> log1p -> HVG -> PCA), preventing the silent-wrong-HVG-selection pitfall from running HVG on non-log data
- Copy-on-entry semantics verified by test: caller's original AnnData is byte-for-byte unchanged after the call
- Deterministic given a fixed `random_state`, verified by comparing `X_pca` arrays across two calls
- Small-fixture size guard (20 genes x 50 cells) does not raise, via two-stage clamping (n_top_genes against `n_vars`, then n_pcs against the *actual* post-selection `n_hvg`)
- `PreprocessSummary` construction is complete and structurally bounded (no field scales with `n_cells`/`n_genes_total`)

## Task Commits

Each task was committed atomically (combined into a single implementation commit since Task 2 is a direct, small extension of Task 1's function signature -- both are covered by the same test file's distinct test functions):

1. **Task 1+2: preprocess() with size guards, copy semantics, and PreprocessSummary** - `4a98e6c` (test, RED) then `bbebb36` (feat, GREEN)

**Plan metadata:** (this commit)

_TDD flow: RED (failing tests) -> GREEN (full implementation covering both tasks' behavior in one pass, since Task 2's `PreprocessSummary` return was cheaper to build alongside Task 1 than to retrofit)._

## Files Created/Modified
- `analysis/preprocess.py` - `preprocess(adata, *, target_sum, n_top_genes, n_pcs, random_state) -> (AnnData, PreprocessSummary)`
- `tests/test_preprocess.py` - 6 tests: pipeline order/HVG/PCA presence, no-mutation, determinism, small-input size guard, summary shape, summary boundedness

## Decisions Made
- **PCA n_comps clamp uses actual n_hvg, not adata.n_vars:** The plan's suggested clamp (`min(n_pcs, adata.n_obs - 1, adata.n_vars - 1)`) failed on the small `synthetic_adata` fixture with `ValueError: n_components=19 must be strictly less than min(n_samples, n_features)=19 with svd_solver='arpack'`. Root cause: `sc.pp.pca` restricts to `adata.var['highly_variable']` automatically once HVG selection has run, so the solver's actual feature count is the *realized* `n_hvg` (which can be smaller than `n_vars` or even smaller than the requested `n_top_genes`, e.g. when too few genes have nonzero dispersion on a small fixture) -- not `adata.n_vars`. Fixed by computing `n_hvg = int(adata.var["highly_variable"].sum())` after the HVG call and clamping `n_pcs` against `n_hvg - 1` instead of `adata.n_vars - 1`. This is a Rule 1 (bug fix) auto-fix, documented below.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] PCA n_comps clamp used actual post-HVG-selection gene count, not adata.n_vars**
- **Found during:** Task 1 (running `test_preprocess_small_input_size_guard` against the small `synthetic_adata` fixture)
- **Issue:** The plan's literal clamp (`min(n_pcs, adata.n_obs - 1, adata.n_vars - 1)`) raised `ValueError` from sklearn's PCA arpack solver: `n_components=19 must be strictly less than min(n_samples, n_features)=19`. HVG selection on this fixture returned only 19 genes (not the requested/clamped 20), because too few genes had nonzero normalized dispersion -- and PCA's `mask_var` auto-restricts to those 19 HVGs as its feature count, not the fixture's full 20 `n_vars`.
- **Fix:** Compute `n_hvg = int(adata.var["highly_variable"].sum())` immediately after the `highly_variable_genes` call, and clamp `n_pcs` against `n_hvg - 1` (not `adata.n_vars - 1`) before calling `sc.pp.pca`.
- **Files modified:** `analysis/preprocess.py`
- **Verification:** `uv run pytest tests/test_preprocess.py -x -q` -- all 6 tests pass, including the small-fixture guard; full suite (`uv run pytest tests/ -q`) still green (37 passed)
- **Committed in:** `bbebb36` (Task 1 implementation commit)

---

**Total deviations:** 1 auto-fixed (1 bug fix)
**Impact on plan:** Necessary correctness fix for the size-guard behavior explicitly required by the plan's `<behavior>` spec; no scope creep, no architectural change.

## Issues Encountered
None beyond the auto-fixed clamping bug above.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- `analysis/preprocess.py::preprocess()` is ready for `analysis/pipeline.py` (Wave 2, plan 02-05) to compose with `analysis/cluster.py` and `analysis/diffexp.py` (running in parallel as plans 02-03/02-04)
- `PreprocessSummary.dataset_id` remains `None` here by design -- Wave 2's orchestration entrypoint is responsible for filling it in once `store.save()` returns a version, per `analysis/summary.py`'s documented contract
- No blockers for downstream Wave 1 plans (02-03, 02-04) or Wave 2 (02-05) from this plan's work

---
*Phase: 02-analysis-tool-layer*
*Completed: 2026-09-04*

## Self-Check: PASSED

- FOUND: analysis/preprocess.py
- FOUND: tests/test_preprocess.py
- FOUND: .planning/phases/02-analysis-tool-layer/02-02-SUMMARY.md
- FOUND: commit 4a98e6c (test: add failing tests)
- FOUND: commit bbebb36 (feat: implement preprocess())
