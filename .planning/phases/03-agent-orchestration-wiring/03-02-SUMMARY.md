---
phase: 03-agent-orchestration-wiring
plan: 02
subsystem: agent
tags: [claude-agent-sdk, mcp, tool-calling, tdd, scanpy]

# Dependency graph
requires:
  - phase: 03-agent-orchestration-wiring
    provides: "03-01: claude-agent-sdk installed, live_llm pytest marker, agent/ package skeleton"
provides:
  - "agent/tools.py: ingest_10x_tool/analyze_dataset_tool @tool-decorated async handlers, thin pass-throughs to Phase 1/2's ingest_10x()/analyze()"
  - "agent/server.py: bioclaw_server, an in-process create_sdk_mcp_server(...) wrapping both tools"
affects: [03-05-wave-2-session-wiring]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "@tool-decorated handlers become claude_agent_sdk.SdkMcpTool instances, not directly callable -- unit tests invoke <tool>.handler(args) directly; the SdkMcpTool objects themselves are what create_sdk_mcp_server(tools=[...]) expects"
    - "Bounded Phase 1/2 results serialized via json.dumps() into a single text content block (structuredContent is silently dropped by the in-process @tool decorator)"
    - "Optional tool-input params (e.g. analyze_dataset_tool's version) omitted from the dict schema and read via args.get(...) in the handler, since every key in a dict schema is otherwise required"
    - "STORE_ROOT is a module-level constant read once at import time (env-overridable via BIOCLAW_STORE_ROOT), never taken from LLM-controlled args -- a deliberate isolation boundary"
    - "Uncaught Phase 1/2 exceptions (KeyError, RuntimeError) propagate straight through the handler; the SDK's in-process MCP server converts them to error tool results at dispatch time"

key-files:
  created:
    - agent/tools.py
    - agent/server.py
    - tests/test_agent_tools.py
  modified: []

key-decisions:
  - "Test suite calls <tool>.handler(args) rather than <tool>(args) directly, since @tool-decorated functions are SdkMcpTool instances (verified against the installed claude_agent_sdk package: vars() shows name/description/input_schema/handler/annotations fields) -- not plain callables as the plan's illustrative <behavior> text implied"
  - "Added a local analyzable_mtx_dir fixture (300 genes x 60 cells, two marker-gene pseudo populations) in tests/test_agent_tools.py for the analyze_dataset_tool round-trip test, instead of reusing conftest.py's tiny_mtx_dir (18 genes): QCConfig's default min_genes_per_cell=200 filters every cell out of an 18-gene dataset (no cell can ever have >=200 detected genes when only 18 exist), and ingest_10x_tool's schema intentionally doesn't expose qc_config as a tool-input override -- Phase 1's own tests/test_pipeline.py always overrides qc_config when running the full pipeline on tiny_mtx_dir for this same reason. tiny_mtx_dir is still used, per the plan, for the plain ingest-only test."

patterns-established:
  - "MCP tool wiring: any future Phase 1/2 entrypoint the agent needs to call gets a thin @tool handler here, then gets added to bioclaw_server's tools=[...] list in agent/server.py -- no intermediate abstraction layer."

requirements-completed: ["AGENT-01"]

# Metrics
duration: 12min
completed: 2026-09-05
---

# Phase 3 Plan 02: Agent Orchestration Wiring -- Tool-Calling Surface Summary

**Thin `@tool`-decorated handlers (`ingest_10x_tool`, `analyze_dataset_tool`) wrapping Phase 1/2's real pipeline functions verbatim, assembled into one in-process `bioclaw_server` MCP server ready for Wave 2's `ClaudeAgentOptions` wiring.**

## Performance

- **Duration:** ~12 min
- **Started:** 2026-09-05T12:38:00Z (approx, per session start)
- **Completed:** 2026-09-05T12:50:00Z
- **Tasks:** 2
- **Files modified:** 3 (all created)

## Accomplishments
- `agent/tools.py` implements `ingest_10x_tool`/`analyze_dataset_tool`, both thin async wrappers that call the real `ingest_10x()`/`analyze()` functions and serialize the bounded-dataclass result as a single JSON `text` content block.
- `analyze_dataset_tool`'s optional `version` parameter is omitted from its registered tool schema (`{"name": str}`, no `version` key) and read via `args.get("version")` in the handler -- verified directly against the installed `claude_agent_sdk` package's `SdkMcpTool.input_schema` attribute.
- `STORE_ROOT` is a module-level constant (env-overridable via `BIOCLAW_STORE_ROOT`), never read from LLM-controlled `args` -- tests monkeypatch it to `tmp_path`, so no test ever writes into the repo's real `data/` directory.
- `agent/server.py` assembles both tools into `bioclaw_server = create_sdk_mcp_server(name="bioclaw", version="1.0.0", tools=[...])`, which imports and constructs cleanly.
- `tests/test_agent_tools.py` (5 tests, TDD RED->GREEN for Task 1) covers: successful ingest returning `{"dataset_id": "pilot@1"}`, a full ingest->analyze round trip returning `preprocess`/`cluster`/`de` keys with `de: None`, the version-omitted-from-schema contract, propagated `KeyError` on an unknown dataset name, and `bioclaw_server`'s clean import.

## Task Commits

Each task was committed atomically:

1. **Task 1: ingest_10x_tool + analyze_dataset_tool handlers (TDD)** - `939fc89` (feat) -- test file written and confirmed RED (`ModuleNotFoundError: No module named 'agent.tools'`) before `agent/tools.py` was implemented; committed together once GREEN since both were authored in the same pass per the plan's TDD flow.
2. **Task 2: Assemble the in-process MCP server** - `73a8c5a` (feat) -- `agent/server.py` added plus one import-assertion test.

**Plan metadata:** (this SUMMARY.md + STATE.md commit, made immediately following this document)

## Files Created/Modified
- `agent/tools.py` - `ingest_10x_tool`, `analyze_dataset_tool` (`SdkMcpTool` instances via `@tool`), module-level `STORE_ROOT`
- `agent/server.py` - `bioclaw_server`, the assembled in-process MCP server
- `tests/test_agent_tools.py` - 5 tests: ingest round trip, analyze round trip, schema-omits-version contract, unknown-dataset `KeyError` propagation, `bioclaw_server` import

## Decisions Made
- Test calls use `<tool>.handler(args)`, not `<tool>(args)` directly -- see key-decisions above for the verified reason (`SdkMcpTool` instances aren't callable; `agent/server.py`'s `create_sdk_mcp_server(tools=[...])` needs the `SdkMcpTool` objects themselves, so the exported names had to stay as the decorated objects, not the raw handler functions).
- Added a local, larger, real-structure `analyzable_mtx_dir` fixture for the analyze round-trip test instead of `tiny_mtx_dir` -- see key-decisions above for the QC-threshold reasoning.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] `@tool`-decorated functions are not directly callable**
- **Found during:** Task 1 (writing `tests/test_agent_tools.py`)
- **Issue:** The plan's `<behavior>` text illustrates calling `asyncio.run(ingest_10x_tool({...}))` directly, but the installed `claude_agent_sdk`'s `@tool` decorator returns an `SdkMcpTool` instance (confirmed via `vars(decorated_fn)` showing `name`/`description`/`input_schema`/`handler`/`annotations`), which is not callable (`TypeError: 'SdkMcpTool' object is not callable`).
- **Fix:** Tests invoke `<tool>.handler(args)` instead of `<tool>(args)`; `agent/tools.py`'s implementation is otherwise unchanged from the plan's provided code (the module-level names `ingest_10x_tool`/`analyze_dataset_tool` remain the decorated `SdkMcpTool` objects, exactly as `agent/server.py`'s `create_sdk_mcp_server(tools=[...])` requires).
- **Files modified:** tests/test_agent_tools.py
- **Verification:** `uv run pytest tests/test_agent_tools.py -x -q` passes
- **Committed in:** `939fc89` (Task 1 commit)

**2. [Rule 3 - Blocking] `tiny_mtx_dir`'s 18 genes can never pass default QC thresholds**
- **Found during:** Task 1 (writing the analyze-round-trip test)
- **Issue:** Calling `analyze()` immediately after ingesting `tiny_mtx_dir` (per the plan's literal `<behavior>` text) raised `ValueError: Found array with 0 sample(s)` inside `sc.pp.log1p` -- `ingest_10x`'s default `QCConfig(min_genes_per_cell=200)` filtered every one of `tiny_mtx_dir`'s 40 cells out, since no cell can have >=200 detected genes when the fixture only has 18 genes total. Confirmed this is a known, pre-existing characteristic of this fixture: Phase 1's own `tests/test_pipeline.py` always overrides `qc_config=QCConfig(min_genes_per_cell=1)` when running a full pipeline against `tiny_mtx_dir`. `ingest_10x_tool`'s schema intentionally has no `qc_config` override (out of this plan's declared tool-input surface), so the same override path isn't available through the tool layer.
- **Fix:** Added a local `analyzable_mtx_dir` pytest fixture directly in `tests/test_agent_tools.py` (not `conftest.py`, which is shared, read-only infrastructure this plan doesn't own) -- 300 genes x 60 cells with two marker-gene pseudo populations, large/structured enough to survive default QC and produce genuine cluster structure. `tiny_mtx_dir` is still used, per the plan, for the plain ingest-only test.
- **Files modified:** tests/test_agent_tools.py
- **Verification:** `uv run pytest tests/test_agent_tools.py -x -q` passes; full round trip confirmed producing `n_clusters: 2` before being folded into the test assertions.
- **Committed in:** `939fc89` (Task 1 commit)

---

**Total deviations:** 2 auto-fixed (both Rule 3 - blocking issues discovered while writing the RED tests, resolved before any implementation was written)
**Impact on plan:** Both fixes were necessary to make the plan's stated `<done>` criteria achievable at all; no scope creep -- `agent/tools.py`/`agent/server.py` were implemented exactly per the plan's provided code blocks with zero changes.

## Issues Encountered
None beyond the two deviations documented above.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- `bioclaw_server` is ready for Wave 2's (`03-05`) `ClaudeAgentOptions(mcp_servers={"bioclaw": bioclaw_server})` wiring.
- `agent/tools.py`'s `STORE_ROOT` env-override pattern (`BIOCLAW_STORE_ROOT`) is available if Wave 2's session wiring needs to point the whole agent process at a non-default data directory.
- No blockers for Wave 2. Full fast-tier suite (`uv run pytest tests/ -q -m "not live_llm"`) is green at 74 passed, including this plan's 5 new tests alongside 03-03/03-04's Wave 1 sibling tests.

---
*Phase: 03-agent-orchestration-wiring*
*Completed: 2026-09-05*

## Self-Check: PASSED

- FOUND: agent/tools.py
- FOUND: agent/server.py
- FOUND: tests/test_agent_tools.py
- FOUND: .planning/phases/03-agent-orchestration-wiring/03-02-SUMMARY.md
- FOUND: 939fc89 (Task 1 commit)
- FOUND: 73a8c5a (Task 2 commit)
