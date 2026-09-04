---
phase: 01-ingest-qc-pipeline
plan: 01
subsystem: testing
tags: [uv, pytest, scanpy, anndata, h5py, scipy, fixtures]

# Dependency graph
requires: []
provides:
  - "pyproject.toml: Python 3.12+ project with scanpy[scrublet]>=1.12, anndata>=0.13, pytest>=8 (uv-managed .venv, uv.lock committed)"
  - "tests/conftest.py: tiny_mtx_dir, tiny_h5_file, synthetic_adata pytest fixtures — network-free synthetic 10x-format inputs"
  - "tests/test_fixtures.py: smoke tests proving all three fixtures are structurally valid"
affects: [01-02-loaders-and-contract, 01-03-qc, 01-04-store, 01-05-pipeline-integration]

# Tech tracking
tech-stack:
  added: [uv, scanpy, anndata, pytest, h5py, scipy]
  patterns:
    - "Synthetic 10x fixtures built with fixed RNG seeds (np.random.default_rng) for reproducibility, no network calls, no bundled binary test data"
    - "10x MEX .mtx.gz written via scipy.io.mmwrite to a temp .mtx path then gzip-recompressed (mmwrite has no native gzip target support)"
    - "10x H5 built directly with h5py per CellRanger v3 layout (/matrix/{data,indices,indptr,shape,barcodes}, /matrix/features/{id,name,feature_type,genome})"

key-files:
  created:
    - pyproject.toml
    - uv.lock
    - tests/conftest.py
    - tests/test_fixtures.py
  modified: []

key-decisions:
  - "Committed uv.lock alongside pyproject.toml for reproducible dependency resolution across future plan executions"
  - "Used fixed gene indices/names (MT-CO1, MT-ND1, DUPGENE x2, ZEROGENE) across tiny_mtx_dir and tiny_h5_file so both fixtures independently exercise the same edge cases (MT genes, duplicate symbol, all-zero row/col) without needing to be byte-identical"
  - "synthetic_adata boosts 3 MT- genes on a random 10-cell subset (not all cells) so pct_counts_mt has real variance for threshold-filtering tests in Plan 01-03"

patterns-established:
  - "Pattern: All Phase 1 tests consume tiny_mtx_dir / tiny_h5_file / synthetic_adata fixtures by name from tests/conftest.py — no per-plan fixture duplication"

requirements-completed: []

# Metrics
duration: 13min
completed: 2026-09-03
---

# Phase 1 Plan 01: Test Infrastructure & Synthetic 10x Fixtures Summary

**uv-managed Python 3.12+ project (scanpy/anndata/pytest) plus three synthetic, network-free 10x-format pytest fixtures (MEX directory, HDF5 file, in-memory AnnData) that every later Phase 1 plan consumes by name.**

## Performance

- **Duration:** 13 min
- **Started:** 2026-09-03T20:25:00-07:00
- **Completed:** 2026-09-03T20:38:50-07:00
- **Tasks:** 2 completed
- **Files modified:** 4 (pyproject.toml, uv.lock, tests/conftest.py, tests/test_fixtures.py)

## Accomplishments
- Working `uv sync`-managed Python 3.12+ environment with scanpy[scrublet], anndata, and pytest installed and importable
- Three synthetic 10x-format fixtures (`tiny_mtx_dir`, `tiny_h5_file`, `synthetic_adata`) implemented exactly to the plan's interface contract, each with MT- genes, an all-zero cell, and an all-zero gene
- `tiny_mtx_dir` additionally carries a gene symbol duplicated across two Ensembl IDs, proven to resolve correctly via `make_unique=True`
- Full smoke-test coverage proving all three fixtures parse/behave as intended before any downstream loader/QC/store code is written
- `uv run pytest tests/ -q` runs clean with zero collection errors and no network access

## Task Commits

Each task was committed atomically:

1. **Task 1: Initialize Python project and install dependencies via uv** - `885d944` (chore)
2. **Task 2: Create synthetic 10x fixtures and prove they are structurally valid** - `ee2f428` (test, RED) → `ff6856e` (feat, GREEN)

**Plan metadata:** (this commit)

_Task 2 followed TDD: RED (failing "fixture not found" errors) → GREEN (fixtures implemented, all 3 tests pass). No refactor commit needed — implementation was clean on first pass._

## Files Created/Modified
- `pyproject.toml` - Project metadata, Python 3.12+ requirement, scanpy/anndata/pytest deps, pytest testpaths config
- `uv.lock` - Locked dependency resolution (committed for reproducibility)
- `tests/conftest.py` - `tiny_mtx_dir`, `tiny_h5_file`, `synthetic_adata` pytest fixtures
- `tests/test_fixtures.py` - Smoke tests proving structural validity of all three fixtures

## Decisions Made
- Committed `uv.lock` (not just `pyproject.toml`) so future plan executions and CI reproduce the exact same dependency versions.
- Used shared, hand-picked gene naming (`MT-CO1`, `MT-ND1`, `DUPGENE` x2, `ZEROGENE`) across `tiny_mtx_dir`/`tiny_h5_file` so both independently exercise identical edge cases without requiring byte-identical construction (plan explicitly allows "same shape is fine but not required to be identical").
- `synthetic_adata` boosts MT- gene counts on only a 10-cell subset (of 50) rather than uniformly, so `pct_counts_mt` has genuine spread for Plan 01-03's threshold-filtering tests.

## Deviations from Plan

None - plan executed exactly as written. All fixture names, shapes, and structural characteristics match the `<interfaces>` block verbatim.

## Issues Encountered

`uv sync` downloaded a managed Python 3.12 interpreter automatically (system Python was 3.9.6) — this was anticipated in the plan's Task 1 instructions and required no intervention.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- `tests/conftest.py` fixtures (`tiny_mtx_dir`, `tiny_h5_file`, `synthetic_adata`) are ready for Plan 01-02 (`ingest/loaders.py`), Plan 01-03 (`ingest/qc.py`), and Plan 01-04 (`ingest/store.py`) to consume directly by fixture name.
- No blockers for Wave 1 plans.

---
*Phase: 01-ingest-qc-pipeline*
*Completed: 2026-09-03*

## Self-Check: PASSED

All created files verified present on disk (pyproject.toml, uv.lock, tests/conftest.py, tests/test_fixtures.py, this SUMMARY.md). All task commit hashes (885d944, ee2f428, ff6856e) verified present in git log.
