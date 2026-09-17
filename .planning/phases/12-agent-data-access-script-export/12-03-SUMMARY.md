---
phase: 12-agent-data-access-script-export
plan: 03
subsystem: api
tags: [fastapi, scanpy, cellxgene-census, export, reproducibility, vanilla-js]

# Dependency graph
requires:
  - phase: 12-agent-data-access-script-export
    provides: "12-01 Wave 0 scaffold (tests/test_webapp_script_export.py red Nyquist tests, format_census_source() provenance string format)"
provides:
  - "generate_analysis_script() pure string renderer reading adata.uns['qc']/['analysis']"
  - "GET /api/export/script FastAPI endpoint (password-gated, 404/422 handling)"
  - "exportScript() frontend anchor-click download helper"
  - "Export Script toolbar button wired alongside Export CSV"
affects:
  - 12-04 (if any further phase-12 wave)
  - future Docker phase (DOCK-01) — endpoint behavior unaffected by containerization

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Pure f-string script renderer (no template engine) — generate_analysis_script() takes adata + source_path + dataset_id, returns a complete .py string"
    - "Endpoint mirrors export_csv exactly: parse name@version, DatasetStore.load() (KeyError->404), StreamingResponse with Content-Disposition attachment"
    - "Frontend anchor-click download pattern (not fetch) reused for a second export type so the session cookie rides on browser navigation"

key-files:
  created:
    - webapp/backend/export_script.py
  modified:
    - webapp/backend/main.py
    - webapp/frontend/api.js
    - webapp/frontend/main.js
    - webapp/frontend/index.html

key-decisions:
  - "webapp/backend/export_script.py was found pre-existing (untracked, from an earlier interrupted run) and already matched the plan spec exactly — verified against all 6 EXPORT-02 tests rather than rewritten from scratch"
  - "Endpoint resolves source_path via store.list(name) matching the loaded version (falling back to the latest record) since DatasetStore.load() does not itself return provenance metadata"
  - "Export Script button uses the same show/hide helpers as the Export CSV button (_showDownloadBtn/_hideDownloadBtn) so both toolbar buttons always appear/disappear together — no separate state tracking needed"

patterns-established:
  - "Pattern: dual-export toolbar — CSV (zip of tables) and Script (.py) share dataset-active-state visibility logic in _showDownloadBtn/_hideDownloadBtn"

requirements-completed: [EXPORT-02]

# Metrics
duration: ~20min
completed: 2026-09-17
---

# Phase 12 Plan 03: Script Export Summary

**GET /api/export/script renders a self-contained, reproducible scanpy .py script from adata.uns['qc']/['analysis'] and dataset provenance, branching on census-fetch vs sc.read_h5ad source, with a frontend Export Script button using the anchor-click download pattern**

## Performance

- **Duration:** ~20 min
- **Started:** 2026-09-17T13:40:00Z (approx)
- **Completed:** 2026-09-17T14:03:52Z
- **Tasks:** 2
- **Files modified:** 5 (1 created, 4 modified)

## Accomplishments

- `generate_analysis_script()` renders a complete, self-contained scanpy script (no bioclaw imports) with: comment header (dataset_id + UTC timestamp), QC block (min_genes/min_cells/max_pct_mt/scrublet from `adata.uns['qc']['config']`), a source-branching fetch block (`cellxgene_census.open_soma` + `get_anndata` for census-sourced datasets, `sc.read_h5ad` for file-sourced), and an analysis block reproducing every `AnalysisConfig` parameter including `random_state` — or a graceful "# No analysis was run" comment when `adata.uns.get('analysis')` is `None`
- `GET /api/export/script` added to `webapp/backend/main.py`, mirroring the `export_csv` pattern exactly: password-gated via `Depends(require_password)`, parses `name@version`, 404 on unknown dataset (`KeyError`), 422 on malformed `dataset_id`, looks up `source_path` from `store.list(name)` matched to the loaded version (or latest), returns `text/x-python` with `Content-Disposition: attachment`
- All 6 EXPORT-02 tests in `tests/test_webapp_script_export.py` pass: returns .py, QC thresholds present, random_state present, census-source branch (open_soma not read_h5ad), auth gate (401 without cookie), no-analysis graceful degradation
- Frontend: `exportScript()` added to `api.js` (identical anchor-click pattern to `exportCsv`), `export-script-btn` added to the toolbar in `index.html`, `main.js` imports `exportScript` and un-hides/hides the new button together with `download-btn` via the existing `_showDownloadBtn`/`_hideDownloadBtn` helpers, plus a dedicated click handler

## Task Commits

Each task was committed atomically:

1. **Task 1: generate_analysis_script() renderer + /api/export/script endpoint** - `1b1b4fe` (feat)
2. **Task 2: Frontend exportScript() helper + Export Script button** - `90440c2` (feat)

**Plan metadata:** (this commit, pending)

## Files Created/Modified

- `webapp/backend/export_script.py` - Pure `generate_analysis_script(adata, source_path, dataset_id) -> str` renderer; found pre-existing from an interrupted run and verified to already match spec, then committed as part of Task 1
- `webapp/backend/main.py` - Added `GET /api/export/script` endpoint; imports `generate_analysis_script` from `webapp.backend.export_script`
- `webapp/frontend/api.js` - Added `exportScript(datasetId)` mirroring `exportCsv`
- `webapp/frontend/index.html` - Added `export-script-btn` toolbar button next to `download-btn`
- `webapp/frontend/main.js` - Imports `exportScript`; `_showDownloadBtn`/`_hideDownloadBtn` now toggle both buttons; added click handler for `export-script-btn`

## Decisions Made

- Verified rather than rewrote `webapp/backend/export_script.py`: it was present as an untracked 152-line file from an earlier interrupted run. Read it in full and compared line-by-line against the plan's spec (comment header, source branching, QC block with scrublet handling, analysis block with all `AnalysisConfig` fields, graceful no-analysis path) — it matched exactly, so it was left as-is and validated by running the actual test suite rather than assumed correct.
- The endpoint needs `source_path` provenance, which `DatasetStore.load()` does not return (it only returns the `AnnData`). Used `store.list(name)` to fetch the registry record and match it to the loaded version (falling back to the latest record when no explicit version was requested), consistent with the `DatasetStore.list()` contract read from `ingest/store.py`.
- Reused the existing `_showDownloadBtn`/`_hideDownloadBtn` helper functions rather than adding a parallel pair for the new button — keeps CSV and Script export buttons permanently paired in visibility with a single code path, matching the plan's instruction to "un-hide both buttons together."

## Deviations from Plan

None - plan executed exactly as written. The pre-existing untracked `export_script.py` file matched spec, so no rewrite was needed; this is not a deviation, just an efficient discovery during Task 1.

## Issues Encountered

The full fast test suite (`uv run pytest tests/ -m "not live_llm and not bio_fm_smoke and not vcc_data and not census_data" -q`) shows 3 failures in `tests/test_census_tool.py` (`test_census_fetch_returns_dataset_id`, `test_census_fetch_runs_in_thread`, `test_fetched_dataset_loadable`) when run as part of the full suite, but all 4 tests in that file pass when run in isolation. Root cause traced to that file's own `asyncio.get_event_loop().run_until_complete()` pattern (flagged by its own `DeprecationWarning: There is no current event loop`), which is fragile to test ordering elsewhere in the suite. Confirmed this is unrelated to 12-03's changes: `--ignore=tests/test_census_tool.py` gives 248 passed / 0 failed. `tests/test_census_tool.py`, `agent/tools.py`, and `ingest/census.py` are all owned by the concurrently-executing plan 12-02, which 12-03 was explicitly instructed not to touch. Logged in `.planning/phases/12-agent-data-access-script-export/deferred-items.md` for 12-02's own verification pass to catch.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- EXPORT-02 fully satisfied: reproducible script export endpoint + frontend button both working and tested
- Phase 12 now has both DATA-01 (in progress via concurrent plan 12-02) and EXPORT-02 (this plan) implemented against the shared 12-01 Wave 0 scaffold
- Once plan 12-02 completes and stabilizes `agent/tools.py`/`ingest/census.py`, the full fast suite should be re-run to confirm the `test_census_tool.py` event-loop flakiness is resolved (see deferred-items.md)

---
*Phase: 12-agent-data-access-script-export*
*Completed: 2026-09-17*

## Self-Check: PASSED

- FOUND: .planning/phases/12-agent-data-access-script-export/12-03-SUMMARY.md
- FOUND: commit 1b1b4fe (Task 1)
- FOUND: commit 90440c2 (Task 2)
- FOUND: all 5 files_modified paths exist on disk
- FOUND: /api/export/script string in webapp/backend/main.py
- FOUND: export/script string in webapp/frontend/api.js
- FOUND: export-script-btn string in webapp/frontend/index.html
- FOUND: exportScript string in webapp/frontend/main.js
