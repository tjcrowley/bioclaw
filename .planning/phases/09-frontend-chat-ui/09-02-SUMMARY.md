---
phase: 09-frontend-chat-ui
plan: 02
subsystem: ui
tags: [javascript, es-modules, fetch, websocket, frontend-api-client]

# Dependency graph
requires:
  - phase: 09-frontend-chat-ui
    provides: "09-01's stub api.js (exported function names only) and the StaticFiles mount serving webapp/frontend/ at /app"
provides:
  - "Complete webapp/frontend/api.js ES module: login, askQuestion, openToolStream, listSessions, getSession, uploadDataset"
  - "Shared _fetch() 401 handling contract (dispatches bioclaw:unauthorized CustomEvent) that all future frontend modules can rely on"
  - "WebSocket manager pattern for /ws/{stream_id} that relies on automatic browser cookie forwarding, no query-string auth"
affects: [09-03, 09-04, 09-05]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "api.js is the single fetch/WS boundary for the frontend; no other module calls fetch() or WebSocket() directly"
    - "_fetch() wrapper centralizes credentials:'include' and 401 -> bioclaw:unauthorized CustomEvent dispatch"
    - "openToolStream() returns {close()} handle; caller owns the WS lifecycle, module never holds global WS state"

key-files:
  created: []
  modified:
    - webapp/frontend/api.js

key-decisions:
  - "Implemented api.js exactly per plan's provided code (no deviations needed)"

patterns-established:
  - "WS URL built from location.protocol/location.host at call time (ws: vs wss: based on page protocol) rather than hardcoding — works in both local http dev and future https deployment without code changes"

requirements-completed: [UI-02]

# Metrics
duration: ~2min
completed: 2026-09-13
---

# Phase 9 Plan 02: Frontend API Client Module Summary

**Complete `webapp/frontend/api.js` ES module wrapping all six backend endpoints (login, ask, sessions list/get, upload, WS tool stream) behind a single `credentials:'include'` + 401-event contract.**

## Performance

- **Duration:** ~2 min
- **Started:** 2026-09-13T07:21:42Z
- **Completed:** 2026-09-13T07:22:57Z
- **Tasks:** 1
- **Files modified:** 1

## Accomplishments
- Overwrote the 09-01 stub `webapp/frontend/api.js` with the full API client: `login`, `askQuestion`, `openToolStream`, `listSessions`, `getSession`, `uploadDataset`
- Centralized 401 handling via a shared `_fetch()` helper that dispatches `bioclaw:unauthorized` on `window`
- `openToolStream()` opens a browser WebSocket to `ws[s]://${location.host}/ws/{streamId}` relying on automatic cookie forwarding on the WS upgrade request — no password ever appears in the URL
- `uploadDataset()` passes a raw `FormData` body with no manual `Content-Type` header, letting the browser set the multipart boundary

## Task Commits

Each task was committed atomically:

1. **Task 1: Create webapp/frontend/api.js — complete API client module** - `b50786a` (feat)

**Plan metadata:** (this commit, docs)

## Files Created/Modified
- `webapp/frontend/api.js` - Complete API client: fetch wrappers for /api/login, /api/ask, /api/sessions, /api/sessions/{id}, /api/upload, plus a WebSocket manager for /ws/{stream_id}

## Decisions Made
None - plan's provided code implemented verbatim, matching the exact interfaces contract (function names, request shapes, credential mode) specified in the plan frontmatter and `<action>` block.

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness
- `webapp/frontend/api.js` is now the stable, complete import surface for Plan 09-03 (chat.js, executing concurrently against a different file) and Plan 09-04 (sessions.js/citations.js)
- Both required verification commands pass: the two targeted `test_webapp_frontend.py` tests, and the full fast suite (208 passed, 6 deselected)
- No blockers for downstream Phase 9 plans

---
*Phase: 09-frontend-chat-ui*
*Completed: 2026-09-13*

## Self-Check: PASSED

- FOUND: webapp/frontend/api.js
- FOUND: b50786a (commit)
- FOUND: askQuestion export in api.js text
