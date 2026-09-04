---
phase: 02-analysis-tool-layer
plan: 03
subsystem: analysis
tags: [scanpy, leiden, igraph, umap, clustering, anndata]

# Dependency graph
requires:
  - phase: 02-analysis-tool-layer
    provides: "analysis/summary.py ClusterSummary dataclass and tests/conftest.py structured_adata fixture (Plan 02-01)"
provides:
  - "analysis/cluster.py::cluster(adata, **config) -> (AnnData, ClusterSummary)"
  - "Leiden clustering (flavor=igraph, directed=False) + UMAP embedding building block for Wave 2 pipeline.py"
affects: [02-05-pipeline]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "sc.pp.neighbors -> sc.tl.leiden(flavor='igraph', directed=False, n_iterations=2) -> sc.tl.umap, mirroring analysis/preprocess.py's copy-then-mutate contract"
    - "n_neighbors clamped to min(n_neighbors, adata.n_obs - 1) for small-input size guard, same pattern as preprocess.py's HVG/PCA clamping"
    - "Determinism contract scoped to Leiden labels only, not UMAP coordinates (umap-learn upstream nondeterminism)"

key-files:
  created: [analysis/cluster.py, tests/test_cluster.py]
  modified: []

key-decisions:
  - "flavor='igraph' always paired with explicit directed=False and n_iterations=2 per scanpy's official recommendation, never left to defaults, to avoid the Pitfall 2 ValueError regression"
  - "Test PCA setup done via raw sc.pp calls (normalize_total/log1p/pca) directly in tests/test_cluster.py, not via analysis.preprocess, keeping 02-03 fully independent of the parallel 02-02 plan per the plan's interface note"

patterns-established:
  - "Bounded-summary construction pattern (cluster_sizes as dict[str,int] via value_counts().to_dict(), never a per-cell array) reused verbatim from preprocess.py's PreprocessSummary construction"

requirements-completed: ["ANLYS-02"]

# Metrics
duration: ~5min
completed: 2026-09-04
---

# Phase 02 Plan 03: Leiden Clustering + UMAP Summary

**`analysis/cluster.py::cluster()` runs neighbors -> Leiden (igraph flavor, directed=False) -> UMAP with size guards, returning a bounded `ClusterSummary`**

## Performance

- **Duration:** ~5 min
- **Started:** 2026-09-04T20:25:00Z (approx)
- **Completed:** 2026-09-04T20:31:00Z
- **Tasks:** 2 (combined into one TDD RED/GREEN cycle since both were implemented together in the single `cluster()` function)
- **Files modified:** 2

## Accomplishments
- `cluster()` builds a neighbor graph, runs Leiden clustering via scanpy's `igraph` flavor with `directed=False` always explicit, and computes a 2D UMAP embedding
- Small-input size guard: `n_neighbors` clamped to `min(n_neighbors, adata.n_obs - 1)`, verified against Phase 1's 50-cell `synthetic_adata` fixture
- Leiden cluster-label determinism verified (list equality across two runs with the same `random_state`) without asserting UMAP coordinate exactness, per Pitfall 5
- Returns a bounded `ClusterSummary` (`cluster_sizes` is `O(n_clusters)`, never `O(n_cells)`)

## Task Commits

Both plan tasks were implemented together in a single TDD cycle since the `ClusterSummary` construction (Task 2) is a natural extension of the same function body as Task 1's clustering mechanics, and the test file was written once covering both behaviors:

1. **Task 1 + Task 2: cluster() neighbors/Leiden/UMAP + ClusterSummary** - `8d4d25e` (test, RED), `fa7d9ee` (feat, GREEN)

**Plan metadata:** (this commit, docs: complete plan)

_Note: All 6 tests in tests/test_cluster.py passed on first implementation attempt — no separate refactor commit needed._

## Files Created/Modified
- `analysis/cluster.py` - `cluster(adata, *, resolution=1.0, n_neighbors=15, n_pcs=None, random_state=0) -> tuple[AnnData, ClusterSummary]`; copies input, clamps `n_neighbors`, runs `sc.pp.neighbors` -> `sc.tl.leiden(flavor="igraph", directed=False, n_iterations=2)` -> `sc.tl.umap`, builds `ClusterSummary` from `value_counts()`
- `tests/test_cluster.py` - 6 tests: multi-cluster + UMAP shape, directed=False regression guard, Leiden determinism, small-input size guard, bounded-summary field correctness, summary O(n_clusters) bound check

## Decisions Made
- Implemented Task 1 and Task 2 as a single combined TDD cycle (one test file, one implementation commit for GREEN) rather than two separate RED/GREEN pairs, since the plan's own `<action>` for Task 1 says "Return the mutated adata only (summary construction is Task 2)" but the interfaces and behavior specs for both tasks are tightly coupled in one function body — splitting into two mechanical implementation passes would have required either a throwaway Task 1 return-type or two full test-suite rewrites. All behavior from both tasks' `<behavior>` blocks is covered by the 6 tests written before any implementation, satisfying TDD RED before GREEN.
- Test PCA setup uses raw `sc.pp.normalize_total`/`sc.pp.log1p`/`sc.pp.pca` calls in a local `_pca()` helper inside `tests/test_cluster.py`, not `analysis.preprocess`, per the plan's explicit interface note keeping 02-03 independent of the parallel 02-02 plan

## Deviations from Plan

None - plan executed exactly as written. `flavor="igraph"` is always called with `directed=False` and `n_iterations=2` exactly as specified in `02-RESEARCH.md` Pattern 2.

## Issues Encountered

None. All 6 tests passed on the first implementation attempt (no debug iteration needed). Full existing test suite (43 tests across ingest/QC/store/preprocess/cluster) remained green after this plan's changes.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- `analysis/cluster.py::cluster()` is ready for Wave 2's `analysis/pipeline.py` to compose alongside `preprocess()` and `differential_expression()` (02-04, running in parallel)
- No blockers. This plan only touched `analysis/cluster.py` and `tests/test_cluster.py`, avoiding any file overlap with the concurrently-executing 02-04 plan (`analysis/diffexp.py`)

---
*Phase: 02-analysis-tool-layer*
*Completed: 2026-09-04*

## Self-Check: PASSED

- FOUND: analysis/cluster.py
- FOUND: tests/test_cluster.py
- FOUND: .planning/phases/02-analysis-tool-layer/02-03-SUMMARY.md
- FOUND: 8d4d25e (test commit)
- FOUND: fa7d9ee (feat commit)
