---
phase: 05-perturbation-response-tool-vcc-benchmark-harness
plan: 02
subsystem: perturbation
tags: [sklearn, ridge-regression, anndata, numpy, linear-model, perturbation, single-cell]

# Dependency graph
requires:
  - phase: 05-01
    provides: perturbation/summary.py dataclass contracts (PerturbationCall/PerturbationSummary), tests/conftest.py perturbation_adata fixture

provides:
  - LinearAdditivePerturbationModel (fit/predict) -- PERT-01 predictor core with exact known-gene lookup + ridge fallback
  - fit_from_adata() -- AnnData-facing convenience wrapper returning (fitted_model, control_mean)
  - tests/test_perturbation_model.py -- 6 unit tests covering all three predict paths and fixture-based recovery

affects:
  - 05-03 (pipeline composition needs LinearAdditivePerturbationModel and fit_from_adata)
  - 05-04 (eval harness imports model.py)
  - 05-05 (benchmark report imports model.py)

# Tech tracking
tech-stack:
  added: [sklearn.linear_model.Ridge (already in venv via cell-eval), scipy.sparse (existing)]
  patterns:
    - Ridge fallback with single-feature (target gene's own control expression value) per 05-RESEARCH.md Pattern 1
    - Densify-if-sparse X pattern (mirrors annotation/baseline.py precedent)
    - fit() stores gene_names list + gene_index dict for O(1) gene lookup in predict()
    - fit_from_adata() returns (model, control_mean) tuple so Plan 05-03 can call model.predict(control_mean, target_gene) without re-pseudobulking

key-files:
  created:
    - perturbation/model.py
    - tests/test_perturbation_model.py
  modified: []

key-decisions:
  - "Ridge fallback feature is target gene's own control-expression scalar (single-feature Ridge), not all-gene control vector -- per 05-RESEARCH.md Pattern 1's documented design choice for the unseen-gene path"
  - "predict() routing: exact known-shift lookup first, ridge fallback second, KeyError third -- distinct failure mode for genes not in gene_names vs genes in gene_names but unseen at fit time"
  - "fit_from_adata() returns (model, control_mean) tuple because Plan 05-03's pipeline.predict() needs both without repeating pseudobulking"

patterns-established:
  - "Pattern: TDD RED->GREEN both tasks share one commit (tests + implementation) since they target the same two files and GREEN covered all 6 test cases in one pass"
  - "Pattern: atol=0.5 documented tolerance for fixture-based recovery assertions with Poisson-sampled counts; exact lookup path should track group mean to floating-point precision but generous threshold documents intent"

requirements-completed: ["PERT-01"]

# Metrics
duration: 2min
completed: 2026-09-09
---

# Phase 5 Plan 02: LinearAdditivePerturbationModel and fit_from_adata Summary

**Control-mean + per-gene additive shift predictor with Ridge fallback for unseen genes, plus AnnData convenience wrapper -- PERT-01 predictor core for Plans 05-03/04/05**

## Performance

- **Duration:** 2 min
- **Started:** 2026-09-09T15:40:20Z
- **Completed:** 2026-09-09T15:42:47Z
- **Tasks:** 2 (Task 1: model fit/predict; Task 2: fit_from_adata + fixture tests)
- **Files modified:** 2

## Accomplishments

- Implemented LinearAdditivePerturbationModel with exact lookup for fit-time perturbation genes, Ridge regression fallback for genes in gene_names but not seen during fit, and clear KeyError for genes absent from gene_names entirely
- Implemented fit_from_adata() that pseudobulks an AnnData (densifies sparse X, groups by obs[target_gene_col]) and returns (fitted_model, control_mean) with zero caller-side pseudobulking required
- 6 tests: 3 hand-built (exact recovery, non-crashing fallback, KeyError) + 3 fixture-based (control_mean match, GENE00-GENE04 recovery within atol=0.5, shape checks); full suite 105 passed

## Task Commits

Each task was committed atomically:

1. **Task 1+2: LinearAdditivePerturbationModel + fit_from_adata (combined)** - `3f48c24` (feat)

(Both TDD tasks targeted the same two files and GREEN covered all 6 test cases in one implementation pass; committed together as one atomic unit.)

**Plan metadata:** (committed with docs commit below)

## Files Created/Modified

- `/Users/darren/.openclaw/workspace/bioclaw/perturbation/model.py` - LinearAdditivePerturbationModel class + fit_from_adata(); replaces 05-01 stub with real logic
- `/Users/darren/.openclaw/workspace/bioclaw/tests/test_perturbation_model.py` - 6 tests: hand-built unit tests (no fixture) + perturbation_adata fixture-based recovery tests

## Decisions Made

- Ridge fallback uses a single-feature matrix (target gene's own control expression scalar), not all-gene control vector. This matches 05-RESEARCH.md Pattern 1's "simplest defensible choice" and is sufficient since ridge's extrapolation only needs a scalar handle on the gene's baseline expression.
- fit_from_adata() returns (model, control_mean) tuple -- Plan 05-03 needs control_mean alongside the model to call model.predict(control_mean, target_gene), so returning it avoids repeated pseudobulking.
- atol=0.5 for fixture-based recovery tolerance: the exact lookup path (used for GENE00-GENE04 which ARE in pert_means) should track the group mean to floating-point precision; 0.5 is generous documentation of intent, not a meaningful tolerance band.

## Deviations from Plan

None - plan executed exactly as written. The two TDD tasks were merged into a single commit (both targeting the same two files) but all specified behavior and tests were implemented per spec.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Plan 05-03 (pipeline composition: naive_baseline_predict + pipeline.predict() + predict_perturbation_tool wiring) can import LinearAdditivePerturbationModel and fit_from_adata() from perturbation/model.py immediately
- control_mean return from fit_from_adata() is wired to the correct shape (n_vars,) and matches the fixture's observed non-targeting mean exactly

---
*Phase: 05-perturbation-response-tool-vcc-benchmark-harness*
*Completed: 2026-09-09*
