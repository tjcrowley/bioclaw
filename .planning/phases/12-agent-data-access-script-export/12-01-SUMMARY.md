---
phase: 12-agent-data-access-script-export
plan: 01
subsystem: testing
tags: [pytest, anndata, cellxgene-census, tdd, scaffolding, ingest]

# Dependency graph
requires:
  - phase: 11-quick-wins-history-replay-h5ad-upload-csv-export
    provides: EXPORT-01 CSV export, h5ad upload, session history replay — all fast-suite green
  - phase: 12-agent-data-access-script-export
    provides: 12-RESEARCH.md and 12-VALIDATION.md defining DATA-01/EXPORT-02 contracts
provides:
  - "census_data pytest marker registered in pyproject.toml"
  - "ingest/census.py: ingest_from_anndata() + format_census_source() shared helpers"
  - "tests/test_census_tool.py: 4 DATA-01 unit tests (red Nyquist scaffold for plan 02)"
  - "tests/test_census_smoke.py: 1 network round-trip test gated by census_data marker"
  - "tests/test_webapp_script_export.py: 6 EXPORT-02 unit tests (red Nyquist scaffold for plan 03)"
affects:
  - 12-02-census-fetch-tool
  - 12-03-script-export

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "ingest_from_anndata(): in-memory ingest helper mirrors ingest_10x() without loaders.load()"
    - "format_census_source(): pure provenance-string formatter for census source_path round-trip"
    - "Nyquist scaffold: test files reference future symbols (plan 02/03) — red at this wave, green after implementation"
    - "census_data marker gates network tests same way vcc_data gates VCC tests"

key-files:
  created:
    - ingest/census.py
    - tests/test_census_tool.py
    - tests/test_census_smoke.py
    - tests/test_webapp_script_export.py
  modified:
    - pyproject.toml

key-decisions:
  - "ingest_from_anndata() accepts pre-built AnnData (no loaders.load()) — keeps census AnnData in memory, avoids write+read round-trip"
  - "format_census_source() is a pure string function — no I/O, no imports of cellxgene_census — so ingest/census.py can be tested without network"
  - "census_data marker follows the vcc_data marker pattern: marker in pyproject.toml + skipif(not env-var) in smoke test"
  - "test_census_tool.py patches ingest.census._census_fetch_blocking (plan 02 creates it) so unit tests isolate the tool handler from the network call"

patterns-established:
  - "Pattern: Nyquist Wave 0 scaffold — create test files that reference future symbols; they collect but fail at runtime until implementation lands"
  - "Pattern: census provenance string 'cellxgene-census:{version}:{organism}:{filter}' parsed by EXPORT-02 script generator to reconstruct the fetch call"

requirements-completed: [DATA-01, EXPORT-02]

# Metrics
duration: 8min
completed: 2026-09-16
---

# Phase 12 Plan 01: Agent Data Access + Script Export — Wave 0 Scaffold Summary

**census_data marker, ingest/census.py shared helpers (ingest_from_anndata + format_census_source), and three Nyquist red-scaffold test files establishing DATA-01 and EXPORT-02 contracts for plans 02 and 03**

## Performance

- **Duration:** ~8 min
- **Started:** 2026-09-16T (prior session, commit 061a1b1)
- **Completed:** 2026-09-16
- **Tasks:** 3 (Task 1 from prior session, Tasks 2-3 this session)
- **Files modified:** 5

## Accomplishments

- `ingest/census.py` delivers `ingest_from_anndata()` (in-memory pipeline mirror of `ingest_10x`) and `format_census_source()` (pure provenance string builder) — both callable, no network, no cellxgene_census import
- `census_data` pytest marker registered; fast suite collects 252 tests with 0 unknown-marker warnings
- Three test files (4 + 1 + 6 = 11 tests) collect cleanly; all unit tests are red (implementation in plans 02/03) — correct Nyquist state

## Task Commits

1. **Task 1: Register census_data marker + implement ingest/census.py helper** - `061a1b1` (feat)
2. **Task 2: Write DATA-01 test scaffolds (mocked unit + network smoke)** - `490b3f6` (test)
3. **Task 3: Write EXPORT-02 script export test scaffold** - `f29b4cd` (test)

## Files Created/Modified

- `pyproject.toml` - Added `census_data` marker to `[tool.pytest.ini_options]`
- `ingest/census.py` - `format_census_source()` + `ingest_from_anndata()` in-memory pipeline helper
- `tests/test_census_tool.py` - 4 DATA-01 unit tests: census_fetch_returns_dataset_id, runs_in_thread, fetched_dataset_loadable, tool_registered
- `tests/test_census_smoke.py` - 1 network round-trip test gated by `@pytest.mark.census_data` + `CENSUS_DATA` env var
- `tests/test_webapp_script_export.py` - 6 EXPORT-02 tests: export_script_returns_py, contains_qc_thresholds, contains_random_state, census_source, requires_auth, no_analysis_graceful

## Decisions Made

- `ingest_from_anndata()` accepts a pre-built AnnData and skips `loaders.load()` — keeps the already-materialized census AnnData in memory, avoids a write+read round-trip, matches "call through the pipeline, not around it" per 12-RESEARCH.md Open Question 2
- `format_census_source()` is a pure string function with zero imports of `cellxgene_census` so the module is census-source-agnostic and fully testable without network
- `test_census_tool.py` patches `ingest.census._census_fetch_blocking` (plan 02 creates this closure) so unit tests isolate the tool handler logic from the blocking network call
- `test_census_smoke.py` requires both the marker (`-m census_data`) AND the env var (`CENSUS_DATA=1`) so it can never accidentally run in CI

## Deviations from Plan

None — plan executed exactly as written. Task 1 was already committed in a prior session; Tasks 2 and 3 were created fresh this session.

## Issues Encountered

None. The prior interrupted run had already committed Task 1 (`ingest/census.py` and the marker). This session picked up at Task 2 cleanly.

## User Setup Required

None — no external service configuration required.

## Next Phase Readiness

- Plans 02 (census-fetch tool) and 03 (script export) can now run in parallel — both have their test contracts defined and the shared `ingest/census.py` helper they depend on
- `fetch_census_dataset_tool` (plan 02) must: add `_census_fetch_blocking` to `ingest/census.py`, implement the async tool handler using `asyncio.to_thread`, register it in `agent/server.py`
- `GET /api/export/script` (plan 03) must: read `adata.uns['qc']['config']` and `adata.uns['analysis']`, parse `source_path` for `cellxgene-census:` prefix, return `text/x-python` with `import scanpy` header

---
*Phase: 12-agent-data-access-script-export*
*Completed: 2026-09-16*
