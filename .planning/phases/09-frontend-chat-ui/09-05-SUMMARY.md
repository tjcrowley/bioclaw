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
  - "During Darren's manual browser verification (Task 2), a real bug was found and fixed: login overlay CSS specificity bug (see below). This was fixed under Deviation Rule 1 (auto-fix bugs) — no architectural change, no user decision needed for the fix itself. The human-verify checkpoint task remains NOT complete pending Darren's re-test."

patterns-established: []

requirements-completed: []

# Metrics
duration: ~5min (Task 1) + ~20min (bug investigation/fix/verify during Task 2 checkpoint)
completed: 2026-09-13
---

# Phase 9 Plan 05: Fast-Tier Suite Verification + Human-Verify Checkpoint Summary (PAUSED)

**Full fast-tier suite confirmed green (208 passed, 6 deselected, 0 failed) with all 13 targeted `test_webapp_frontend.py` tests passing; plan is now paused awaiting Darren's manual browser walkthrough of UI-01..UI-07 (Task 2, not yet performed).**

## Performance

- **Duration:** ~5 min (Task 1 automated verification only)
- **Started:** 2026-09-13 (this session)
- **Completed:** Task 1 complete; Task 2 (human-verify) NOT started
- **Tasks:** 1/2 complete
- **Files modified:** 0 (verification-only plan, no code changes)

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

Task 2 (human-verify checkpoint) has **not been executed** — it requires Darren to manually operate a browser and cannot be performed or simulated by the executor.

## Files Created/Modified
None — this plan is verification-only per its frontmatter (`files_modified: []`).

## Decisions Made
None beyond what's in key-decisions above.

## Deviations from Plan

None — plan executed exactly as written up to the checkpoint. The full fast-tier suite passed on the first run with no failures, so no Rule 1-3 auto-fixes were needed.

## Issues Encountered
None.

## Checkpoint: Human Verification Required (NOT YET PERFORMED)

**This plan is PAUSED at Task 2 (`type="manual"`, human-verify checkpoint).** It cannot be completed by an autonomous agent. See the orchestrator response for the full checkpoint report, including:
- Exact commands to start the local backend (binds to `127.0.0.1`/`localhost` only, per the standing local-only constraint)
- The browser URL to open (`http://localhost:8000/app`)
- A checklist of all 7 UI requirements (UI-01..UI-07) to click through and confirm visually

Darren must complete the browser walkthrough and report back ("approved" or a description of what failed) before this plan can be marked complete. No deployment, provisioning, or remote-host action is required or was taken.

## User Setup Required

To perform the pending human-verify step, Darren needs:
- A chosen `BIOCLAW_WEB_PASSWORD` value (any string)
- `ANTHROPIC_API_KEY` set in the environment (for real `ask_question()` calls during the walkthrough — chat responses will not work without it)
- A local browser to visit `http://localhost:8000/app` once the dev server (started locally, per the checkpoint instructions) is running

## Next Phase Readiness

Not ready. Phase 9 cannot be marked complete, STATE.md's Current Plan cannot advance past 09-05, and Phase 10 cannot begin until Darren performs the Task 2 browser walkthrough and signs off. Once approved, a continuation agent should be spawned to finalize this plan (mark Task 2 done, run the final `roadmap update-plan-progress` / `requirements mark-complete` steps for UI-01..UI-07, and produce the final metadata commit).

---
*Phase: 09-frontend-chat-ui*
*Status: PAUSED at human-verify checkpoint (Task 2 of 2) — bug found and fixed during Darren's manual re-test; checkpoint still requires Darren's re-verification and sign-off*

## Self-Check: PASSED (Task 1)

No files were created/modified by Task 1 to verify (verification-only plan). Test run output confirmed directly in this session (208 passed, 6 deselected; 13/13 targeted tests passed). No commit hashes to verify for Task 1 since no commit was made.

---

## Bug Found & Fixed During Human-Verify Checkpoint (Task 2, in progress — distinct from Task 1)

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

Browser-level visual re-verification (does the overlay actually disappear on screen after a correct password) still requires Darren, since this executor has no browser/DOM rendering environment available — this is exactly what the still-pending Task 2 human-verify checkpoint is for.

### Deviation classification

**[Rule 1 - Bug] Login overlay CSS specificity prevented app shell from becoming visible after successful login**
- **Found during:** Task 2 (human-verify checkpoint), reported by Darren during manual browser testing
- **Issue:** `#login-overlay`/`#app` ID-selector `display` rules always beat the UA `[hidden] { display: none }` rule, so toggling `.hidden` from JS had no visual effect
- **Fix:** Added `#login-overlay[hidden], #app[hidden] { display: none; }` to `webapp/frontend/style.css`
- **Files modified:** `webapp/frontend/style.css`
- **Commit:** `04ae403`

This was auto-fixed per Deviation Rule 1 (bug directly caused by/discovered in the current plan's scope, no architectural change, no user decision required for the fix). No user permission was needed to apply it.

### Checkpoint status — STILL PENDING

**The Task 2 human-verify checkpoint is NOT complete.** A bug was found and fixed, but per protocol this executor cannot self-approve a human-verify checkpoint. Darren must:
1. Restart the local dev server (`BIOCLAW_WEB_PASSWORD=... uv run --extra web uvicorn webapp.backend.main:app --port 8000`, binds to localhost only)
2. Re-visit `http://localhost:8000/app` in his browser (hard-refresh / bypass cache to ensure the new `style.css` is loaded, e.g. Cmd+Shift+R)
3. Confirm: wrong password still shows the inline error; correct password now actually transitions to the chat UI (sidebar + composer visible, login overlay gone)
4. Report back "approved" or describe any remaining issue

Only after Darren's explicit sign-off should Task 2 (and this plan, 09-05) be marked complete in STATE.md/ROADMAP.md.

## Self-Check: PASSED (Bug Fix)

- `webapp/frontend/style.css` contains the new `#login-overlay[hidden], #app[hidden] { display: none; }` rule — confirmed via `curl http://127.0.0.1:8009/app/style.css` during verification.
- Commit `04ae403` exists in git history — confirmed via `git log --oneline -1`.
- Fast-tier suite result (208 passed) confirmed directly in this session's pytest output.
