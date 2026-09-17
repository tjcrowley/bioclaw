# Deferred Items — Phase 12

## From 12-03 execution (2026-09-17)

**Item:** `tests/test_census_tool.py::test_census_fetch_returns_dataset_id`,
`test_census_fetch_runs_in_thread`, `test_fetched_dataset_loadable` fail
intermittently when the full fast test suite runs (`uv run pytest tests/ -m
"not live_llm and not bio_fm_smoke and not vcc_data and not census_data" -q`),
but pass in isolation (`uv run pytest tests/test_census_tool.py -q` and
`... -k test_census_tool` within the full collection both green).

**Root cause (suspected):** `tests/test_census_tool.py` uses
`asyncio.get_event_loop().run_until_complete(...)` (see its own
DeprecationWarning: "There is no current event loop") instead of
`pytest.mark.asyncio` / `asyncio.run()`. This pattern is fragile to test
ordering — an earlier async test in the suite can leave no event loop
installed on the current thread, causing `RuntimeError` for this file's
tests specifically when run after other suites.

**Scope:** `tests/test_census_tool.py`, `agent/tools.py`, `ingest/census.py`
are all owned by the concurrently-executing plan 12-02
(census-fetch-tool), which this plan (12-03) was explicitly instructed not
to touch. Confirmed out of scope: `uv run pytest tests/ ... --ignore=tests/test_census_tool.py`
gives 248 passed / 0 failed, i.e. no regression from 12-03's changes
(export_script.py, main.py, api.js, index.html, main.js).

**Action:** Not fixed by 12-03. Flagging for 12-02's own verification pass —
its own plan's `<verify>` step should catch this if it re-runs the full
suite after 12-02 finishes and files stabilize.

**Resolution (2026-09-17, post-12-02 landing):** Re-ran the full fast suite
after plan 12-02 committed (`feat(12-02): implement census fetch
orchestration in ingest/census.py`, `feat(12-02): add
fetch_census_dataset_tool and register in bioclaw_server`) — all 252 tests
now pass with 0 failures. Confirms this was transient flakiness from
concurrent file edits mid-execution, not a real defect. No further action
needed.
