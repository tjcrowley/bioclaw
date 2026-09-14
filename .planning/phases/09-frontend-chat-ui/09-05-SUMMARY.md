---
phase: 09-frontend-chat-ui
plan: 05
subsystem: testing
tags: [pytest, fastapi-testclient, integration-gate, checkpoint]

# Dependency graph
requires:
  - phase: 09-frontend-chat-ui
    provides: "09-01..09-04's complete frontend (index.html/style.css/api.js/chat.js/citations.js/sessions.js/main.js) and login endpoint, verified together here"
provides:
  - "Confirmed-green fast-tier test suite (208 passed, 6 deselected) with zero regressions across the full project"
  - "Confirmed-green tests/test_webapp_frontend.py (15/15), including all 13 tests explicitly enumerated in the plan's coverage table"
  - "Requirement-to-test coverage mapping for UI-01..UI-07 (see table below), each backed by at least one passing automated test"
affects: [10-verification-launch]

# Tech tracking
tech-stack:
  added: []
  patterns: []

key-files:
  created: []
  modified:
    - "webapp/frontend/style.css (bug fix found during Darren's human-verify pass — see 'Bug Found & Fixed' section below)"

key-decisions:
  - "No code changes made in Task 1 (as specified) — Task 1 is a pure verification run; zero deviations were needed since the full suite passed on first run"
  - "During Darren's manual browser verification (Task 2), a real bug was found and fixed: login overlay CSS specificity bug (see below). This was fixed under Deviation Rule 1 (auto-fix bugs) — no architectural change, no user decision needed for the fix itself."
  - "Darren re-tested in his browser after the CSS fix (commit 04ae403) and replied 'approved' on 2026-09-13 — login gate, dark theme, chat thread, live activity, citations, session sidebar, and upload all confirmed working. Task 2 (human-verify checkpoint) is now complete; Phase 9 (UI-01..UI-07) is complete."

patterns-established: []

requirements-completed: [UI-01, UI-02, UI-03, UI-04, UI-05, UI-06, UI-07]

# Metrics
duration: ~5min (Task 1) + ~20min (bug investigation/fix/verify) + human re-verification turnaround
completed: 2026-09-13
---

# Phase 9 Plan 05: Fast-Tier Suite Verification + Human-Verify Checkpoint Summary

**Full fast-tier suite confirmed green (208 passed, 6 deselected, 0 failed) with all 13 targeted `test_webapp_frontend.py` tests passing; Darren completed the manual browser walkthrough of UI-01..UI-07 and replied "approved" after the CSS fix. Phase 9 is complete.**

## Performance

- **Duration:** ~5 min (Task 1 automated verification) + ~20 min (bug fix cycle) + human re-verification turnaround
- **Started:** 2026-09-13 (this session)
- **Completed:** 2026-09-13 — both tasks complete, checkpoint approved by Darren
- **Tasks:** 2/2 complete
- **Files modified:** 1 (`webapp/frontend/style.css` — bug fix, see below)

## Accomplishments
- Ran `uv run --extra web pytest tests/ -x -q -m "not live_llm and not bio_fm_smoke and not vcc_data"` — **208 passed, 6 deselected, 0 failed, 74 warnings** (all pre-existing/benign deprecation warnings from scanpy/polars/cell_eval, unrelated to Phase 9)
- Ran all 13 explicitly-named tests from the plan's verification list individually — **13 passed, 0 failed**
- Confirmed no regression in any pre-existing test file (all Phase 1-8 tests still green alongside the new Phase 9 frontend tests)

### Requirement coverage confirmed

| Requirement | Test(s) | Result |
|---|---|---|
| UI-01 | `test_chat_js_exports` (sendMessage, appendMessage) | PASSED |
| UI-02 | `test_chat_js_exports` (renderActivityEvent) + `test_api_js_exports` (openToolStream) | PASSED |
| UI-03 | `test_citations_js_exports` | PASSED |
| UI-04 | `test_sessions_js_exports` | PASSED |
| UI-05 | `test_api_js_exports` (uploadDataset) | PASSED |
| UI-06 | `test_login_page_served`, `test_login_sets_cookie`, `test_login_rejects_bad_password`, `test_login_no_prior_auth_required` | PASSED |
| UI-07 | `test_css_design_tokens`, `test_login_page_served` | PASSED |

All seven requirements have at least one passing automated test. This closes the automated half of the plan's success criteria.

## Task Commits

Task 1 made no code changes (pure verification run, per plan's `<objective>`: "No code changes are made in this plan"). No commit was created for Task 1 — nothing to stage. This SUMMARY.md and STATE.md updates are the only artifacts of this session, committed as plan metadata below.

Task 2 (human-verify checkpoint) required Darren to manually operate a browser and could not be performed or simulated by the executor. Darren completed it in two passes (first pass found the CSS bug fixed in 04ae403, second pass confirmed the fix and replied "approved") — see "Checkpoint: Human Verification — APPROVED" below.

## Files Created/Modified
- `webapp/frontend/style.css` — bug fix during Task 2 checkpoint (see "Bug Found & Fixed" section below); no other files modified. This plan is otherwise verification-only per its frontmatter (`files_modified: []`).

## Decisions Made
None beyond what's in key-decisions above.

## Deviations from Plan

None — plan executed exactly as written up to the checkpoint. The full fast-tier suite passed on the first run with no failures, so no Rule 1-3 auto-fixes were needed.

## Issues Encountered
None.

## Checkpoint: Human Verification — APPROVED

**Task 2 (`type="manual"`, human-verify checkpoint) is complete.** Darren's first browser walkthrough surfaced the login-overlay CSS bug documented below; after the fix (commit 04ae403) he restarted the local backend, hard-refreshed `http://localhost:8000/app`, re-ran the full UI-01..UI-07 checklist, and replied **"approved"** on 2026-09-13.

Confirmed working in the browser:
- UI-06 (login gate): unauthenticated load shows only the login overlay; wrong password shows inline error with chat UI hidden; correct password now correctly transitions to the chat UI (the bug this checkpoint caught)
- UI-07 (dark theme): dark background, left sidebar + main panel layout resembling OpenClaw's own UI
- UI-01 (chat thread): question/answer bubbles render correctly
- UI-02 (live activity): tool-call activity panel appears during agent work and clears on answer arrival
- UI-03 (citations): citation buttons render (not raw `[ref:...]` text) and open the audit-log detail view
- UI-04 (session sidebar): past sessions list and resume-session flow work
- UI-05 (upload): file picker/drag-drop upload flow surfaces progress and result in the thread

No deployment, provisioning, or remote-host action was required or taken — verification was entirely local (`127.0.0.1`/`localhost`).

## User Setup Required

Darren performed the human-verify step using:
- A chosen `BIOCLAW_WEB_PASSWORD` value
- `ANTHROPIC_API_KEY` set in the environment (for real `ask_question()` calls during the walkthrough)
- A local browser at `http://localhost:8000/app` against the locally-run dev server

No further setup is required — the checkpoint is closed.

## Next Phase Readiness

Ready. Phase 9 (UI-01..UI-07) is complete — all seven requirements have both a passing automated test and a Darren-approved manual browser verification. STATE.md's Current Plan advances past 09-05, and Phase 10 (Packaging & Local Verification) may begin.

---
*Phase: 09-frontend-chat-ui*
*Status: COMPLETE — human-verify checkpoint approved by Darren on 2026-09-13 after the CSS fix (commit 04ae403)*

## Self-Check: PASSED (Task 1)

No files were created/modified by Task 1 to verify (verification-only plan). Test run output confirmed directly in this session (208 passed, 6 deselected; 13/13 targeted tests passed). No commit hashes to verify for Task 1 since no commit was made.

---

## Bug Found & Fixed During Human-Verify Checkpoint (Task 2 — distinct from Task 1)

While Darren was performing the Task 2 manual browser walkthrough at `http://localhost:8000/app`, he reported:

> "incorrect password says 'incorrect password' but the correct password sends me back to the password form."

Server-side uvicorn access logs from his test session showed `POST /api/login` → 200, `GET /app/` → 200/304, `GET /api/sessions` → 200 (not 401) immediately after login — proving the backend auth flow (cookie set + accepted on the next request) was already correct. The bug was isolated to the frontend.

### Root cause

`webapp/frontend/style.css` declared `#login-overlay { display: flex; ... }` and `#app { display: grid; ... }` using ID selectors (CSS specificity `1,0,0`). The browser's built-in UA stylesheet rule `[hidden] { display: none }` is an attribute selector (specificity `0,1,0`) — lower than an ID selector. So when `main.js`'s `showApp()` set `loginOverlay.hidden = true` after a successful login, the `hidden` attribute was correctly applied to the DOM, but it had **no visual effect**: the ID selector's own `display: flex` declaration continued to win and render the overlay on top (`z-index: 100`), fully obscuring the app shell underneath — even though the app shell itself (`#app`) was correctly un-hidden and the session list had loaded successfully.

This explains the asymmetry Darren observed:
- **Wrong password:** `loginError.hidden = false` shows `#login-error`, which has no competing `display` rule in CSS — this worked correctly, hence "incorrect password" displayed as expected.
- **Correct password:** `showApp()` ran correctly (auth state, DOM structure, session data were all fine) but the overlay never visually disappeared, making it look exactly like being "sent back to the password form."

The bug was purely a CSS specificity conflict — no JS logic, no backend auth logic, no cookie/SameSite issue was involved.

### Fix

Minimal CSS addition to `webapp/frontend/style.css` (7 lines): added `#login-overlay[hidden], #app[hidden] { display: none; }` — an ID+attribute compound selector with specificity `1,1,0`, which now correctly out-specifies the base `#login-overlay`/`#app` `display` rules and lets the `hidden` DOM property control visibility as `main.js` intends.

**Files modified:** `webapp/frontend/style.css`
**Commit:** `04ae403` — `fix(09-05): login overlay stays visible after successful login`

### Verification performed

1. **Full fast-tier suite re-run:** `uv run --extra web pytest tests/ -x -q -m "not live_llm and not bio_fm_smoke and not vcc_data"` → **208 passed, 6 deselected, 0 failed** — no regressions from the CSS-only change (no test in the fast-tier suite exercises rendered CSS, as expected).
2. **Backend curl cookie-jar test** (local server on `127.0.0.1:8009`, `BIOCLAW_WEB_PASSWORD` set locally, no deployment):
   - Wrong password → `401`
   - Correct password → `200` + `Set-Cookie: session=...; HttpOnly`
   - `GET /api/sessions` with saved cookie → `200` with real session data
   - `GET /api/sessions` with no cookie → `401`
   - This independently reconfirmed the backend auth flow was never broken, isolating the bug entirely to the CSS layer.
3. **Served-asset check:** `curl http://127.0.0.1:8009/app/style.css` confirmed the new `[hidden]` override rules are present in what the browser will actually load.

Browser-level visual re-verification (does the overlay actually disappear on screen after a correct password) required Darren, since this executor has no browser/DOM rendering environment available — this is exactly what the Task 2 human-verify checkpoint was for, and it has now been completed (see "Checkpoint: Human Verification — APPROVED" above).

### Deviation classification

**[Rule 1 - Bug] Login overlay CSS specificity prevented app shell from becoming visible after successful login**
- **Found during:** Task 2 (human-verify checkpoint), reported by Darren during manual browser testing
- **Issue:** `#login-overlay`/`#app` ID-selector `display` rules always beat the UA `[hidden] { display: none }` rule, so toggling `.hidden` from JS had no visual effect
- **Fix:** Added `#login-overlay[hidden], #app[hidden] { display: none; }` to `webapp/frontend/style.css`
- **Files modified:** `webapp/frontend/style.css`
- **Commit:** `04ae403`

This was auto-fixed per Deviation Rule 1 (bug directly caused by/discovered in the current plan's scope, no architectural change, no user decision required for the fix). No user permission was needed to apply it.

### Checkpoint status — APPROVED

**The Task 2 human-verify checkpoint is complete.** Darren restarted the local dev server, hard-refreshed `http://localhost:8000/app` to load the new CSS, re-ran the full UI-01..UI-07 checklist, and confirmed: wrong password still shows the inline error; correct password now correctly transitions to the chat UI (sidebar + composer visible, login overlay gone). He replied "approved" on 2026-09-13.

This plan (09-05) and Phase 9 (UI-01..UI-07) are now both complete in STATE.md/ROADMAP.md.

## Self-Check: PASSED (Bug Fix)

- `webapp/frontend/style.css` contains the new `#login-overlay[hidden], #app[hidden] { display: none; }` rule — confirmed via `curl http://127.0.0.1:8009/app/style.css` during verification.
- Commit `04ae403` exists in git history — confirmed via `git log --oneline -1`.
- Fast-tier suite result (208 passed) confirmed directly in this session's pytest output.

## Self-Check: PASSED (Checkpoint Finalization)

- Darren's literal response to the re-verification request was "approved" (see resume_instructions of this finalization pass) — no ambiguity, no reported failures.
- Commits `04ae403` and `d49c541` (CSS fix + related follow-up) exist in git history.
- REQUIREMENTS.md already lists UI-01..UI-07 as Complete under Phase 9 (traceability table).
- ROADMAP.md's Phase 9 row now shows 5/5 plans complete via `roadmap update-plan-progress 9`.
