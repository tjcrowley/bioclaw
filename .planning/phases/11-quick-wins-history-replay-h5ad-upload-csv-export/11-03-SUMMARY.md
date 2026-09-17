---
phase: 11-quick-wins-history-replay-h5ad-upload-csv-export
plan: "03"
subsystem: api
tags: [csv, export, zipfile, streamingresponse, fastapi, frontend]

# Dependency graph
requires:
  - phase: 11-quick-wins-history-replay-h5ad-upload-csv-export
    provides: DatasetStore.load() and agent_tools.STORE_ROOT used by export endpoint
provides:
  - GET /api/export/csv endpoint returning ZIP of clusters.csv + de_genes.csv + annotations.csv
  - exportCsv() JS function in api.js using anchor-click browser download pattern
  - Download button (#download-btn) in main panel, shown when dataset is active in session
affects:
  - phase-12 (any future export enhancements)
  - frontend-ux (download flow)

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "ZIP streaming via io.BytesIO + zipfile.ZipFile + StreamingResponse"
    - "Anchor-click browser download (avoids fetch() for file responses)"
    - "Graceful placeholder rows for missing optional AnnData uns keys"

key-files:
  created:
    - tests/test_webapp_export.py
  modified:
    - webapp/backend/main.py
    - webapp/frontend/api.js
    - webapp/frontend/index.html
    - webapp/frontend/main.js
    - webapp/frontend/chat.js
    - webapp/frontend/style.css

key-decisions:
  - "annotation/pipeline.py annotate() does not persist results back to the store; annotations.csv always shows placeholder for current datasets — correct behavior documented in code comment"
  - "DatasetStore.save() takes (name, adata) not (adata, name) — plan fixture had args reversed; fixed in test implementation"
  - "Used anchor-click pattern (not fetch()) for CSV download so session cookie is sent automatically on browser navigation"
  - "__onAskResponse hook wired in chat.js composer submit to refresh session.recent_datasets after each ask and show download button"

patterns-established:
  - "Placeholder row pattern: gracefully handle missing AnnData obs/uns keys with a descriptive single-row placeholder rather than 500 error"
  - "Browser file download: create anchor element, set href, click(), remove — never use fetch() for file downloads"

requirements-completed:
  - EXPORT-01

# Metrics
duration: 5min
completed: 2026-09-17
---

# Phase 11 Plan 03: CSV Export Summary

**GET /api/export/csv endpoint returning ZIP (clusters.csv + de_genes.csv + annotations.csv) with anchor-click browser download button and full auth/error handling**

## Performance

- **Duration:** ~5 min
- **Started:** 2026-09-17T00:54:45Z
- **Completed:** 2026-09-17T00:59:30Z
- **Tasks:** 3 of 3 complete
- **Files modified:** 6

## Accomplishments
- Implemented `GET /api/export/csv` FastAPI endpoint using StreamingResponse + zipfile
- ZIP always contains clusters.csv, de_genes.csv, annotations.csv — with graceful placeholder rows when leiden/DE/annotation data is absent
- Auth gate (401), 404 for unknown datasets, 422 for malformed dataset_id format
- Added `exportCsv()` JS function to api.js using the anchor-click browser download pattern
- Added hidden `#download-btn` to index.html panel toolbar, shown after upload or after ask responses that associate a dataset
- 9 unit tests covering all edge cases (ZIP contents, missing leiden, missing DE, auth, 404, 422, Content-Disposition)
- All 231 fast-tier tests pass

## Task Commits

Each task was committed atomically:

1. **Task 1: RED tests for GET /api/export/csv** - `bc48751` (test)
2. **Task 1: Implement GET /api/export/csv endpoint** - `b4bcd8e` (feat)
3. **Task 2: Add export download button to frontend** - `626024b` (feat)
4. **Task 3: Human verify — ZIP export confirmed in browser** - `74784e3` (docs)

**Plan metadata:** `74784e3` (docs: human-verify checkpoint approved)

## Files Created/Modified
- `tests/test_webapp_export.py` - 9 unit tests covering ZIP contents, missing data, auth, 404, 422
- `webapp/backend/main.py` - Added GET /api/export/csv endpoint + imports (io, zipfile, pandas, scanpy, StreamingResponse, DatasetStore)
- `webapp/frontend/api.js` - Added exportCsv() function using anchor-click pattern
- `webapp/frontend/index.html` - Added #panel-toolbar with hidden #download-btn before chat-thread
- `webapp/frontend/main.js` - Added window.__currentDatasetId tracking, download button wiring, __onAskResponse hook
- `webapp/frontend/chat.js` - Call window.__onAskResponse after ask responses to refresh recent_datasets
- `webapp/frontend/style.css` - Added .panel-toolbar and .toolbar-btn styles

## Decisions Made
- `annotation/pipeline.py` annotate() does not persist results back to the store. `annotations.csv` will always show a placeholder row for current datasets. This is correct behavior and is documented in a code comment. No change to annotation pipeline was needed.
- `DatasetStore.save()` signature is `save(name, adata, ...)` — the plan's fixture example had args reversed. Fixed in test implementation.
- Used anchor-click pattern (not fetch()) for the CSV download so the session cookie is sent automatically on browser navigation — consistent with RESEARCH.md Pitfall 5 guidance.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed reversed arguments in test fixture**
- **Found during:** Task 1 RED phase
- **Issue:** Plan's test fixture example called `store.save(adata, "test-dataset")` but `DatasetStore.save()` signature is `save(name, adata, ...)` — name-first, adata-second
- **Fix:** Corrected argument order in test fixture to `store.save("test-dataset", adata)` and added return value capture `version = store.save(...)`
- **Files modified:** tests/test_webapp_export.py
- **Verification:** Tests ran correctly after fix
- **Committed in:** bc48751 (Task 1 test commit)

---

**Total deviations:** 1 auto-fixed (Rule 1 - bug in plan example code)
**Impact on plan:** Fix was required for tests to run. No scope creep.

## Issues Encountered
None beyond the fixture argument order fix above.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- CSV export backend and frontend are complete; browser verification passed (Task 3 checkpoint approved)
- Phase 11 Plan 03 is fully complete
- EXPORT-01 requirement is satisfied
- All three Phase 11 plans (HIST-01, DATA-02, EXPORT-01) are complete — Phase 11 is done

---
*Phase: 11-quick-wins-history-replay-h5ad-upload-csv-export*
*Completed: 2026-09-17*
