---
phase: 08-session-dataset-endpoints
plan: 01
subsystem: api
tags: [fastapi, sqlite, session-management, dependency-injection]

# Dependency graph
requires:
  - phase: 07-backend-api-streaming-foundation
    provides: FastAPI app skeleton (POST /api/ask, WS /ws/{stream_id}), password auth (require_password), streaming.py, deps.py's get_ask_question() DI pattern, AskRequest/AskResponse schemas
provides:
  - SessionMemory.touch()/list_sessions()/session_exists() backed by a new additive `sessions` table (agent/memory.py)
  - run_session() marks every session as listable the moment it starts, independent of tool-call activity
  - ask_question() and POST /api/ask genuinely forward/resume a known session_id instead of silently discarding it
  - GET /api/sessions (list, password-gated) and GET /api/sessions/{session_id} (detail, 404 for unknown) endpoints
  - SessionSummary/SessionListResponse/UploadResponse Pydantic contracts (UploadResponse reserved for Plan 08-02)
affects: [08-02-dataset-upload-endpoint, webapp-frontend]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Additive SQLite table pattern: new `sessions` table added to existing SessionMemory connection/init without touching the pre-existing `session_memory` table or its methods"
    - "SQLite upsert via INSERT ... ON CONFLICT(session_id) DO UPDATE for idempotent touch() semantics"
    - "get_session_memory() DI factory mirrors get_ask_question(), overridable in tests via app.dependency_overrides"

key-files:
  created: []
  modified:
    - agent/memory.py
    - agent/session.py
    - qa/session.py
    - webapp/backend/deps.py
    - webapp/backend/schemas.py
    - webapp/backend/main.py
    - tests/test_agent_memory.py
    - tests/test_qa_session.py
    - tests/test_webapp_backend.py

key-decisions:
  - "sessions table implemented exactly per plan's provided SQL/code (PRIMARY KEY session_id, upsert-on-touch) -- no deviation needed"
  - "session_memory.touch(session_id) placed immediately after session_id resolution in run_session(), before build_options(), so a zero-tool-call session is still listable"
  - "_fake_ask_question test double upgraded to accept session_id and touch the injected session_memory, exercising real DI wiring end-to-end instead of a hardcoded stub return"

patterns-established:
  - "New session-lifecycle SQLite tables are added additively to SessionMemory's existing connection/init pattern rather than a new store class"
  - "GET endpoints requiring auth follow the same dependencies=[Depends(require_password)] + Depends(deps.get_*) shape as POST /api/ask"

requirements-completed: [API-03]

# Metrics
duration: ~10min
completed: 2026-09-12
---

# Phase 8 Plan 1: Session Listing + session_id Resumption Summary

**GET /api/sessions and GET /api/sessions/{session_id} backed by a new SQLite `sessions` table, plus a fixed POST /api/ask that genuinely resumes a session instead of silently dropping the incoming session_id**

## Performance

- **Duration:** ~10 min
- **Started:** 2026-09-12T13:52:00Z (approx)
- **Completed:** 2026-09-12T13:59:03Z
- **Tasks:** 3
- **Files modified:** 9

## Accomplishments
- `SessionMemory` can now enumerate every session that has started (not just ones with a dataset-producing tool call), most-recently-active first, via a new additive `sessions` table
- `run_session()` calls `session_memory.touch(session_id)` on every invocation, so a session is listable the instant it starts
- `POST /api/ask` now reads `req.session_id` and forwards it end-to-end through `ask_question()` -> `run_session()`, closing the previously-structural gap where session resumption was impossible
- New password-gated `GET /api/sessions` (list) and `GET /api/sessions/{session_id}` (detail, 404 for unknown) endpoints, backed by `SessionMemory`

## Task Commits

Each task was committed atomically:

1. **Task 1: SessionMemory sessions table + touch/list_sessions/session_exists** - `83d02fc` (feat)
2. **Task 2: ask_question() forwards session_id; webapp session contracts** - `5c2c840` (feat)
3. **Task 3: Wire session_id through /api/ask + add GET /api/sessions endpoints** - `d97d0be` (feat)

**Plan metadata:** (pending) `docs(08-01): complete plan`

_Note: tasks were type="auto" tdd="true" for Tasks 1-2 (tests written alongside implementation in the same commit, per plan's provided action blocks) and plain type="auto" for Task 3._

## Files Created/Modified
- `agent/memory.py` - Added additive `sessions` table + `touch()`/`list_sessions()`/`session_exists()` methods
- `agent/session.py` - `run_session()` calls `session_memory.touch(session_id)` once per invocation
- `qa/session.py` - `ask_question()` accepts and forwards `session_id` to `run_session()`
- `webapp/backend/deps.py` - Added `get_session_memory()` DI factory
- `webapp/backend/schemas.py` - Added `SessionSummary`, `SessionListResponse`, `UploadResponse` (last one reserved for Plan 08-02)
- `webapp/backend/main.py` - `ask()` forwards `req.session_id`; added `GET /api/sessions` and `GET /api/sessions/{session_id}` routes
- `tests/test_agent_memory.py` - 5 new tests for touch/list_sessions/session_exists
- `tests/test_qa_session.py` - 1 new test for session_id forwarding
- `tests/test_webapp_backend.py` - Updated `_fake_ask_question` test double + 5 new tests (resume, list metadata, 401, 404, cross-call dataset recall)

## Decisions Made
None beyond what the plan specified -- all code implemented exactly per the plan's provided `<action>` blocks (SQL, method bodies, endpoint handlers, tests). No architectural deviations.

## Deviations from Plan

None - plan executed exactly as written. All three tasks' `<action>` blocks were implemented verbatim, all pre-existing tests in `tests/test_agent_memory.py`, `tests/test_qa_session.py`, and `tests/test_webapp_backend.py` continued to pass unmodified alongside the new tests.

## Issues Encountered

The Edit tool initially rejected edits to `agent/memory.py` and `agent/session.py` with a "file has not been read yet" error despite those files having been read earlier in a parallel batch of Read calls at session start -- resolved by re-reading each file individually immediately before editing it. No impact on outcome.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness
- API-03 ("list existing sessions and resume a session by ID") is now closed and structurally verified by tests
- `UploadResponse` schema is already in place in `webapp/backend/schemas.py`, ready for Plan 08-02 (dataset upload endpoint, API-04) to consume
- Full test suite (183 passed, 5 deselected for live_llm/bio_fm_smoke/vcc_data markers) confirms no regression across the whole codebase

---
*Phase: 08-session-dataset-endpoints*
*Completed: 2026-09-12*

## Self-Check: PASSED

All 9 modified files and the SUMMARY.md itself confirmed present on disk; all 3 task commits (83d02fc, 5c2c840, d97d0be) confirmed present in git log.
