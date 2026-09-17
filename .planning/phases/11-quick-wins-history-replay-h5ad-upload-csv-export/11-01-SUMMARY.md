---
phase: 11-quick-wins-history-replay-h5ad-upload-csv-export
plan: "01"
subsystem: database
tags: [sqlite, wal, session-memory, history-replay, fastapi, vanilla-js]

# Dependency graph
requires: []
provides:
  - SQLite messages table in SessionMemory with WAL mode and 64 KB content cap
  - add_message() and get_messages() methods on SessionMemory
  - MessageRecord Pydantic schema
  - GET /api/sessions/{id} returns messages array
  - POST /api/ask stores user + assistant turns per conversation
  - sessions.js resumeSession() replays full message history on resume
affects:
  - 11-quick-wins-history-replay-h5ad-upload-csv-export
  - Phase 12 DATA-01 (messages table is the persistence layer DATA-01 builds on)

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "SQLite WAL mode enabled in _connect() for all SessionMemory connections"
    - "Content cap enforced at Python string-length level (not bytes) before INSERT"
    - "Pydantic MessageRecord wraps raw dict rows from get_messages()"
    - "JS history replay: loop over summary.messages with fallback to dataset hint"

key-files:
  created:
    - tests/test_agent_memory.py (6 new HIST-01 tests added)
    - tests/test_webapp_backend.py (3 new HIST-01 integration tests added)
  modified:
    - agent/memory.py
    - webapp/backend/schemas.py
    - webapp/backend/main.py
    - webapp/frontend/sessions.js

key-decisions:
  - "WAL mode set in _connect() — idempotent PRAGMA, applies to every connection automatically"
  - "Content cap at 64 KB character count (not bytes) matches HIST-01 success criteria"
  - "touch() called before add_message() in ask() to ensure session is listed even for ask-only sessions"
  - "Citations not stored in messages table — replay renders assistant messages as plain text (intentional per research guidance)"
  - "Fallback to dataset context hint preserved for pre-HIST-01 sessions with no stored messages"

patterns-established:
  - "TDD pattern: RED tests first (must fail), then GREEN implementation, then run full suite"
  - "Messages isolated per session_id via WHERE clause on session_id column"

requirements-completed:
  - HIST-01

# Metrics
duration: 3min
completed: 2026-09-17
---

# Phase 11 Plan 01: History Replay Summary

**SQLite messages table with WAL mode and 64 KB cap enables full Q&A history replay when a researcher resumes a session**

## Performance

- **Duration:** 3 min
- **Started:** 2026-09-17T00:54:24Z
- **Completed:** 2026-09-17T00:57:35Z
- **Tasks:** 3
- **Files modified:** 6

## Accomplishments
- Added messages table to SessionMemory with WAL mode and 64 KB per-entry content cap; add_message() and get_messages() implemented with 6 unit tests
- Enriched GET /api/sessions/{id} to return messages array; POST /api/ask now stores both user and assistant turns per conversation turn
- Replaced the static "Resuming session..." placeholder in sessions.js with a history replay loop that re-renders all prior Q&A turns in order

## Task Commits

Each task was committed atomically:

1. **Task 1: Add messages table, WAL mode, add_message(), get_messages()** - `4b51cd4` (feat)
2. **Task 2: Enrich API schema, store turns in POST /api/ask, return messages from GET /api/sessions/{id}** - `2fa432a` (feat)
3. **Task 3: Replace JS placeholder with full history replay in sessions.js** - `5b4c4c7` (feat)

**Plan metadata:** (docs commit follows)

## Files Created/Modified
- `agent/memory.py` - Added _CREATE_MESSAGES_TABLE_SQL, _CONTENT_CAP, WAL mode in _connect(), add_message(), get_messages()
- `webapp/backend/schemas.py` - Added MessageRecord model; added messages field to SessionSummary
- `webapp/backend/main.py` - Imported MessageRecord; get_session() enriched with messages; ask() stores turns and calls touch()
- `webapp/frontend/sessions.js` - resumeSession() replaced with history replay loop + fallback
- `tests/test_agent_memory.py` - 6 new HIST-01 unit tests (WAL, add/retrieve, 64 KB cap, ordering, isolation)
- `tests/test_webapp_backend.py` - 3 new HIST-01 integration tests (messages returned, empty for new session, ask stores both roles)

## Decisions Made
- WAL mode in _connect() makes it idempotent — every connection automatically gets WAL without callers needing to manage it
- Content cap enforced at Python string-length level (not bytes) per HIST-01 specification
- touch() called before add_message() in ask() to ensure ask-only sessions (no uploads) are still listed in session sidebar
- Citations omitted from history replay — appendMessage renders assistant turns as plain text; citation links only appear for live responses

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

A pre-existing RED test (`test_export_csv_returns_zip`) from plan 11-03 was already failing at the start of execution — this is out of scope for this plan and was noted but not modified. All 38 tests covering plans 11-01 scope (test_agent_memory.py + test_webapp_backend.py) pass.

## User Setup Required

None - no external service configuration required. SQLite WAL mode is self-configuring.

## Next Phase Readiness

- Session history persistence complete; plan 11-02 (h5ad upload, DATA-02) can proceed independently
- Plan 11-03 (CSV export, EXPORT-01) can proceed independently
- Phase 12 DATA-01 has the messages table available as the persistence layer it depends on

---
*Phase: 11-quick-wins-history-replay-h5ad-upload-csv-export*
*Completed: 2026-09-17*
