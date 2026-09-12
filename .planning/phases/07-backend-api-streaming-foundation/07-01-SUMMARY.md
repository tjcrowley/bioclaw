---
phase: 07-backend-api-streaming-foundation
plan: 01
subsystem: api
tags: [fastapi, pydantic, auth, hooks, claude-agent-sdk, streaming-foundation]

# Dependency graph
requires:
  - phase: 06-natural-language-qa-capstone
    provides: agent/session.py::run_session()/build_options() and qa/session.py::ask_question() as the stable synchronous session entrypoints this plan makes additively streamable
provides:
  - extra_hooks kwarg on build_options()/run_session()/ask_question() -- a caller can now observe intermediate PostToolUse activity without modifying the existing hook chain
  - webapp/backend/schemas.py -- AskRequest/AskResponse/ToolEvent Pydantic v2 contracts
  - webapp/backend/auth.py -- require_password/require_password_ws shared-password check (HTTP + WebSocket, timing-safe)
  - fastapi[standard] installed as an optional 'web' dependency group, base install unaffected
affects: [08-streaming-endpoints, 09-frontend, 10-deployment]

# Tech tracking
tech-stack:
  added: ["fastapi[standard]>=0.141.1 (optional 'web' extra)", pydantic v2 (already transitive, now used directly for API contracts)]
  patterns:
    - "Additive kwarg extension pattern: new optional list-typed kwarg defaulting to None, appended (never replacing) an existing collection, so omitting it is byte-for-byte identical to prior behavior"
    - "Shared-password auth checked via three fallback sources (Bearer header, query param, cookie) so both plain HTTP and browser WebSocket clients (which cannot set custom headers) can authenticate through the same secrets.compare_digest check"

key-files:
  created:
    - webapp/__init__.py
    - webapp/backend/__init__.py
    - webapp/backend/schemas.py
    - webapp/backend/auth.py
    - tests/test_webapp_backend.py
  modified:
    - agent/session.py
    - qa/session.py
    - tests/test_agent_session_wiring.py
    - tests/test_qa_session.py
    - pyproject.toml
    - uv.lock

key-decisions:
  - "extra_hooks appended (not prepended/merged) to the existing [_make_log_hook, record_dataset_reference] list inside the single PostToolUse HookMatcher -- preserves the single-HookMatcher shape already asserted by test_build_options_returns_claude_agent_options"
  - "auth._valid() reads BIOCLAW_WEB_PASSWORD lazily via os.environ.get() inside the function body (not at import time), so tests can monkeypatch.setenv per-test without import-order coupling"
  - "uv add ... --optional web followed by uv sync --extra web (never a bare uv sync) to avoid uninstalling the just-added fastapi/uvicorn/websockets from .venv before this task's own pytest run needed them"

patterns-established:
  - "webapp/backend/ package as the home for all FastAPI wire contracts (schemas.py) and cross-cutting concerns (auth.py) -- Plan 07-02's main.py/streaming.py/deps.py import from here rather than redefining shapes inline"

requirements-completed: [API-05, API-02]

# Metrics
duration: ~10min
completed: 2026-09-11
---

# Phase 7 Plan 01: Additive extra_hooks + webapp/backend Foundation Summary

**Additive `extra_hooks` kwarg threaded through the existing agent/qa session stack, plus a new `webapp/backend/` package (Pydantic contracts + timing-safe shared-password auth) and `fastapi[standard]` installed as an optional dependency group -- the stable surface Plan 07-02's streaming FastAPI app builds on.**

## Performance

- **Duration:** ~10 min
- **Tasks:** 2 completed
- **Files modified:** 11

## Accomplishments
- `build_options()`/`run_session()` (agent/session.py) and `ask_question()` (qa/session.py) all accept a new `extra_hooks: list | None = None` kwarg, forwarded end-to-end with zero behavioral change when omitted
- `webapp/backend/schemas.py` defines `AskRequest`/`AskResponse`/`ToolEvent` -- the exact wire contracts Plan 07-02's endpoints will implement against
- `webapp/backend/auth.py` implements `require_password`/`require_password_ws`, a single timing-safe (`secrets.compare_digest`) shared-password check reusable by both HTTP routes (Bearer header/query/cookie) and WebSocket routes (query/cookie, since browser WS clients can't set custom headers)
- `fastapi[standard]` added as a new `[project.optional-dependencies] web` group in `pyproject.toml`; base (non-web) dependency list untouched

## Task Commits

1. **Task 1: Additive extra_hooks kwarg on build_options/run_session/ask_question** - `0267f65` (feat)
2. **Task 2: fastapi[standard] install + webapp/backend schemas.py + auth.py contracts** - `75fbeb2` (feat)

**Plan metadata:** (this commit)

## Files Created/Modified
- `agent/session.py` - `build_options()`/`run_session()` gained `extra_hooks: list | None = None`, appended to the existing PostToolUse hook list inside the single `HookMatcher`
- `qa/session.py` - `ask_question()` gained `extra_hooks: list | None = None`, forwarded unchanged to `run_session()`
- `tests/test_agent_session_wiring.py` - added `test_build_options_appends_extra_hooks` and `test_build_options_extra_hooks_defaults_to_none_safely`
- `tests/test_qa_session.py` - added `test_ask_question_forwards_extra_hooks`
- `pyproject.toml` - new `[project.optional-dependencies] web = ["fastapi[standard]>=0.141.1"]` group
- `uv.lock` - updated lockfile for the new `web` extra (fastapi, uvicorn, websockets, httpx, and transitive deps)
- `webapp/__init__.py`, `webapp/backend/__init__.py` - package markers
- `webapp/backend/schemas.py` - `AskRequest`/`AskResponse`/`ToolEvent` Pydantic v2 models
- `webapp/backend/auth.py` - `_valid()`, `require_password()`, `require_password_ws()`
- `tests/test_webapp_backend.py` - 4 new tests covering `_valid()`'s three branches and schema construction

## Decisions Made
- extra_hooks is appended to (not merged/deduplicated against) the existing hook list -- simplest possible additive semantics, matches the plan's exact interface spec
- `auth._valid()` reads the env var lazily inside the function body rather than at module import time, so `monkeypatch.setenv` works per-test without needing to reload the module
- Followed the plan's explicit `uv add ... --optional web` then `uv sync --extra web` sequencing (never a bare `uv sync`) to avoid desyncing `.venv` before this task's own fastapi-importing tests run

## Deviations from Plan

None - plan executed exactly as written. All code (schemas.py, auth.py, and the extra_hooks changes) matches the plan's `<action>` blocks verbatim; no Rule 1-4 triggers encountered.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required. `BIOCLAW_WEB_PASSWORD` is an environment variable Plan 07-02/07-03 will need at runtime, but no action is needed at this wave (tests use `monkeypatch.setenv`).

## Next Phase Readiness

Plan 07-02 (streaming/deps/main FastAPI app) can now:
- Import `webapp.backend.schemas.{AskRequest,AskResponse,ToolEvent}` directly as stable wire contracts
- Import `webapp.backend.auth.{require_password,require_password_ws}` as FastAPI dependencies on every HTTP/WebSocket route
- Pass a streaming-observer hook into `qa.session.ask_question(..., extra_hooks=[...])` to surface intermediate tool-call activity over a WebSocket, without any further changes to `agent/session.py` or `qa/session.py`

No blockers. `uv sync --extra web` confirmed fastapi/uvicorn/websockets/httpx installed with no resolver conflicts; full fast test suite (163 tests, excluding `live_llm`/`bio_fm_smoke`/`vcc_data`) passes with the `web` extra installed.

---
*Phase: 07-backend-api-streaming-foundation*
*Completed: 2026-09-11*

## Self-Check: PASSED

All created/modified files verified present on disk; both task commits (0267f65, 75fbeb2) verified present in git history.
