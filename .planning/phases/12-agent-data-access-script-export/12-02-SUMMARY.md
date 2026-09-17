---
phase: 12-agent-data-access-script-export
plan: 02
subsystem: data
tags: [cellxgene-census, asyncio, tiledb-soma, mcp-tool, agent]

# Dependency graph
requires:
  - phase: 12-01
    provides: "format_census_source() and ingest_from_anndata() helpers in ingest/census.py"
provides:
  - "fetch_census_dataset() async orchestration in ingest/census.py, running the blocking TileDB-SOMA census fetch inside asyncio.to_thread()"
  - "fetch_census_dataset_tool @tool handler in agent/tools.py"
  - "fetch_census_dataset_tool registered in bioclaw_server (agent/server.py)"
affects: [12-03-export-script, phase-13-fm]

# Tech tracking
tech-stack:
  added: [cellxgene_census, anndata]
  patterns:
    - "Entire TileDB-SOMA context-manager + get_anndata call kept inside one closure (_census_fetch_blocking) passed wholesale to asyncio.to_thread() — never open the census outside the thread and pass the handle in"
    - "Cell-count limiting via post-fetch n_obs check + descriptive ValueError, not obs_coords slicing (unreliable on soma_joinid per RESEARCH Pitfall 2)"

key-files:
  created: []
  modified:
    - ingest/census.py
    - agent/tools.py
    - agent/server.py
    - tests/test_census_tool.py
    - tests/test_census_smoke.py

key-decisions:
  - "_census_fetch_blocking() keeps the ENTIRE open_soma with-block + get_anndata call inside one function passed to asyncio.to_thread(), per RESEARCH Pattern 2/Pitfall 1"
  - "max_cells enforced via post-fetch n_obs check (default 50,000), not obs_coords slicing, per RESEARCH Pitfall 2"
  - "Fixed pre-existing test scaffold bugs from 12-01 (SdkMcpTool.handler(...) instead of calling the tool object directly; asyncio.run() instead of deprecated get_event_loop().run_until_complete()) — the latter was explicitly flagged as a 12-02 action item in deferred-items.md by the concurrently-executing 12-03 plan"

patterns-established:
  - "Async @tool handlers that await an async pipeline function directly (fetch_census_dataset_tool) rather than wrapping a sync pipeline call, unlike the four pre-existing handlers"

requirements-completed: [DATA-01]

# Metrics
duration: 20min
completed: 2026-09-17
---

# Phase 12 Plan 02: Agent Census Fetch Tool Summary

**Agent can fetch a real public single-cell dataset from cellxgene-census by organism + obs_value_filter via a new `fetch_census_dataset` MCP tool, with the blocking TileDB-SOMA I/O offloaded to `asyncio.to_thread()` so the event loop never stalls.**

## Performance

- **Duration:** ~20 min
- **Completed:** 2026-09-17T14:05:02Z
- **Tasks:** 2 completed
- **Files modified:** 5 (3 plan-scoped: `ingest/census.py`, `agent/tools.py`, `agent/server.py`; 2 test-scaffold fixes: `tests/test_census_tool.py`, `tests/test_census_smoke.py`)

## Accomplishments
- `ingest/census.py` now provides `_census_fetch_blocking()` (the entire `open_soma`/`get_anndata` call in one thread-safe closure) and `async fetch_census_dataset()` (offloads via `asyncio.to_thread`, enforces a `max_cells` guard, ingests via `ingest_from_anndata` with a reproducible `format_census_source()` provenance string).
- `agent/tools.py` gained `fetch_census_dataset_tool`, an async `@tool` handler that awaits the fetch directly and returns `{"dataset_id": ...}` on the same success/error contract as the other four tools.
- `agent/server.py`'s `bioclaw_server` now registers all five tools, including `fetch_census_dataset_tool`.
- DATA-01 satisfied: a researcher can ask the agent for a dataset by organism + tissue/assay filter and get back a real, ingested dataset handle — not an upload.

## Task Commits

Each task was committed atomically:

1. **Task 1: Implement census fetch orchestration in ingest/census.py** - `63bfb38` (feat)
2. **Task 2: Add fetch_census_dataset_tool and register in bioclaw_server** - `67767cd` (feat)

**Plan metadata:** (final commit, see below)

## Files Created/Modified
- `ingest/census.py` - Added `_census_fetch_blocking()` closure and `async fetch_census_dataset()` orchestration on top of Wave 0's `format_census_source()`/`ingest_from_anndata()`
- `agent/tools.py` - Added `fetch_census_dataset_tool` `@tool` handler, imported `fetch_census_dataset`
- `agent/server.py` - Registered `fetch_census_dataset_tool` in `bioclaw_server`'s `tools=[...]` list
- `tests/test_census_tool.py` - Fixed scaffold bugs (see Deviations) so the 12-01 RED test scaffold actually goes GREEN
- `tests/test_census_smoke.py` - Same scaffold fix applied for consistency (network-gated, not run in this plan's automated verification)

## Decisions Made
- `_census_fetch_blocking()` keeps the entire `with cellxgene_census.open_soma(...) as census: ... get_anndata(...)` block inside one function body, passed wholesale to `asyncio.to_thread()` — confirmed this matches RESEARCH Pattern 2/Pitfall 1 exactly (both calls must run in the same worker thread).
- Cell-count limiting implemented as a post-fetch `n_obs > max_cells` check raising a descriptive `ValueError`, not `obs_coords` slicing on `soma_joinid` (RESEARCH Pitfall 2 flags the latter as unreliable).
- `census_version` kept optional (`args.get("census_version", "stable")`), omitted from the tool's dict schema per the established "Pitfall 2" pattern for optional args in `agent/tools.py`.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Fixed pre-existing test scaffold calling SdkMcpTool objects directly instead of via `.handler(...)`**
- **Found during:** Task 1 verification (`uv run pytest tests/test_census_tool.py -x -q`)
- **Issue:** `tests/test_census_tool.py` (committed in 12-01 as a RED scaffold) called `fetch_census_dataset_tool({...})` directly. `@tool`-decorated functions return an `SdkMcpTool` dataclass instance with a `.handler` attribute, not a callable — this raised `TypeError: 'SdkMcpTool' object is not callable` even after Task 2's tool was correctly implemented. The established convention in `tests/test_agent_tools.py` for the four existing tools is `tool_name.handler({...})`.
- **Fix:** Changed all three call sites in `tests/test_census_tool.py` and the one call site in `tests/test_census_smoke.py` to `fetch_census_dataset_tool.handler({...})`.
- **Files modified:** `tests/test_census_tool.py`, `tests/test_census_smoke.py`
- **Verification:** `uv run pytest tests/test_census_tool.py -q` → 4 passed.
- **Committed in:** `67767cd` (Task 2 commit)

**2. [Rule 3 - Blocking] Replaced deprecated `asyncio.get_event_loop().run_until_complete()` with `asyncio.run()`**
- **Found during:** Task 2 verification (full fast suite: `uv run pytest tests/ -m "not live_llm and not bio_fm_smoke and not vcc_data and not census_data" -q`)
- **Issue:** `tests/test_census_tool.py`'s three async tests used `asyncio.get_event_loop().run_until_complete(...)`, which raised `RuntimeError: There is no current event loop in thread 'MainThread'` when run after other test modules in the full suite (an earlier test leaves no default event loop installed). Tests passed in isolation but failed intermittently in the full suite. This exact issue was independently flagged in `.planning/phases/12-agent-data-access-script-export/deferred-items.md` by the concurrently-executing 12-03 plan as "Action: Not fixed by 12-03 ... flagging for 12-02's own verification pass."
- **Fix:** Replaced all four `asyncio.get_event_loop().run_until_complete(...)` call sites (three in `tests/test_census_tool.py`, one in `tests/test_census_smoke.py`) with `asyncio.run(...)`, matching the pattern already used in `tests/test_agent_tools.py`.
- **Files modified:** `tests/test_census_tool.py`, `tests/test_census_smoke.py`
- **Verification:** `uv run pytest tests/ -m "not live_llm and not bio_fm_smoke and not vcc_data and not census_data" -q` → 252 passed, 7 deselected, no failures.
- **Committed in:** `67767cd` (Task 2 commit)

---

**Total deviations:** 2 auto-fixed (both Rule 3 - blocking test-scaffold issues, not implementation bugs)
**Impact on plan:** Both fixes were in the pre-existing test scaffold (committed in 12-01), not in this plan's implementation code. No scope creep — `ingest/census.py`, `agent/tools.py`, and `agent/server.py` were implemented exactly per spec with no fixes needed.

## Issues Encountered
- `ingest/census.py` arrived with the Task 1 implementation already present in the working tree from an earlier interrupted run. Diffed it against the plan's spec before proceeding: it matched exactly (both the `_census_fetch_blocking` closure and `fetch_census_dataset` orchestration), so it was verified and committed as-is rather than rewritten.
- Unrelated, out-of-scope uncommitted changes were present in the working tree at start (`webapp/frontend/api.js`, `webapp/frontend/index.html`, `webapp/frontend/main.js`, `webapp/backend/export_script.py`, `agent/memory.sqlite-shm/-wal`) — these belong to the concurrently-executing 12-03 plan (export script feature) and were left untouched and uncommitted by this plan.

## User Setup Required

None - no external service configuration required. (Real network access to cellxgene-census is only exercised by the phase-gate smoke test `tests/test_census_smoke.py`, gated behind `CENSUS_DATA=1` and the `census_data` marker; not required to pass for this plan.)

## Next Phase Readiness
- DATA-01 fully satisfied; `fetch_census_dataset_tool` is live in `bioclaw_server` alongside the four existing tools.
- `format_census_source()` provenance string is stored as `source_path` on every census-fetched dataset, satisfying EXPORT-02's dependency (script export can reconstruct the census query) — 12-03 (concurrently executed) already builds on this.
- No blockers for Phase 13 (Bio FM integration).

---
*Phase: 12-agent-data-access-script-export*
*Completed: 2026-09-17*

## Self-Check: PASSED

- FOUND: ingest/census.py
- FOUND: agent/tools.py
- FOUND: agent/server.py
- FOUND: .planning/phases/12-agent-data-access-script-export/12-02-SUMMARY.md
- FOUND: commit 63bfb38
- FOUND: commit 67767cd
- FOUND: fetch_census_dataset_tool registered in agent/server.py
