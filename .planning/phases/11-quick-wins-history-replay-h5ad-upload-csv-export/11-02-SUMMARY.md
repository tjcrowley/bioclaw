---
phase: 11-quick-wins-history-replay-h5ad-upload-csv-export
plan: "02"
subsystem: testing
tags: [scanpy, anndata, h5ad, pytest, integration-test, upload]

# Dependency graph
requires:
  - phase: 06-03
    provides: analyzable_mtx_dir fixture (300 genes x 60 cells, survives default QC)
  - phase: 07-02
    provides: uploads.py with _SINGLE_FILE_SUFFIXES=(".h5", ".h5ad") and ingest_10x()
  - phase: 01-02
    provides: ingest/loaders.py sc.read_h5ad() routing for .h5ad files
provides:
  - tiny_h5ad_file pytest fixture in tests/conftest.py
  - test_upload_h5ad_returns_dataset_id integration test in tests/test_webapp_upload.py
  - test_upload_h5ad_rejected_without_password auth test in tests/test_webapp_upload.py
affects: [phase-12, phase-13, phase-14]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Convert analyzable_mtx_dir to .h5ad via ingest.loaders.load() for fixture consistency"
    - "Fixture chaining: tiny_h5ad_file depends on analyzable_mtx_dir to share data shape"

key-files:
  created: []
  modified:
    - tests/conftest.py
    - tests/test_fixtures.py
    - tests/test_webapp_upload.py

key-decisions:
  - "Use ingest.loaders.load() (not scanpy directly) to build tiny_h5ad_file fixture — guarantees AnnData structure matches what ingest_10x() produces"
  - "No backend code changes required — uploads.py and loaders.py already handle .h5ad end-to-end"

patterns-established:
  - "Fixture reuse pattern: convert existing analyzable_mtx_dir to different formats rather than duplicating data construction"

requirements-completed: [DATA-02]

# Metrics
duration: 3min
completed: 2026-09-17
---

# Phase 11 Plan 02: H5ad Upload Test Coverage Summary

**End-to-end .h5ad upload path proved by automated tests: tiny_h5ad_file fixture (300 genes x 60 cells) and two integration tests against POST /api/upload**

## Performance

- **Duration:** 3 min
- **Started:** 2026-09-17T00:54:29Z
- **Completed:** 2026-09-17T00:57:00Z
- **Tasks:** 2
- **Files modified:** 3

## Accomplishments
- Added `tiny_h5ad_file` fixture to `tests/conftest.py` — builds a 300-gene x 60-cell .h5ad by running `analyzable_mtx_dir` through `ingest.loaders.load()`, guaranteeing the file survives QC (min_genes_per_cell=200)
- Added `test_upload_h5ad_returns_dataset_id` to `tests/test_webapp_upload.py` — proves the full stack path: HTTP upload → uploads.py staging → ingest_10x() → loaders.py sc.read_h5ad() → DatasetStore.save() → UploadResponse
- Added `test_upload_h5ad_rejected_without_password` confirming .h5ad upload is gated by same auth as all other upload types
- Confirmed no backend code changes needed: _SINGLE_FILE_SUFFIXES already includes `.h5ad`, loaders.py already routes to sc.read_h5ad()

## Task Commits

Each task was committed atomically:

1. **Task 1: Add tiny_h5ad_file fixture to conftest.py** - `7d5d118` (test)
2. **Task 2: Add h5ad upload integration tests** - `034c46f` (test)

**Plan metadata:** TBD (docs: complete plan)

_Note: Both tasks followed TDD (RED test written first, then GREEN implementation)_

## Files Created/Modified
- `tests/conftest.py` - Added `tiny_h5ad_file` fixture (chains on `analyzable_mtx_dir`)
- `tests/test_fixtures.py` - Added `test_tiny_h5ad_file_is_readable` smoke test
- `tests/test_webapp_upload.py` - Added `test_upload_h5ad_returns_dataset_id` and `test_upload_h5ad_rejected_without_password`

## Decisions Made
- Used `ingest.loaders.load()` (not scanpy directly) to construct the `tiny_h5ad_file` fixture — ensures AnnData structure precisely matches what the production ingest pipeline produces, not just "a valid .h5ad"
- No backend changes: confirmed by running all 12 upload tests and the 222-test fast-tier suite with no new failures

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
- One pre-existing failure exists in `tests/test_webapp_export.py::test_export_csv_returns_zip` (404) — this is the CSV export feature targeted by plan 11-03, not related to this plan.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- DATA-02 requirement is now fully evidenced with automated tests
- `tiny_h5ad_file` fixture is available for any future plan needing a valid .h5ad input
- Full fast-tier suite (222 tests) passes; ready to proceed to plan 11-03 (CSV export)

---
*Phase: 11-quick-wins-history-replay-h5ad-upload-csv-export*
*Completed: 2026-09-17*
