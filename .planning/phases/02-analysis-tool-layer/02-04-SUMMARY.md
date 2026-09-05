---
phase: 02-analysis-tool-layer
plan: 04
subsystem: analysis
tags: [scanpy, wilcoxon, differential-expression, anndata]

# Dependency graph
requires:
  - phase: 02-analysis-tool-layer
    provides: "analysis/summary.py DESummary/DEGeneResult dataclasses and tests/conftest.py structured_adata fixture (Plan 02-01)"
provides:
  - "analysis/diffexp.py::differential_expression(adata, groupby, group1, group2=None, **config) -> (AnnData, DESummary)"
  - "Generic Wilcoxon rank-sum DE building block for Wave 2 pipeline.py"
affects: [02-05-pipeline]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "sc.tl.rank_genes_groups(groupby, groups=[group1], reference=group2 or 'rest', method='wilcoxon', tie_correct=True, pts=True, corr_method='benjamini-hochberg') -> sc.get.rank_genes_groups_df extraction, never hand-parsed uns arrays"
    - "DESummary.top_genes capped via sort_values('pvals_adj').head(n_genes); n_significant computed over the full unsliced result before truncation"

key-files:
  created: []
  modified: [analysis/diffexp.py, tests/test_diffexp.py]

key-decisions:
  - "Task 2 (DESummary construction) was interrupted mid-execution by a subagent session-limit cutoff after Task 1 committed; resumed directly in the main session rather than re-spawning an executor, since only one function body needed extending and tests were already RED-committed"

patterns-established:
  - "Bounded DE summary construction (top_genes capped at n_genes, n_significant/n_genes_tested as scalar aggregates over the full ranking) mirrors PreprocessSummary/ClusterSummary's O(1)/O(top_n) invariant from analysis/summary.py"

requirements-completed: ["ANLYS-03"]

# Metrics
duration: ~10min (interrupted, resumed same day)
completed: 2026-09-04
---

# Phase 02 Plan 04: Differential Expression Summary

**`analysis/diffexp.py::differential_expression()` runs generic Wilcoxon rank-sum DE over any categorical `.obs` column and returns a bounded `DESummary`**

## Performance

- **Duration:** ~10 min total (Task 1 committed by subagent executor before hitting a session-limit cutoff; Task 2 completed directly in the orchestrating session)
- **Completed:** 2026-09-04
- **Tasks:** 2
- **Files modified:** 2

## Accomplishments
- `differential_expression()` runs `sc.tl.rank_genes_groups` with `method="wilcoxon"`, `tie_correct=True`, `pts=True`, `corr_method="benjamini-hochberg"`, generic over any `.obs` categorical column (cluster key or condition label)
- Marker-gene recovery verified: population A's known elevated gene block (`GENE00`-`GENE14`) is recovered among top DE hits vs. population B in `structured_adata`
- `group2=None` ("rest") behaves equivalently to explicit `group2="B"` for the two-group fixture
- Returns `(adata, DESummary)`: `top_genes` capped at `n_genes` (default 25) via `sort_values("pvals_adj").head(n_genes)`; `n_genes_tested`/`n_significant` computed over the full unsliced ranking before truncation

## Task Commits

1. **Task 1: differential_expression() core Wilcoxon DE** - `c3960a0` (test, RED), `45afc1e` (feat, GREEN)
2. **Task 2: DESummary/DEGeneResult construction** - `7d7f085` (test extension + feat, GREEN — combined since the interrupted subagent had already left the RED test additions uncommitted; verified RED-would-fail via the prior full-suite run showing `ValueError: too many values to unpack`, then implemented to GREEN)

## Files Created/Modified
- `analysis/diffexp.py` - `differential_expression(adata, groupby, group1, group2=None, *, n_genes=25, tie_correct=True) -> tuple[AnnData, DESummary]`; copies input, runs `rank_genes_groups`, extracts via `rank_genes_groups_df`, builds capped `DESummary`
- `tests/test_diffexp.py` - 8 tests: marker-gene recovery, `group2=None` equivalence, genericity over arbitrary `.obs` column, rank_genes_groups params recorded, non-mutation, bounded-summary shape, top_genes capping, n_significant/n_genes_tested correctness

## Decisions Made
- Resumed Task 2 directly rather than re-spawning a `gsd-executor` subagent, since the prior subagent run had hit a session/rate limit mid-task with Task 1 already cleanly committed and Task 2's tests already written (uncommitted) — re-running from scratch would have duplicated Task 1's work

## Deviations from Plan

None in implementation. Process deviation only: Task 2 execution was interrupted by a subagent session-limit event and completed by the orchestrating session directly instead of the originally-spawned `gsd-executor` agent.

## Issues Encountered

Subagent executing this plan hit a Claude session usage limit mid-Task-2 (after Task 1 was committed, with Task 2's RED test additions written but not yet committed and the implementation not yet extended). Resumed by reading the plan, existing `diffexp.py`, and `summary.py` dataclass contracts directly, then completing the `DESummary` construction to match the already-written test expectations. Full suite (51 tests) green after the fix.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- `analysis/diffexp.py::differential_expression()` is ready for Wave 2's `analysis/pipeline.py` to compose alongside `preprocess()` (02-02) and `cluster()` (02-03)
- All three Wave 1 plans (02-02, 02-03, 02-04) are now complete; Wave 2 (02-05 pipeline.py) can proceed

---
*Phase: 02-analysis-tool-layer*
*Completed: 2026-09-04*

## Self-Check: PASSED

- FOUND: analysis/diffexp.py
- FOUND: tests/test_diffexp.py
- FOUND: .planning/phases/02-analysis-tool-layer/02-04-SUMMARY.md
- FOUND: c3960a0 (test commit, Task 1)
- FOUND: 45afc1e (feat commit, Task 1)
- FOUND: 7d7f085 (feat commit, Task 2)
