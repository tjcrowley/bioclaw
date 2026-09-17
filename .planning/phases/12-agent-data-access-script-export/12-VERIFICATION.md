---
phase: 12-agent-data-access-script-export
verified: 2026-09-17T00:00:00Z
status: passed
score: 9/9 must-haves verified
---

# Phase 12: Agent Data Access + Script Export Verification Report

**Phase Goal:** The agent can fetch real public single-cell datasets from cellxgene-census on demand without a file upload, and researchers can export any session's analysis as a self-contained scanpy script that reproduces the exact analysis run.
**Verified:** 2026-09-17
**Status:** passed
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
| --- | --- | --- | --- |
| 1 | A researcher can ask the agent for a dataset by organism + tissue/assay filter and receive an ingested dataset handle fetched from cellxgene-census, not an uploaded file. | ✓ VERIFIED | `ingest/census.py::fetch_census_dataset` orchestrates fetch->ingest; `agent/tools.py::fetch_census_dataset_tool` registered as MCP tool; `tests/test_census_tool.py::test_census_fetch_returns_dataset_id` and `test_fetched_dataset_loadable` pass. |
| 2 | The census fetch runs inside `asyncio.to_thread()` so the event loop is not blocked. | ✓ VERIFIED | `ingest/census.py` line 222: `await asyncio.to_thread(_census_fetch_blocking, ...)`, with the entire `open_soma`+`get_anndata` call inside the closure (Pitfall 1 compliance). `test_census_fetch_runs_in_thread` passes. |
| 3 | The census query (version, organism, obs_value_filter) is persisted as source_path for reproduction. | ✓ VERIFIED | `format_census_source()` builds `cellxgene-census:{version}:{organism}:{filter}`, passed to `ingest_from_anndata(..., source_path=source)` -> `DatasetStore.save`. |
| 4 | `fetch_census_dataset` is registered in `bioclaw_server` alongside the four existing tools. | ✓ VERIFIED | `agent/server.py` imports `fetch_census_dataset_tool` and appends it to `tools=[...]`; `test_tool_registered` passes. |
| 5 | A researcher can request a scanpy script export for a dataset and receive a self-contained `.py` file. | ✓ VERIFIED | `GET /api/export/script` in `webapp/backend/main.py` returns `StreamingResponse` with `media_type="text/x-python"`; `test_export_script_returns_py` passes. |
| 6 | The generated script reproduces QC thresholds, analysis parameters, and random seed from `adata.uns`, not guessed. | ✓ VERIFIED | `generate_analysis_script()` reads `adata.uns['qc']['config']` and `adata.uns['analysis']` (including `random_state`); `test_script_contains_qc_thresholds` and `test_script_contains_random_state` pass. |
| 7 | For census-sourced datasets the script fetches from cellxgene-census; for file-sourced datasets it reads the `.h5ad` path. | ✓ VERIFIED | Branch on `source_path.startswith("cellxgene-census:")` emits `cellxgene_census.open_soma`/`get_anndata`; else `sc.read_h5ad(...)`. `test_script_census_source` passes. |
| 8 | The script export endpoint is rejected without the shared password. | ✓ VERIFIED | `dependencies=[Depends(require_password)]` on the route; `test_script_export_requires_auth` (401 without cookie) passes. |
| 9 | A dataset with no analysis produces a graceful script with a comment, not a 500/KeyError. | ✓ VERIFIED | `an is None` branch emits `"# No analysis was run..."` comment, no exception; `test_script_no_analysis_graceful` passes. |

**Score:** 9/9 truths verified

### Required Artifacts

| Artifact | Expected | Status | Details |
| --- | --- | --- | --- |
| `pyproject.toml` | `census_data` pytest marker registered | ✓ VERIFIED | Line 33: `"census_data: requires real network access to cellxgene-census S3; excluded from fast/CI runs"`. No unknown-marker warnings in collection. |
| `ingest/census.py` | `ingest_from_anndata`, `format_census_source`, `_census_fetch_blocking`, `fetch_census_dataset` | ✓ VERIFIED | All four present, 240 lines, fully substantive (mirrors `ingest_10x`, correct thread-closure pattern). |
| `tests/test_census_tool.py` | DATA-01 unit tests (mocked) | ✓ VERIFIED | 4 tests, all pass. |
| `tests/test_census_smoke.py` | DATA-01 network round-trip, gated | ✓ VERIFIED | 1 test, skipped without `CENSUS_DATA=1` env var, correctly gated by `census_data` marker + skipif. |
| `tests/test_webapp_script_export.py` | EXPORT-02 unit tests | ✓ VERIFIED | 6 named tests, all pass. |
| `agent/tools.py` | `fetch_census_dataset_tool` `@tool` handler | ✓ VERIFIED | Imports `fetch_census_dataset`, defines async handler with matching try/except contract. |
| `agent/server.py` | Tool registered in `bioclaw_server` | ✓ VERIFIED | `fetch_census_dataset_tool` imported and appended to `tools=[...]`. |
| `webapp/backend/export_script.py` | `generate_analysis_script()` pure renderer | ✓ VERIFIED | 153 lines, no bioclaw imports in generated script, handles both source branches and no-analysis case. |
| `webapp/backend/main.py` | `GET /api/export/script` endpoint | ✓ VERIFIED | Password-gated, parses `name@version`, calls `generate_analysis_script`. |
| `webapp/frontend/api.js` | `exportScript()` anchor-click helper | ✓ VERIFIED | Mirrors `exportCsv` exactly, hits `/api/export/script`. |
| `webapp/frontend/index.html` | `export-script-btn` toolbar button | ✓ VERIFIED | Present, `hidden` by default. |
| `webapp/frontend/main.js` | Button wiring | ✓ VERIFIED | Imports `exportScript`, click handler present, un-hidden alongside `download-btn` via shared show/hide helpers. |

### Key Link Verification

| From | To | Via | Status | Details |
| --- | --- | --- | --- | --- |
| `ingest/census.py::ingest_from_anndata` | `ingest.contract`/`ingest.qc`/`ingest.store.DatasetStore` | in-memory pipeline call | ✓ WIRED | `set_counts_layer` -> `qc.run` -> `set_counts_layer` -> `store.save` sequence present. |
| `ingest/census.py::format_census_source` | `DatasetStore.save(source_path=...)` | provenance string | ✓ WIRED | `fetch_census_dataset` builds `source` via `format_census_source` and passes to `ingest_from_anndata(..., source_path=source)`. |
| `agent/tools.py::fetch_census_dataset_tool` | `ingest.census.fetch_census_dataset` | await inside async handler | ✓ WIRED | Handler awaits `fetch_census_dataset(...)` directly. |
| `ingest.census._census_fetch_blocking` | `cellxgene_census.open_soma` + `get_anndata` | `asyncio.to_thread` | ✓ WIRED | Entire with-block inside closure, passed wholesale to `asyncio.to_thread`. |
| `webapp/backend/main.py::export_script` | `webapp.backend.export_script.generate_analysis_script` | call after loading adata | ✓ WIRED | Imported and called with `(adata, source_path, dataset_id)`. |
| `webapp/backend/export_script.py::generate_analysis_script` | `adata.uns['qc']`/`uns.get('analysis')`/source_path | read stored params | ✓ WIRED | All three read and branched on. |
| `webapp/frontend/main.js` | `api.js::exportScript` | click handler | ✓ WIRED | `export-script-btn` click handler calls `exportScript(window.__currentDatasetId)`. |

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
| --- | --- | --- | --- | --- |
| DATA-01 | 12-01 (scaffold), 12-02 (impl) | Researcher can ask the agent to fetch a real public single-cell dataset by tissue/organism/assay from cellxgene-census without uploading a file | ✓ SATISFIED | `fetch_census_dataset_tool` registered, all mocked tests pass, source_path provenance persisted. |
| EXPORT-02 | 12-01 (scaffold), 12-03 (impl) | Researcher can export the current session's analysis as a reproducible scanpy script capturing QC thresholds, analysis parameters, dataset source, and random seeds | ✓ SATISFIED | `GET /api/export/script` implemented, all 6 tests pass, frontend button wired. |

No orphaned requirement IDs found — both DATA-01 and EXPORT-02 map to plans in this phase and REQUIREMENTS.md marks both `[x]` / "Complete" for Phase 12.

### Anti-Patterns Found

None. Scanned `ingest/census.py`, `webapp/backend/export_script.py`, and `agent/tools.py` for TODO/FIXME/placeholder/empty-implementation patterns — no matches. `deferred-items.md` documents a transient test-ordering flakiness (event-loop reuse in `tests/test_census_tool.py`) that was identified during concurrent execution of plans 02/03 and confirmed resolved post-12-02 landing (full fast suite: 252 passed, 0 failed, re-verified independently in this report).

### Human Verification Required

None required for automated pass. Optional (not blocking) real-network verification exists as a phase-gate smoke test:

1. **Real census network fetch**
   **Test:** `CENSUS_DATA=1 uv run pytest tests/test_census_smoke.py -m census_data -x` on a machine with network access to cellxgene-census S3.
   **Expected:** `test_census_real_fetch_returns_cells` passes, returning a real ingested dataset with n_obs >= 1 and `layers['counts']` present.
   **Why human:** Requires live network access to an external S3-hosted census dataset; intentionally excluded from CI/fast suite per design.

2. **Generated script actually runs end-to-end**
   **Test:** Download a script via the Export Script button for both a census-sourced and a file-sourced dataset, run each with `python script.py` in a fresh environment with scanpy + cellxgene_census installed.
   **Expected:** Script executes without error and reproduces the same QC/analysis result.
   **Why human:** Requires executing generated Python outside the test harness; the automated tests verify content/structure, not runtime execution of the exported script.

### Gaps Summary

No gaps found. All 9 observable truths verified, all 12 artifacts exist and are substantive and wired, all 7 key links confirmed, both requirement IDs (DATA-01, EXPORT-02) satisfied with test evidence. Full fast suite (252 tests) passes with no unknown-marker warnings and no regressions. A previously-flagged transient flakiness issue (documented in deferred-items.md) was independently re-confirmed as resolved during this verification pass.

---

_Verified: 2026-09-17_
_Verifier: Claude (gsd-verifier)_
