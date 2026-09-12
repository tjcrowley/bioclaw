---
phase: 08-session-dataset-endpoints
plan: 03
subsystem: api
tags: [fastapi, claude-agent-sdk, live_llm, session-memory, upload, citations]

# Dependency graph
requires:
  - phase: 08-session-dataset-endpoints (08-01/08-02)
    provides: GET /api/sessions[/{id}] (SessionMemory-backed session list/resume) and POST /api/upload (multipart .h5/.mtx staging + ingest_10x wiring + SessionMemory dataset-reference recording)
provides:
  - A live_llm end-to-end test proving a real upload's dataset_id is recalled and actually analyzed (not just quoted) by a real agent turn in the same session
  - A fix making upload-recalled datasets citable: QA_SYSTEM_PROMPT and SYSTEM_PROMPT/_recall_preamble now tell the model a "(Session context: ...)" dataset is a legitimate, already-verified input it must act on with a tool call, not refuse
  - Confirmed localhost-only operation of the full session/upload API surface (401 unauthenticated, 200 authenticated) against a single-worker uvicorn process
affects: [09-frontend-chat-ui]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Session-recalled dataset context must be framed in the system prompt as a legitimate, pre-verified input the model should act on directly, not as an unverified claim requiring refusal under anti-hallucination rules"
    - "live_llm test assertions on tool-backed answers must check for a resolved [ref:tool:...] citation, not a substring match on an id that could appear in a refusal message"

key-files:
  created:
    - tests/test_webapp_session_upload_integration.py
  modified:
    - qa/session.py
    - agent/session.py

key-decisions:
  - "Root cause of the checkpoint's first failure: POST /api/upload writes directly into SessionMemory via ingest_10x(), bypassing the PostToolUse hook/audit-log path that QA_SYSTEM_PROMPT's citation requirement assumed always produced session context -- the model correctly followed its own anti-hallucination rule and refused to treat an untooled dataset_id as verified. Fixed by explicitly carving out session-recalled datasets as a legitimate exception in the prompt, not by weakening the anti-hallucination rule itself."
  - "Corrected a latent test bug (not just a prompt bug): analyze_dataset() itself writes a NEW store version as its output (Phase 2 versioning behavior), so the exact upload-time dataset_id string (e.g. webapp-e2e-upload@1) can never appear verbatim in a real tool-backed answer (the citable output is webapp-e2e-upload@2). The assertion was corrected to check the version-independent dataset name plus a resolved analyze_dataset citation, instead of the impossible exact-id substring match."

patterns-established:
  - "When a system prompt teaches the model to refuse acting on data it can't verify, any new code path that injects context outside the normal tool-call/audit-log flow (e.g. direct-write endpoints like POST /api/upload) must be explicitly exempted in that same prompt, or the model will correctly refuse it as unverifiable."

requirements-completed: [API-03, API-04]

# Metrics
duration: ~2min active work (Task 1) + checkpoint cycle spanning ~4h wall-clock (live_llm test run, root-cause diagnosis, fix, two user-run re-verifications against the real Anthropic API)
completed: 2026-09-12
---

# Phase 8 Plan 03: Live end-to-end session/upload verification + citability fix Summary

**Fixed a real anti-hallucination refusal bug uncovered by the phase-8 live_llm checkpoint -- upload-recalled datasets are now citable, not just quotable -- closing Phase 8 (API-03/API-04) with a real Claude Agent SDK pass.**

## Performance

- **Duration:** ~2 min for Task 1 (test authoring); checkpoint cycle (live run -> diagnosis -> fix -> two verified re-runs) spanned the same session, roughly 4h wall-clock between the two commits
- **Started:** 2026-09-12T07:13:14-07:00 (Task 1 commit)
- **Completed:** 2026-09-12T11:18:36-07:00 (checkpoint fix commit, final approval)
- **Tasks:** 2 (1 auto, 1 checkpoint:human-verify)
- **Files modified:** 3 (1 created, 2 modified in the checkpoint fix)

## Accomplishments
- Wrote and committed `tests/test_webapp_session_upload_integration.py`, a single `live_llm`-marked test driving the real (non-dependency-overridden) FastAPI app through a real `POST /api/upload` -> real `POST /api/ask` (same `session_id`) -> real `GET /api/sessions`
- First live run technically passed pytest but exposed a genuine product bug: the real agent refused to analyze the upload-recalled `dataset_id`, correctly citing its own anti-hallucination rule, because `POST /api/upload` bypasses the `PostToolUse` hook/audit-log path that rule assumed existed
- Fixed the root cause in `qa/session.py` (`QA_SYSTEM_PROMPT`) and `agent/session.py` (`SYSTEM_PROMPT`/`_recall_preamble`): a dataset surfaced via `(Session context: ...)` is now explicitly framed as a legitimate, already-verified input, and the model is instructed to call the appropriate tool on it directly to produce a citable result
- Strengthened the test's own assertions: replaced a weak `dataset_id in answer` substring check (which passed even on a refusal message that happened to quote the id) with a check for a resolved `analyze_dataset` citation, and corrected the dataset-id assertion to the version-independent name (since `analyze_dataset` writes a new store version, e.g. recalled `webapp-e2e-upload@1` in, cited `webapp-e2e-upload@2` out -- pre-existing Phase 2 versioning behavior)
- Re-verified live against the real Anthropic API twice by the user: the model genuinely called `analyze_dataset`, cited a resolved `[ref:mcp__bioclaw__analyze_dataset:...]` tool result, and reported real cluster/variance figures (2 clusters, 60 cells, PC1 27.1% variance), including honest transparency about the `@1`/`@2` version drift
- Manually verified localhost-only operation: unauthenticated `GET /api/sessions` against a local single-worker uvicorn process (127.0.0.1:8124) returned 401; the same request with `?password=` returned 200 with real session data. No deployment, provisioning, or remote host was touched
- Full fast test suite green (193 passed, 6 deselected) as of the final check
- Phase 8 (Session & Dataset Endpoints) is now complete; API-03 and API-04 closed

## Task Commits

Each task was committed atomically:

1. **Task 1: Write the live_llm session/upload end-to-end integration test** - `3b8a516` (test)
2. **Checkpoint fix: make upload-recalled datasets citable, not just quotable** - `a2bb07d` (fix)

**Plan metadata:** (this commit) - `docs(08-03): complete phase gate checkpoint`

## Files Created/Modified
- `tests/test_webapp_session_upload_integration.py` - Single `live_llm`-marked test: real upload -> real ask (same session_id) -> real session list; asserts on a resolved `analyze_dataset` citation and the version-independent dataset name, not an exact-id substring match
- `qa/session.py` - `QA_SYSTEM_PROMPT` updated to carve out session-recalled datasets as a legitimate, already-verified input requiring direct tool use, not refusal
- `agent/session.py` - `SYSTEM_PROMPT`/`_recall_preamble` updated with the same clarification for the base agent session path

## Decisions Made
- Anti-hallucination refusal was the correct behavior of the *existing* prompt given an *unaudited* input path -- the fix strengthens the prompt's carve-out rather than weakening the anti-hallucination rule itself, preserving QA-01/QA-02's guarantees from Phase 6
- The exact upload-time `dataset_id` can never appear verbatim in a real tool-backed answer once `analyze_dataset` is actually invoked (it produces a new store version as output); the test's success criterion was corrected to match real, correct tool-backed behavior instead of an assumption that was already false under Phase 2's versioning model

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Upload-recalled dataset context triggered anti-hallucination refusal**
- **Found during:** Task 2 (checkpoint: first live_llm test run against the real Anthropic API)
- **Issue:** `POST /api/upload` writes directly to `SessionMemory` via `ingest_10x()`, with no agent/LLM/tool-call involvement. `QA_SYSTEM_PROMPT`'s anti-hallucination rule required the model to have invoked a tool in-session before treating a referenced dataset as verified; the model correctly refused to analyze the upload-recalled `dataset_id` since, from its perspective, no tool call had produced it.
- **Fix:** Updated `QA_SYSTEM_PROMPT` (`qa/session.py`) and `SYSTEM_PROMPT`/`_recall_preamble` (`agent/session.py`) to explicitly state that a dataset surfaced via `(Session context: ...)` is a legitimate, already-verified input, and instruct the model to call the appropriate tool on it directly to produce its own citable result.
- **Files modified:** `qa/session.py`, `agent/session.py`
- **Verification:** Re-run live against the real Anthropic API (twice, by Darren): model called `analyze_dataset`, cited a resolved `[ref:mcp__bioclaw__analyze_dataset:...]` result, reported real figures -- 1 passed both times.
- **Committed in:** `a2bb07d`

**2. [Rule 1 - Bug] Test assertion required an impossible exact dataset_id match**
- **Found during:** Task 2 (checkpoint: diagnosing the first live_llm run alongside the prompt bug above)
- **Issue:** The test asserted the exact upload-time `dataset_id` string (e.g. `webapp-e2e-upload@1`) would appear verbatim in the agent's answer. This can never happen for a genuinely tool-backed answer: `analyze_dataset` writes a NEW store version as its output (pre-existing Phase 2 versioning behavior), so a correct answer cites `webapp-e2e-upload@2`, not `@1`. The original weak assertion (`dataset_id in answer`) only ever passed because a refusal message happened to quote the input id verbatim.
- **Fix:** Replaced the substring check with an assertion that the answer contains a resolved `analyze_dataset` citation, and checks the version-independent dataset name (`webapp-e2e-upload`) rather than the exact versioned id.
- **Files modified:** `tests/test_webapp_session_upload_integration.py`
- **Verification:** Live_llm test passed twice against the real API with the corrected assertions.
- **Committed in:** `a2bb07d`

---

**Total deviations:** 2 auto-fixed (2 bugs, both surfaced only by the live_llm checkpoint against the real Claude Agent SDK)
**Impact on plan:** Both fixes were necessary for the phase's actual success criterion (real agent recall + real tool-backed analysis of an uploaded dataset) to be genuinely true rather than only superficially passing pytest. No scope creep -- both fixes are scoped exactly to the citability gap this checkpoint exists to catch.

## Issues Encountered
- The first live_llm test run "passed" pytest while masking a real product bug (the model's answer happened to quote the refused dataset_id, satisfying the original weak assertion). This is exactly the failure mode Phase 8's live_llm checkpoint (mirroring Phase 6/7's own live_llm checkpoint pattern) exists to catch before a fake/spy-only fast-tier suite could ever surface it. Resolved via the two fixes above; re-verified live twice more before approval.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness
- Phase 8 (Session & Dataset Endpoints) is complete: `GET /api/sessions[/{id}]` (API-03) and `POST /api/upload` (API-04) are both implemented, fast-tier tested, and now live-verified end to end against the real Claude Agent SDK, including the specific case (upload-recalled context) that structurally differs from the audited tool-call path Phase 6/7's citation protocol was originally built around.
- The prompt fix in `qa/session.py`/`agent/session.py` is a general capability (any future session-context-injection path benefits from the same carve-out), not upload-specific -- worth keeping in mind if Phase 9/10 introduce other non-tool-call context injection points.
- No blockers for Phase 9 (Frontend Chat UI), which consumes this now-complete Phase 7+8 API surface.

---
*Phase: 08-session-dataset-endpoints*
*Completed: 2026-09-12*
