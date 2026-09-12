---
phase: 07-backend-api-streaming-foundation
plan: 02
subsystem: api
tags: [fastapi, asyncio, websocket, streaming, dependency-injection]

# Dependency graph
requires:
  - phase: 07-backend-api-streaming-foundation
    provides: "Plan 07-01's extra_hooks kwarg on ask_question(), webapp/backend/schemas.py contracts, and webapp/backend/auth.py require_password/require_password_ws"
provides:
  - "webapp/backend/streaming.py -- stream_id-keyed asyncio.Queue registry (get_or_create_queue/drop_queue) + make_stream_hook PostToolUse hook factory that never raises"
  - "webapp/backend/deps.py -- get_ask_question, an overridable Depends() factory wrapping qa.session.ask_question for fast-tier test injection"
  - "webapp/backend/main.py -- FastAPI app with POST /api/ask (API-01) and WS /ws/{stream_id} (API-02), both password-gated (API-05)"
affects: [07-03, 08-streaming-endpoints, 09-frontend]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "In-process asyncio.Queue registry keyed by a client-supplied stream_id, bridging a PostToolUse hook (server-side tool activity) into a WebSocket drain loop (client-facing) -- single-Uvicorn-worker only"
    - "Hooks passed through extra_hooks must swallow all exceptions and always return {} -- verified explicitly by a never-raises test with a full queue and malformed input"
    - "FastAPI Depends()-injectable factory (deps.get_ask_question) overridden via app.dependency_overrides in tests, so fast-tier endpoint tests never call the real LLM"

key-files:
  created:
    - webapp/backend/streaming.py
    - webapp/backend/deps.py
    - webapp/backend/main.py
  modified:
    - tests/test_webapp_backend.py

key-decisions:
  - "make_stream_hook's _tool_response_is_error() only recognizes a dict with is_error truthy -- matches the plan's exact spec and the schema's ToolEvent.is_error boolean; a list-shaped tool_response (the common success case) is always is_error=False"
  - "main.py accepts the WebSocket (await websocket.accept()) only after require_password_ws's Depends() resolves, so an unauthenticated WS client is rejected with a policy-violation close before any accept -- relies on FastAPI 0.141's support for raising WebSocketException from a dependency"
  - "streaming.drop_queue(stream_id) is called in the WS handler's finally block, so a queue is torn down when its one WebSocket consumer disconnects, regardless of whether disconnect was clean or an exception"

patterns-established: []

requirements-completed: [API-01, API-02, API-05]

# Metrics
duration: ~5min
completed: 2026-09-12
---

# Phase 7 Plan 02: Streaming Queue Registry + FastAPI Ask/WS Endpoints Summary

**In-process asyncio.Queue registry + PostToolUse hook factory (streaming.py), an overridable ask_question dependency (deps.py), and a password-gated FastAPI app exposing POST /api/ask and WS /ws/{stream_id} (main.py) -- proven end to end by a fast-tier test where a WebSocket client connected before a POST receives that POST's tool-call events live.**

## Performance

- **Duration:** ~5 min
- **Tasks:** 2 completed
- **Files modified:** 4

## Accomplishments
- `webapp/backend/streaming.py`: `get_or_create_queue`/`drop_queue` (stream_id-keyed, idempotent) and `make_stream_hook` (a PostToolUse hook factory that enqueues `{tool_name, tool_input, is_error}` events and never raises, even on a full queue or malformed `tool_response`)
- `webapp/backend/deps.py`: `get_ask_question()` returning the real `qa.session.ask_question`, overridable per-test via `app.dependency_overrides`
- `webapp/backend/main.py`: `POST /api/ask` (delegates to the injected `ask_question`, wires a `make_stream_hook` into `extra_hooks` when `stream_id` is present) and `WS /ws/{stream_id}` (drains its queue to the client until disconnect), both gated behind Plan 07-01's `require_password`/`require_password_ws`
- Proved live, in a fast-tier test with no real API key: a WS client connected to `/ws/stream-1` before the correlated `POST /api/ask` receives that request's tool-call event over the wire (API-02's core behavior)
- Full fast test suite (172 tests, excluding `live_llm`/`bio_fm_smoke`/`vcc_data`) green with these new files added

## Task Commits

1. **Task 1: streaming.py queue registry + hook factory, deps.py overridable ask_question** - `41909ca` (feat)
2. **Task 2: main.py -- FastAPI app, POST /api/ask, WS /ws/{stream_id}** - `f1682b4` (feat)

**Plan metadata:** (this commit)

## Files Created/Modified
- `webapp/backend/streaming.py` - `_QUEUES` registry dict, `get_or_create_queue`, `drop_queue`, `_tool_response_is_error`, `make_stream_hook`
- `webapp/backend/deps.py` - `get_ask_question()` factory wrapping `qa.session.ask_question`
- `webapp/backend/main.py` - FastAPI `app`, `POST /api/ask`, `WS /ws/{stream_id}`
- `tests/test_webapp_backend.py` - 9 new tests: 5 for streaming.py/deps.py (Task 1), 4 for main.py's endpoints (Task 2)

## Decisions Made
- `_tool_response_is_error()` checks only `isinstance(tool_response, dict) and tool_response.get("is_error")` -- matches the plan's exact spec verbatim, no broader heuristic needed since the schema's `ToolEvent.is_error` is a plain boolean
- WS handler calls `await websocket.accept()` only after the `require_password_ws` dependency succeeds, relying on FastAPI 0.141.1's documented support for raising `WebSocketException` from a route dependency to reject the handshake pre-accept
- `streaming.drop_queue(stream_id)` placed in the WS handler's `finally` block so a queue's lifetime is tied to its single WebSocket consumer's connection lifetime

## Deviations from Plan

None - plan executed exactly as written. All code (streaming.py, deps.py, main.py, and all 9 tests) matches the plan's `<action>`/`<behavior>` blocks verbatim; no Rule 1-4 triggers encountered.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required. `BIOCLAW_WEB_PASSWORD` remains an environment variable needed at runtime (tests use `monkeypatch.setenv`); Plan 07-03's live_llm checkpoint will need it set for real manual verification.

## Next Phase Readiness

Plan 07-03 (live_llm e2e + human-verify checkpoint) can now:
- Run the real `uvicorn webapp.backend.main:app` with `BIOCLAW_WEB_PASSWORD` set and a real `ANTHROPIC_API_KEY`, exercising the full `POST /api/ask` -> `ask_question()` -> real agent session -> `WS /ws/{stream_id}` path end to end
- Rely on `main.py`, `streaming.py`, and `deps.py` as stable, fully-tested surfaces -- no further changes to this plan's files should be needed for 07-03's live verification

No blockers. Full fast suite (172 tests, excluding `live_llm`/`bio_fm_smoke`/`vcc_data`) confirmed green with `webapp/backend/main.py`/`streaming.py`/`deps.py` added.

---
*Phase: 07-backend-api-streaming-foundation*
*Completed: 2026-09-12*

## Self-Check: PASSED

All created/modified files verified present on disk; both task commits (41909ca, f1682b4) verified present in git history.
