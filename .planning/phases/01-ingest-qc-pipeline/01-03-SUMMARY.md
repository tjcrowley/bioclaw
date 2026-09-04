---
phase: 01-ingest-qc-pipeline
plan: 03
subsystem: data-pipeline
tags: [scanpy, anndata, scrublet, qc, dataclass]

# Dependency graph
requires:
  - phase: 01-ingest-qc-pipeline (01-01)
    provides: pytest env + synthetic_adata fixture (tests/conftest.py)
provides:
  - "ingest/qc.py: QCConfig dataclass + run(adata, cfg) -> AnnData"
  - "adata.uns['qc'] audit contract (config, n_cells_before/after, removed_by_reason)"
affects: [01-05 (pipeline entrypoint calls qc.run() directly)]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Explicit QCConfig dataclass driving all filtering thresholds, never hard-coded inline"
    - "Per-run audit log written to adata.uns['qc'] with removed_by_reason breakdown"
    - "Scrublet n_prin_comps auto-shrink-on-ValueError loop, so the same code path works on both tiny test fixtures and full-size real datasets"

key-files:
  created: [ingest/qc.py, tests/test_qc.py]
  modified: []

key-decisions:
  - "Filled NaN pct_counts_mt/doublet_score/predicted_doublet with 0/0.0/False for all-zero cells instead of leaving nulls, since the QC-01 contract requires every column non-null for every cell (degenerate cells are expected to be dropped by min_genes filtering downstream, not by producing NaN QC values)"
  - "Scrublet's default n_prin_comps=30 crashes on small inputs (PCA n_components must be < min(n_samples, n_features) after Scrublet's internal HVG selection); added a shrink-and-retry loop rather than a fixed magic number, so it's robust for both this project's small synthetic fixtures and real-scale datasets"

patterns-established:
  - "QCConfig dataclass with typed, documented defaults is the only source of filtering thresholds -- ingest/qc.py::run() never hard-codes a cutoff"

requirements-completed: ["QC-01", "QC-02"]

# Metrics
duration: 4min
completed: 2026-09-04
---

# Phase 1 Plan 3: QC Module (QC-01, QC-02) Summary

**`ingest/qc.py` computes mito%/gene-count/doublet metrics via scanpy + Scrublet and filters by an explicit `QCConfig`, logging a full per-reason removal breakdown to `adata.uns['qc']` on every run.**

## Performance

- **Duration:** 4 min (active implementation; commits 07:48-07:52 local)
- **Started:** 2026-09-04T14:48:15Z
- **Completed:** 2026-09-04T14:52:14Z
- **Tasks:** 2 completed
- **Files modified:** 2 (ingest/qc.py created, tests/test_qc.py created)

## Accomplishments
- `QCConfig` dataclass (`min_genes_per_cell`, `min_cells_per_gene`, `max_pct_mt`, `doublet_action`) is the sole source of QC thresholds -- no hard-coded cutoffs anywhere in `run()`.
- `run(adata, cfg)` computes `pct_counts_mt`, `n_genes_by_counts`, `total_counts`, `doublet_score`, `predicted_doublet` on `.obs` for every cell, non-null, then filters by config and writes `adata.uns['qc']` with resolved config (as a plain dict), `n_cells_before`, `n_cells_after`, and `removed_by_reason` (`low_gene_count`, `high_mito`, `doublet`).
- Implausibly strict configs (e.g. `min_genes_per_cell=100000`) produce a valid, explicit 0-`n_obs` result instead of crashing -- verified by a dedicated test.
- Doublets default to flagged, not removed (`doublet_action="flag"`); `doublet_action="filter"` removes them and records the count under `removed_by_reason["doublet"]`.

## Task Commits

Each task was committed atomically (TDD: test -> feat):

1. **Test: failing tests for QC metrics and config-driven filtering** - `c4366da` (test)
2. **Task 1: QC metric computation (QC-01)** - `8a695fe` (feat)
3. **Task 2: QCConfig, filtering, and logged audit trail (QC-02)** - `ed184fe` (feat)

**Plan metadata:** (this commit)

_Note: both tasks' tests were written together in one RED commit up front (`test_qc.py` covers all five `must_haves`/behaviors from both tasks); Task 1's GREEN commit implemented only the metrics half and was verified against `test_qc_metrics_present` alone before Task 2's GREEN commit added filtering/config/audit logging and turned the full file green._

## Files Created/Modified
- `ingest/qc.py` - `QCConfig` dataclass + `run(adata, cfg) -> AnnData`; metrics via `sc.pp.calculate_qc_metrics` + Scrublet, filtering via `sc.pp.filter_cells`/`filter_genes`/boolean mito+doublet masks, audit log to `adata.uns['qc']`
- `tests/test_qc.py` - 5 tests: metrics presence/non-null, config logging, threshold-changes-filtering, doublet filter action, impossibly-strict-config-returns-empty-result

## Decisions Made
- All-zero cells (present by design in the shared `synthetic_adata` fixture) produce `NaN` from both `calculate_qc_metrics` (0/0 mito%) and Scrublet (no expression signal for kNN/PCA). Rather than leave nulls in columns the QC-01 contract requires to be always-populated, these are explicitly filled: `pct_counts_mt` -> 0.0, `doublet_score` -> 0.0, `predicted_doublet` -> `False`. Such cells are expected to be removed by `min_genes_per_cell` filtering in practice, not by NaN propagation.
- Scrublet's `n_prin_comps=30` default fails on small AnnData objects because the PCA solver bound (`min(n_samples, n_features)`) depends on Scrublet's own internal HVG selection, not directly on `adata.n_vars`/`n_obs`. Implemented a shrink-and-retry loop (halve `n_prin_comps` on `ValueError`, floor at 2) instead of a fixed smaller constant, so the same code path is correct for both this project's tiny synthetic fixtures and full-size real datasets without needing dataset-size-aware branching.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Scrublet crashes with default n_prin_comps on small AnnData inputs**
- **Found during:** Task 1 (QC metric computation)
- **Issue:** `sc.pp.scrublet(adata)` with the default `n_prin_comps=30` raised `ValueError: n_components=30 must be between 1 and min(n_samples, n_features)=12` when run against the shared 20-gene x 50-cell `synthetic_adata` fixture, because Scrublet's internal PCA step operates on a smaller HVG-selected feature space than `adata.n_vars`.
- **Fix:** Added `_run_scrublet()` helper with a shrink-and-retry loop: start at `min(30, n_vars, n_obs)`, halve on `ValueError`, floor at 2.
- **Files modified:** `ingest/qc.py`
- **Verification:** `test_qc_metrics_present` passes against the synthetic fixture.
- **Committed in:** `8a695fe` (Task 1 commit)

**2. [Rule 1 - Bug] NaN QC values for all-zero cells violate the "always populated" QC-01 contract**
- **Found during:** Task 1 (QC metric computation)
- **Issue:** The fixture's deliberately all-zero cell (`total_counts == 0`) produced `NaN` for `pct_counts_mt` (0/0 division) and for `doublet_score`/`predicted_doublet` (no signal for Scrublet's kNN/PCA step), failing the `.notna().all()` assertion required by `<behavior>`.
- **Fix:** Filled `pct_counts_mt` with 0.0, `doublet_score` with 0.0, `predicted_doublet` with `False` (explicitly cast back to `bool` dtype after `fillna`, since `fillna` on a bool Series otherwise silently promotes to `object` dtype).
- **Files modified:** `ingest/qc.py`
- **Verification:** `test_qc_metrics_present` passes.
- **Committed in:** `8a695fe` (Task 1 commit)

**3. [Rule 1 - Bug] `~adata.obs["predicted_doublet"]` performed bitwise, not logical, negation after `fillna`**
- **Found during:** Task 2 (filtering/audit trail), while implementing `doublet_action="filter"`
- **Issue:** `fillna(False)` on the `predicted_doublet` boolean column silently promoted it to `object` dtype; `~` on an `object`-dtype Series of Python `bool`s performs bitwise inversion (`-1`/`-2`) rather than logical negation, and AnnData's boolean-mask indexing then raised `KeyError` on those out-of-range values.
- **Fix:** Explicit `.astype(bool)` after `.fillna(False)` to restore a true boolean dtype before any downstream `~` usage.
- **Files modified:** `ingest/qc.py`
- **Verification:** `test_doublet_filter_action` and full `tests/test_qc.py -x -q` pass.
- **Committed in:** `ed184fe` (Task 2 commit)

---

**Total deviations:** 3 auto-fixed (all Rule 1 - bugs surfaced by exercising the real synthetic fixture, not scope creep)
**Impact on plan:** All three fixes were required for the plan's own stated behaviors (non-null QC columns, working doublet filtering) to actually hold on the shared test fixture; no architectural changes, no new dependencies.

## Issues Encountered
None beyond the auto-fixed items above.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- `ingest/qc.py::run(adata, cfg) -> AnnData` is ready for Plan 01-05's pipeline entrypoint to call directly, per the `<interfaces>` contract this plan implemented exactly.
- Ran in parallel with Plan 01-04 (`ingest/store.py`); touched only `ingest/qc.py`/`tests/test_qc.py` as scoped, no conflicts observed (`git status` clean, no rebase needed at completion).
- Full suite (`uv run pytest tests/ -q`) green: 17 tests passing across loaders, contract, fixtures, and QC.

---
*Phase: 01-ingest-qc-pipeline*
*Completed: 2026-09-04*

## Self-Check: PASSED

- FOUND: ingest/qc.py
- FOUND: tests/test_qc.py
- FOUND: .planning/phases/01-ingest-qc-pipeline/01-03-SUMMARY.md
- FOUND commit: c4366da
- FOUND commit: 8a695fe
- FOUND commit: ed184fe
