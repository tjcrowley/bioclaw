---
phase: 07-backend-api-streaming-foundation
plan: 03
subsystem: api
tags: [fastapi, websocket, pytest, live_llm, claude-agent-sdk]

# Dependency graph
requires:
  - phase: 07-backend-api-streaming-foundation
    provides: "Plan 07-02's webapp/backend/main.py (POST /api/ask, WS /ws/{stream_id}), streaming.py queue registry, and deps.py overridable ask_question, all password-gated per Plan 07-01"
provides:
  - "tests/test_webapp_integration.py -- single live_llm-marked end-to-end test proving the real FastAPI app (no dependency_overrides), a real ask_question() call, and real WebSocket tool-event streaming all work together against the live Claude Agent SDK"
  - "Live, human-confirmed proof that the backend is password-gated (401 unauthenticated / 200 authenticated) and runs localhost-only, closing out Phase 7's success criteria"
affects: [08-session-dataset-endpoints, 09-frontend-chat-ui]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "live_llm end-to-end test connects a WebSocket client before issuing the correlated POST, then asserts on the first streamed event's tool_name prefix (mcp__bioclaw__) -- mirrors Phase 6's 06-03 live_llm checkpoint pattern at the HTTP/WS layer instead of calling ask_question() directly"
    - "Tolerate SDK-internal meta tool-call events (e.g. ToolSearch) that can precede the first domain tool-call event on a real streamed session -- assert on the first event whose tool_name matches the expected domain prefix, not unconditionally on the very first event received"

key-files:
  created:
    - tests/test_webapp_integration.py
  modified: []

key-decisions:
  - "test_ask_streams_real_tool_events_end_to_end drains WebSocket events in a loop until it finds one whose tool_name starts with mcp__bioclaw__, rather than asserting on ws.receive_json() unconditionally -- the real Claude Agent SDK can emit its own internal ToolSearch/meta events over the same PostToolUse hook path before the first domain tool call, which the fast-tier (faked) tests never exercised"
  - "Checkpoint approved by Darren with a real ANTHROPIC_API_KEY: live_llm test passed (1 passed), unauthenticated POST /api/ask returned 401, password-authenticated POST /api/ask returned 200, and the server was confirmed bound to 127.0.0.1 only for the entire verification -- no deployment or remote host involved at any point"

patterns-established: []

requirements-completed: [API-01, API-02]

# Metrics
duration: ~15min active (plus a cross-session pause awaiting human verification with a real ANTHROPIC_API_KEY)
completed: 2026-09-12
---

# Phase 7 Plan 03: Live End-to-End Webapp Integration Test + Phase Gate Checkpoint Summary

**Single live_llm-marked test (`tests/test_webapp_integration.py`) proving the real FastAPI app, a real `ask_question()` call, and real WebSocket tool-event streaming work together end to end against the live Claude Agent SDK -- confirmed by Darren with a real API key: 1 passed, 401 unauthenticated / 200 authenticated, localhost-only throughout.**

## Performance

- **Duration:** ~15 min active work (Task 1 write + one auto-fix), plus a cross-session pause while awaiting the human-verify checkpoint with a real `ANTHROPIC_API_KEY`
- **Tasks:** 2 completed (1 auto + 1 checkpoint)
- **Files modified:** 1

## Accomplishments
- `tests/test_webapp_integration.py`: one `live_llm`-marked, `ANTHROPIC_API_KEY`-gated test that drives the real, non-dependency-overridden FastAPI `app` through a real `POST /api/ask` call while a WebSocket client is connected to the correlated `/ws/{stream_id}`, and asserts a real `mcp__bioclaw__*` tool-call event arrives over the socket alongside a non-empty real answer over HTTP
- Fixed the test (Rule 1, discovered only when actually run against the live SDK) to tolerate SDK-internal `ToolSearch`-style meta tool-call events that can precede the first domain tool-call event on a real session, instead of asserting on the very first WebSocket event unconditionally
- Phase gate checkpoint run and confirmed by Darren with a real `ANTHROPIC_API_KEY`:
  - `uv run --extra web pytest tests/test_webapp_integration.py -m live_llm -x -s` -> 1 passed
  - `POST /api/ask` without password against a locally-running `uvicorn webapp.backend.main:app` -> 401
  - `POST /api/ask?password=<real password>` -> 200 with a real answer
  - Server bound to `127.0.0.1:8000` only for the entire verification -- no deployment, no remote host, no DigitalOcean involvement
- Phase 7 (Backend API + Streaming Foundation) is now complete: all three plans (07-01, 07-02, 07-03) executed and verified; API-01, API-02, API-05 all closed

## Task Commits

1. **Task 1: Write the live_llm end-to-end webapp integration test** - `ac744e8` (test)
2. **(Rule 1 fix) Tolerate SDK ToolSearch meta-events before first domain tool-call event** - `e81c848` (fix)
3. **Task 2: Checkpoint: Verify real end-to-end ask + streaming, and localhost-only operation** - human verification only, no code commit; approved by Darren (see Checkpoint Resolution below)

**Plan metadata:** (this commit)

## Files Created/Modified
- `tests/test_webapp_integration.py` - `test_ask_streams_real_tool_events_end_to_end`: real `TestClient(app)` (no overrides), real `ask_question()` via `POST /api/ask`, real WebSocket drain loop asserting on the first `mcp__bioclaw__*` tool-call event

## Decisions Made
- WebSocket assertion drains events in a loop looking for the first `tool_name` starting with `mcp__bioclaw__`, rather than asserting on the first event received -- the real Claude Agent SDK can surface its own internal meta events (e.g. `ToolSearch`) over the same hook path before any domain tool call, a behavior the fast-tier faked tests never exercised and which only surfaced once run against the live SDK
- Checkpoint treated as unambiguously approved: Darren ran the exact `how-to-verify` steps with a real `ANTHROPIC_API_KEY` and `BIOCLAW_WEB_PASSWORD`, pasted terminal output confirming 1 passed / 401 / 200, and confirmed the server never left `127.0.0.1`

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Tolerate SDK ToolSearch meta-events before first domain tool-call event**
- **Found during:** Task 2 (running the live_llm test against the real Claude Agent SDK for the first time)
- **Issue:** The initial test asserted on the very first WebSocket event unconditionally, but the real SDK can emit its own internal `ToolSearch`-style meta tool-call event over the same `PostToolUse` hook path before the first `mcp__bioclaw__*` domain tool call -- a distinction invisible to the fast-tier tests in Plan 07-02, which only ever fake a single domain tool call
- **Fix:** Changed the assertion to drain WebSocket events in a loop until one is found whose `tool_name` starts with `mcp__bioclaw__`, then assert on that event
- **Files modified:** `tests/test_webapp_integration.py`
- **Verification:** Confirmed by Darren's checkpoint run -- `uv run --extra web pytest tests/test_webapp_integration.py -m live_llm -x -s` -> 1 passed
- **Committed in:** `e81c848`

---

**Total deviations:** 1 auto-fixed (1 bug fix, surfaced only by the live SDK)
**Impact on plan:** Necessary for correctness against the real SDK's actual event stream; no scope creep -- the fix only changes which event the test asserts on, not what it verifies.

## Issues Encountered

None beyond the auto-fixed issue above.

## User Setup Required

None going forward. This plan's own human-verify checkpoint required a real `ANTHROPIC_API_KEY` and `BIOCLAW_WEB_PASSWORD` for one-time manual verification, which Darren has now completed and confirmed.

## Checkpoint Resolution

The Task 2 human-verify checkpoint (gate="blocking") was run by Darren locally with a real `ANTHROPIC_API_KEY` and confirmed:
1. `uv run --extra web pytest tests/test_webapp_integration.py -m live_llm -x -s` -> **1 passed** (the ToolSearch-tolerant fix from `e81c848` resolved the real end-to-end ask + tool-call streaming test against the live Claude Agent SDK).
2. `uv run --extra web uvicorn webapp.backend.main:app --port 8000` started locally.
3. `POST /api/ask` without a password -> **401 Unauthorized**.
4. `POST /api/ask?password=<real password>` -> **200 OK**.
5. The server was bound to `127.0.0.1:8000` only for the entire verification -- no deployment, no remote host, no DigitalOcean involvement at any point.

Darren's exact confirmation ("it worked", with pasted terminal output matching all of the above) is treated as unambiguous approval; no further verification was requested.

## Next Phase Readiness

Phase 7 (Backend API + Streaming Foundation) is complete: all three plans (07-01, 07-02, 07-03) executed and verified, both structurally (fast-tier tests) and live (this plan's `live_llm` checkpoint). API-01, API-02, and API-05 are all closed.

Phase 8 (Session & Dataset Endpoints, API-03/API-04) can now build directly on:
- `webapp/backend/main.py`'s password-gated FastAPI `app` and its `require_password`/`require_password_ws` dependencies
- `webapp/backend/deps.py`'s `Depends()`-overridable pattern for injecting fakes into fast-tier tests
- `webapp/backend/streaming.py`'s queue registry, if any new streaming endpoint needs the same live tool-event pattern

No blockers. No open issues carried forward from Phase 7.

---
*Phase: 07-backend-api-streaming-foundation*
*Completed: 2026-09-12*

## Self-Check: PASSED

Verified on disk: `tests/test_webapp_integration.py` FOUND. Verified in git history: commits `ac744e8` and `e81c848` both FOUND.
