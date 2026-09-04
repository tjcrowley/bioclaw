---
phase: 01-ingest-qc-pipeline
plan: 04
subsystem: database
tags: [sqlite, anndata, h5ad, storage, versioning]

# Dependency graph
requires:
  - phase: 01-ingest-qc-pipeline
    provides: "tests/conftest.py synthetic_adata fixture (Plan 01-01)"
provides:
  - "ingest/store.py::DatasetStore -- filesystem + SQLite versioned dataset registry"
  - "save(name, adata, source_path=, qc_config=) -> version int, auto-incrementing per name"
  - "load(name, version=None, backed=None) -> AnnData, KeyError on missing name/version"
  - "list(name=None) -> list[dict] of registry records, qc_config deserialized"
affects: ["01-05 (pipeline glue calls DatasetStore directly)", "phase 2+ (agent/analysis reference datasets by name)"]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Filesystem + SQLite registry: one .h5ad file per (name, version) under {root}/{name}/v{N}.h5ad, indexed by a datasets table in {root}/registry.sqlite"
    - "CREATE TABLE IF NOT EXISTS on every __init__ -- idempotent, no separate migration step needed at this scale"

key-files:
  created: [ingest/store.py, tests/test_store.py]
  modified: []

key-decisions:
  - "Hand-rolled filesystem+SQLite registry (per 01-RESEARCH.md build-vs-buy) instead of adopting LaminDB -- zero new dependencies, trivially testable, narrow enough to swap backends later"
  - "Version numbering: MAX(version) for name, defaulting to 0, so first save is version 1; versions never overwritten, only incremented"

patterns-established:
  - "DatasetStore(root=...) is the single entry point later phases use to save/load named datasets -- no direct .h5ad path handling outside this module"

requirements-completed: ["INGEST-03"]

# Metrics
duration: 2min
completed: 2026-09-04
---

# Phase 01 Plan 04: Versioned Dataset Store Summary

**Filesystem + SQLite `DatasetStore` (save/load/list) for named, auto-versioned AnnData datasets, backed by stdlib `sqlite3` with zero new dependencies.**

## Performance

- **Duration:** 2 min (07:56:19 - 07:57:33 PDT)
- **Started:** 2026-09-04T14:56:00Z
- **Completed:** 2026-09-04T14:57:33Z
- **Tasks:** 2 completed
- **Files modified:** 2 (both created)

## Accomplishments

- `DatasetStore.save()` writes an AnnData to `{root}/{name}/v{N}.h5ad` and records name/version/path/created_at/source_path/qc_config in a SQLite `datasets` table, auto-incrementing version per name starting at 1.
- `DatasetStore.load()` fetches the latest or a specific version by name, round-tripping `.X` values exactly through `.h5ad` write/read; raises `KeyError` for an unknown name or version.
- `DatasetStore.list()` returns registry records (as dicts, `qc_config` deserialized from JSON back into a dict) filtered by name or across all names, ordered by name then version; returns an empty list (not an error) for an unknown name.

## Task Commits

Each task was committed atomically (TDD: test -> feat):

1. **Task 1: Save/load roundtrip and versioning**
   - `465efff` (test) - failing tests for roundtrip, versioning, missing-name KeyError, and list metadata roundtrip (all test cases written up front)
   - `e6ab573` (feat) - `DatasetStore.save()`/`load()` implementation; verified against Task 1's three tests before `list()` was added
2. **Task 2: Registry listing and metadata query**
   - `a3d9b60` (feat) - `DatasetStore.list()` implementation; full `tests/test_store.py` (7 tests) green

**Plan metadata:** (this commit) `docs(01-04): complete versioned dataset store plan`

_Note: all test cases for both tasks were written in a single RED commit (`465efff`) since they share one test module; `save`/`load` and `list` were then implemented and verified in two separate GREEN commits matching the plan's task boundaries._

## Files Created/Modified

- `ingest/store.py` - `DatasetStore` class: `__init__(root)`, `save()`, `load()`, `list()`; stdlib `sqlite3` registry, `adata.write_h5ad`/`anndata.read_h5ad` for storage
- `tests/test_store.py` - 7 tests: roundtrip, versioning (increment not overwrite), missing-name `KeyError`, list ordering, list-all, list-missing-name-empty, list metadata roundtrip (`source_path`, `qc_config`)

## Decisions Made

- Registry table created via `CREATE TABLE IF NOT EXISTS` on every `DatasetStore.__init__` rather than a separate migration/setup step -- sufficient for this scale and avoids a migrations framework dependency.
- `list()` deserializes `qc_config` back into a dict (not left as a raw JSON string) so callers get the same shape they passed to `save()`.

## Deviations from Plan

None - plan executed exactly as written. `ingest/store.py` and `tests/test_store.py` were the only files touched, matching the plan's `files_modified`.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required. Tests use `tmp_path`, not the repo's real `data/` directory; no `data/` directory was created in the repo by this plan.

## Next Phase Readiness

- `DatasetStore` is ready for Plan 01-05 (pipeline glue) to call directly: `save(name, adata, source_path=..., qc_config=...)` after loaders + QC, `load(name)` / `list(name)` for downstream phases (agent, analysis) to reference datasets by name.
- Full test suite (`uv run pytest tests/ -q`) passes: 24 passed, no regressions in loaders/QC/contract tests.

---
*Phase: 01-ingest-qc-pipeline*
*Completed: 2026-09-04*

## Self-Check: PASSED

- FOUND: ingest/store.py
- FOUND: tests/test_store.py
- FOUND: .planning/phases/01-ingest-qc-pipeline/01-04-SUMMARY.md
- FOUND: commit 465efff (test)
- FOUND: commit e6ab573 (feat: save/load)
- FOUND: commit a3d9b60 (feat: list)
