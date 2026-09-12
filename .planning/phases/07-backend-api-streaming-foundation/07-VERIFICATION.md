---
phase: 07-backend-api-streaming-foundation
verified: 2026-09-12T00:00:00Z
status: passed
score: 8/8 must-haves verified
---

# Phase 7: Backend API + Streaming Foundation Verification Report

**Phase Goal:** Build the FastAPI backend that wraps qa/session.py::ask_question() with password-gated HTTP and WebSocket endpoints, including live streaming of tool-call activity to connected clients via an additive extra_hooks mechanism.
**Verified:** 2026-09-12
**Status:** passed
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | Existing agent/qa session tests still pass unmodified after adding extra_hooks | ✓ VERIFIED | `tests/test_agent_session_wiring.py`/`tests/test_qa_session.py` pass alongside new tests; 172 total fast-tier tests pass |
| 2 | A caller can pass extra PostToolUse hook callables into ask_question()/run_session()/build_options() and have them invoked alongside existing hooks | ✓ VERIFIED | `agent/session.py::build_options()` builds `hooks = [_make_log_hook(...), record_dataset_reference(...)]; hooks.extend(extra_hooks or [])`; `run_session()`/`ask_question()` forward `extra_hooks` unchanged; covered by `test_build_options_appends_extra_hooks`, `test_ask_question_forwards_extra_hooks` |
| 3 | Any backend route request without the correct shared password is rejected, via a single timing-safe check reusable by both HTTP and WebSocket routes | ✓ VERIFIED | `webapp/backend/auth.py::_valid()` uses `secrets.compare_digest`; `require_password`/`require_password_ws` both call it; `test_ask_rejected_without_password` (401) and `test_ws_rejected_without_password` (policy violation) pass |
| 4 | A client can POST a natural-language question to /api/ask and receive back the agent's answer, sourced from ask_question() | ✓ VERIFIED | `webapp/backend/main.py::ask()` calls injected `ask_question()` and returns `AskResponse`; `test_ask_returns_answer` passes; live `test_ask_streams_real_tool_events_end_to_end` (live_llm) collects correctly and is documented as passed by Darren in 07-03-SUMMARY.md checkpoint resolution |
| 5 | A client connected over WebSocket to /ws/{stream_id} before the correlated POST receives tool-call activity events as they happen, not only the final answer | ✓ VERIFIED | `main.py`'s WS handler drains `streaming.get_or_create_queue(stream_id)`; `make_stream_hook` enqueues events during the POST; `test_ask_streams_tool_events` proves WS-before-POST ordering with a fake agent; live test confirms same behavior against real SDK per checkpoint |
| 6 | A request to /api/ask or /ws/{stream_id} without the correct shared password is rejected (HTTP 401 / WS policy-violation) | ✓ VERIFIED | Same as #3, applied at the route level via `Depends(require_password)` / `Depends(require_password_ws)` |
| 7 | A request presenting the correct shared password (header, query param, or cookie) succeeds against the same routes | ✓ VERIFIED | `test_ask_returns_answer` (Bearer header), `test_ask_streams_tool_events`/live test (`?password=` query param on WS) both succeed |
| 8 | The backend runs and is fully verifiable on localhost only — no deployment step performed | ✓ VERIFIED (human-confirmed) | 07-03-SUMMARY.md documents Darren's checkpoint: server bound to `127.0.0.1:8000` only, curl checks returned 401/200 as expected, no deployment tooling invoked |

**Score:** 8/8 truths verified

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `agent/session.py` | `extra_hooks` kwarg on `build_options()`/`run_session()`, additive | ✓ VERIFIED | Present exactly as specified; default `None`; appended not replacing |
| `qa/session.py` | `extra_hooks` kwarg on `ask_question()`, forwarded | ✓ VERIFIED | Present; forwarded to `run_session()` alongside `session_memory`/`log_path`/`system_prompt` |
| `webapp/backend/__init__.py` | package marker | ✓ VERIFIED | Present, empty |
| `webapp/backend/schemas.py` | `AskRequest`/`AskResponse`/`ToolEvent` | ✓ VERIFIED | All three Pydantic models present, matching spec exactly |
| `webapp/backend/auth.py` | `require_password`/`require_password_ws` via `secrets.compare_digest` | ✓ VERIFIED | Present, timing-safe, lazy env read |
| `webapp/backend/streaming.py` | `get_or_create_queue`/`make_stream_hook`/`drop_queue` | ✓ VERIFIED | All three present; hook never raises (try/except around `put_nowait`) |
| `webapp/backend/deps.py` | `get_ask_question` overridable factory | ✓ VERIFIED | Present, wraps `qa.session.ask_question` |
| `webapp/backend/main.py` | FastAPI `app` with `POST /api/ask` + `WS /ws/{stream_id}`, password-gated | ✓ VERIFIED | Present; both routes gated via `Depends(require_password)`/`Depends(require_password_ws)` |
| `tests/test_webapp_backend.py` | Fast-tier tests, no real API key | ✓ VERIFIED | 21 tests present (4 auth/schema + 5 streaming/deps + 4 main.py endpoints + additional), all passing |
| `tests/test_webapp_integration.py` | Single `live_llm`-marked end-to-end test | ✓ VERIFIED | Exactly one test, correctly marked, skips cleanly without `ANTHROPIC_API_KEY`, human-confirmed passing per 07-03-SUMMARY.md |
| `pyproject.toml` | `fastapi[standard]` as optional `web` group | ✓ VERIFIED | `[project.optional-dependencies] web = ["fastapi[standard]>=0.141.1"]`; base `dependencies` list unaffected (no fastapi/uvicorn) |

### Key Link Verification

| From | To | Via | Status | Details |
|------|-----|-----|--------|---------|
| `qa/session.py::ask_question` | `agent/session.py::run_session` | `extra_hooks=extra_hooks` | ✓ WIRED | Confirmed in source |
| `agent/session.py::build_options` | `HookMatcher` PostToolUse list | `hooks.extend(extra_hooks or [])` | ✓ WIRED | Confirmed in source |
| `webapp/backend/auth.py::require_password` | `os.environ['BIOCLAW_WEB_PASSWORD']` | `secrets.compare_digest` | ✓ WIRED | Confirmed in source |
| `webapp/backend/main.py POST /api/ask` | `webapp/backend/deps.py::get_ask_question` | `Depends(deps.get_ask_question)` | ✓ WIRED | Confirmed; overridden successfully in tests |
| `webapp/backend/main.py POST /api/ask` | `webapp/backend/streaming.py::make_stream_hook` | `extra_hooks=[make_stream_hook(queue)]` | ✓ WIRED | Confirmed; only when `stream_id` present |
| `webapp/backend/main.py routes` | `webapp/backend/auth.py::require_password(_ws)` | `Depends(...)` | ✓ WIRED | Confirmed on both HTTP and WS routes |
| `webapp/backend/main.py WS /ws/{stream_id}` | `webapp/backend/streaming.py::get_or_create_queue` | `await queue.get()` drain loop | ✓ WIRED | Confirmed; `drop_queue` in `finally` |
| `tests/test_webapp_integration.py` | `webapp/backend/main.py::app` | `TestClient(app)`, no overrides | ✓ WIRED | Confirmed — no `dependency_overrides` used in this file |

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|------------|-------------|--------|----------|
| API-01 | 07-02, 07-03 | FastAPI endpoint accepts NL question, returns agent answer via ask_question() | ✓ SATISFIED | `main.py::ask()`; `test_ask_returns_answer`; live test + human checkpoint |
| API-02 | 07-01, 07-02, 07-03 | Streams tool-call activity live over WebSocket during agent execution | ✓ SATISFIED | `streaming.py` + WS handler; `test_ask_streams_tool_events`; live test + human checkpoint |
| API-05 | 07-01, 07-02 | All backend routes gated behind single shared password | ✓ SATISFIED | `auth.py`; applied on both routes in `main.py`; `test_ask_rejected_without_password`/`test_ws_rejected_without_password` |

Cross-referenced against `.planning/REQUIREMENTS.md`: API-01, API-02, API-05 all marked `[x]` Complete and mapped to "Phase 7 / Complete" in the requirements-to-phase table. No requirement IDs mapped to Phase 7 in REQUIREMENTS.md are missing from the plans' frontmatter — union of `requirements:` fields across 07-01/07-02/07-03 (`API-05, API-02` / `API-01, API-02, API-05` / `API-01, API-02`) = `{API-01, API-02, API-05}`, exactly matching the phase's declared requirement IDs. No orphaned requirements. (API-03/API-04 are explicitly scoped to Phase 8 in REQUIREMENTS.md, not orphaned here.)

### Anti-Patterns Found

None. Scanned `webapp/backend/*.py`, `tests/test_webapp_backend.py`, `tests/test_webapp_integration.py` for TODO/FIXME/XXX/HACK/placeholder/stub patterns, empty-return implementations, and console-log-only handlers — no matches.

### Test Execution Results

- `uv run --extra web pytest tests/test_webapp_backend.py tests/test_agent_session_wiring.py tests/test_qa_session.py -q -m "not live_llm and not bio_fm_smoke and not vcc_data"` → 37 passed
- `uv run --extra web pytest tests/ -q -m "not live_llm and not bio_fm_smoke and not vcc_data"` → 172 passed, 5 deselected (full fast suite green)
- `uv run --extra web pytest tests/test_webapp_integration.py -m live_llm -q --collect-only` → 1 test collected, correctly marked
- `uv run --extra web pytest tests/test_webapp_integration.py -q -m "not live_llm"` → 1 deselected, skips cleanly without ANTHROPIC_API_KEY

### Human Verification Required

None outstanding — the phase's one human-verify checkpoint (07-03 Task 2, live_llm end-to-end test + localhost-only curl checks) was already run and confirmed by Darren, documented in `07-03-SUMMARY.md`'s "Checkpoint Resolution" section (live test 1 passed, 401 unauthenticated, 200 authenticated, server bound to 127.0.0.1 only).

### Gaps Summary

No gaps found. All observable truths, artifacts, and key links verified against the actual codebase (not just SUMMARY claims). Code inspected directly matches the plan's `<action>` blocks verbatim for all three plans (07-01, 07-02, 07-03). Full fast test suite (172 tests) passes; the single live_llm test collects and is marked correctly, with its real-SDK pass already confirmed by human checkpoint. Requirements API-01, API-02, API-05 are all satisfied with no orphaned or missing requirement IDs for this phase.

---

*Verified: 2026-09-12*
*Verifier: Claude (gsd-verifier)*
