---
phase: 03-agent-orchestration-wiring
plan: 05
subsystem: agent
tags: [claude-agent-sdk, mcp, hooks, sqlite, pytest]

# Dependency graph
requires:
  - phase: 03-agent-orchestration-wiring (Wave 1: 03-02/03-03/03-04)
    provides: "agent/tools.py + agent/server.py (bioclaw_server MCP surface), agent/logging.py (log_tool_call), agent/memory.py (SessionMemory)"
provides:
  - "agent/session.py: build_options(), record_dataset_reference() hook factory, _recall_preamble(), run_session() multi-turn entrypoint"
  - "tests/test_agent_session_wiring.py: fast-tier unit tests for the wiring logic, no live API call"
  - "tests/test_agent_integration.py: live_llm-marked end-to-end smoke test proving AGENT-01/02/03 together across two turns"
affects: [phase-04-bio-fm-annotation, phase-06-nl-qa-capstone]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "PostToolUse hooks wrapped in claude_agent_sdk.HookMatcher(hooks=[...]) lists, not bare callables"
    - "Hook callback shape (input_data: PostToolUseHookInput, tool_use_id, context) -> dict, verified against the installed SDK package rather than assumed from docs"
    - "Explicit recall-preamble prepended to every turn's prompt, layered on top of (not replacing) the SDK's own transcript retention"

key-files:
  created:
    - agent/session.py
    - tests/test_agent_session_wiring.py
    - tests/test_agent_integration.py
  modified: []

key-decisions:
  - "Hook callback signature and ClaudeAgentOptions.hooks shape verified at implementation time via inspect.signature(claude_agent_sdk.HookMatcher) and claude_agent_sdk.types.PostToolUseHookInput.__annotations__ against the installed package -- differs from the plan's docs-consistent sketch (single input_data dict + tool_use_id + context, not positional tool_name/tool_input/tool_response/is_error kwargs; is_error lives inside tool_response, not as a top-level hook-input key; hooks[event] is list[HookMatcher], each wrapping a list of callables)"

patterns-established:
  - "_recall_preamble() called fresh before every turn (not just turn 2+) inside run_session()'s per-prompt loop, returning \"\" on a session with nothing recorded yet"

requirements-completed: ["AGENT-01", "AGENT-02", "AGENT-03"]

# Metrics
duration: 5min
completed: 2026-09-05
---

# Phase 3 Plan 05: Agent Session Wiring Summary

**`agent/session.py`'s `run_session()` wires `bioclaw_server`, `log_tool_call`, and `SessionMemory` into one multi-turn `ClaudeSDKClient` loop, with `_recall_preamble()` actually consulted before every turn -- closing the plan-checker's write-only-memory blocker.**

## Performance

- **Duration:** ~5 min
- **Started:** 2026-09-05T12:46:13Z (prior plan's completion commit)
- **Completed:** 2026-09-05T12:51:22Z
- **Tasks:** 2
- **Files modified:** 3 (all new)

## Accomplishments
- `build_options()` assembles a `ClaudeAgentOptions` wiring `bioclaw_server` under `mcp_servers["bioclaw"]`, `allowed_tools=["mcp__bioclaw__*"]`, and two `PostToolUse` hooks (logging + memory-recording) inside a single `HookMatcher`.
- `record_dataset_reference()` returns a hook that parses `dataset_id` out of a real tool result's JSON text content and records it via `SessionMemory.record()` -- silently no-ops (never raises) on error results or malformed/non-JSON text.
- `_recall_preamble()` reads `SessionMemory.recent_datasets()` back into a short context string, returning `""` when nothing has been recorded yet.
- `run_session()` accepts `prompts: str | list[str]`, opens a single `ClaudeSDKClient` context, and loops over turns -- calling `_recall_preamble()` fresh before **every** turn (including turn 1, where it is always `""`) and prepending it to the prompt actually sent to the SDK. This is the read-back half of AGENT-03 that the plan revision added.
- Verified the real installed `claude_agent_sdk` package's `PostToolUse` hook callback shape via `inspect.signature`/`__annotations__` before writing any hook code, per the plan's explicit instruction and 03-RESEARCH.md Open Question 1 -- adapted the implementation to match (see Deviations below).

## Task Commits

Each task was committed atomically (TDD RED->GREEN for Task 1):

1. **Task 1 (RED): failing tests for build_options/record_dataset_reference/_recall_preamble** - `5d33d75` (test)
2. **Task 1 (GREEN): implement build_options/record_dataset_reference/_recall_preamble** - `e08da2b` (feat)
3. **Task 2: run_session() + live_llm integration test** - `59d9168` (feat)

**Plan metadata:** (this commit, docs)

## Files Created/Modified
- `agent/session.py` - `SYSTEM_PROMPT`, `build_options()`, `record_dataset_reference()`, `_recall_preamble()`, `run_session()` -- the full Wave 2 wiring entrypoint.
- `tests/test_agent_session_wiring.py` - Fast-tier unit tests: `ClaudeAgentOptions` structure, hook JSON-parsing/memory-recording (valid dataset_id, non-JSON text, JSON without dataset_id, malformed response), and `_recall_preamble()` empty/non-empty behavior.
- `tests/test_agent_integration.py` - `@pytest.mark.live_llm` smoke test (`@pytest.mark.skipif(not os.environ.get("ANTHROPIC_API_KEY"), ...)`) driving `run_session()` across two turns against `tiny_mtx_dir`, asserting a logged `ingest_10x` record, a non-empty `SessionMemory` entry, and that turn 2's answer contains the dataset_id recorded during turn 1.

## Decisions Made
- The plan's Task 1 code sketch used a `(tool_name, tool_input, tool_response, is_error, **_)` positional-kwargs hook signature; the plan explicitly flagged this as LOW confidence and instructed verification against the installed SDK before writing hook-registration code. Running `inspect.signature(claude_agent_sdk.HookMatcher)` and inspecting `claude_agent_sdk.types.PostToolUseHookInput.__annotations__` showed the real shape is `async def _hook(input_data: PostToolUseHookInput, tool_use_id: str | None, context: HookContext) -> HookJSONOutput`, where `input_data` is a single dict-like object with `tool_name`/`tool_input`/`tool_response` keys (no top-level `is_error` -- it lives inside `tool_response` itself, matching `agent/tools.py`'s `{"content": [...], "is_error": bool}` return contract), and `ClaudeAgentOptions.hooks["PostToolUse"]` expects `list[HookMatcher]`, each wrapping a `hooks=[...]` list of callables -- not a bare list of callables. Implemented `_make_log_hook`/`record_dataset_reference` and `build_options`'s hook registration to match this real shape, and wrote `tests/test_agent_session_wiring.py`'s synthetic `PostToolUseHookInput`-shaped dicts against it. This is a mechanical signature-verification adaptation explicitly anticipated and pre-authorized by the plan itself, not an architectural deviation.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Adapted PostToolUse hook signature/registration to match the installed SDK, not the plan's sketch**
- **Found during:** Task 1 (build_options()/record_dataset_reference() implementation)
- **Issue:** The plan's code sketch (`async def _hook(tool_name, tool_input, tool_response, is_error, **_)`, `hooks={"PostToolUse": [_log_hook, record_dataset_reference(...)]}`) does not match the installed `claude-agent-sdk>=0.2.152` package's actual `HookCallback`/`ClaudeAgentOptions.hooks` types (`(input_data, tool_use_id, context)` positional args; `hooks[event]` must be `list[HookMatcher]`, not bare callables) -- using the sketch verbatim would raise at `ClaudeAgentOptions` construction or hook dispatch time.
- **Fix:** Verified real shapes via `inspect.signature(claude_agent_sdk.HookMatcher)` and `claude_agent_sdk.types.PostToolUseHookInput.__annotations__` (exactly the verification step the plan's `<action>` instructed before writing hook code), then implemented `_make_log_hook`/`record_dataset_reference` accepting `(input_data, tool_use_id, context)` and reading `tool_name`/`tool_input`/`tool_response` off `input_data`, with `is_error` derived from `tool_response.get("is_error")`. Wrapped both hooks in a single `HookMatcher(hooks=[...])` under `hooks={"PostToolUse": [...]}`.
- **Files modified:** `agent/session.py`, `tests/test_agent_session_wiring.py`
- **Verification:** `uv run pytest tests/test_agent_session_wiring.py -x -q` -- 7 passed.
- **Committed in:** `5d33d75` (test), `e08da2b` (feat)

---

**Total deviations:** 1 auto-fixed (1 blocking, pre-authorized signature verification per the plan's own `<action>` instructions)
**Impact on plan:** No scope creep -- this is exactly the "verify against the installed package before writing hook code" step the plan itself specified as LOW confidence and mandatory. All plan `<behavior>`/`<done>` criteria are met with the adapted (verified-correct) signature.

## Issues Encountered
None beyond the anticipated hook-signature verification above.

## User Setup Required
None for the fast-tier suite. The live_llm integration test (`tests/test_agent_integration.py`) requires `ANTHROPIC_API_KEY` (see `console.anthropic.com/settings/keys`) to actually execute against a real model; without it, the test is cleanly skipped (verified: `uv run pytest tests/test_agent_integration.py -m live_llm -q` -> `1 skipped`), not failed, and the fast tier does not depend on it.

## Next Phase Readiness
- Phase 3 (Agent Orchestration Wiring) is now fully implemented: Wave 0 (03-01 infra), Wave 1 (03-02 tools/server, 03-03 logging, 03-04 memory), Wave 2 (03-05 session wiring) all complete.
- `uv run pytest tests/ -q -m "not live_llm"` -> 81 passed (74 prior + 7 new fast-tier wiring tests), 1 deselected (the live_llm integration test).
- Remaining before Phase 3 is marked complete per STATE.md: gsd-verifier goal-backward check against AGENT-01/02/03, and (separately, when a researcher has `ANTHROPIC_API_KEY` available) running `tests/test_agent_integration.py -m live_llm` for the actual live acceptance evidence per 03-VALIDATION.md's Phase Gate.
- `run_session()` is the entrypoint Phase 6 (NL Q&A capstone) will build a user-facing surface on top of.

---
*Phase: 03-agent-orchestration-wiring*
*Completed: 2026-09-05*

## Self-Check: PASSED

All claimed files found on disk (agent/session.py, tests/test_agent_session_wiring.py, tests/test_agent_integration.py, this SUMMARY.md); all claimed commit hashes (5d33d75, e08da2b, 59d9168) found in git log.
