# Phase 7: Backend API + Streaming Foundation - Research

**Researched:** 2026-09-11
**Domain:** FastAPI (HTTP + WebSocket), Claude Agent SDK hook interception, shared-secret auth
**Confidence:** MEDIUM-HIGH (core FastAPI/WebSocket patterns are official-docs-verified HIGH confidence; the tool-call-streaming interception design is an original synthesis over this repo's own `agent/session.py` code, cross-checked against community asyncio.Queue patterns — MEDIUM confidence, no CONTEXT.md existed to further constrain scope)

## Summary

Phase 7 wraps an existing, fully-synchronous `ask_question()` call (which runs a whole Claude Agent SDK session to completion before returning) in a FastAPI backend that must (a) return the final answer over plain HTTP and (b) push tool-call events to a *separate*, concurrently-open WebSocket connection *while that same HTTP request is still being processed*. Nothing about `ask_question()`, `run_session()`, or `build_options()` currently exposes intermediate events to a caller — the only event-interception point that already exists is the `PostToolUse` hook list wired into `ClaudeAgentOptions` inside `agent/session.py::build_options()`. The correct, minimal-risk approach is to make `build_options()`/`run_session()`/`ask_question()` accept an **additive `extra_hooks` parameter** (same pattern already used for `system_prompt` in Phase 6), and have the webapp pass in one extra `PostToolUse` hook per request that does `queue.put_nowait(event)` into an `asyncio.Queue` correlated to that request via a caller-supplied `stream_id`. A WebSocket endpoint, connected *before* the POST is issued, drains that same queue and forwards events as JSON. This is a well-established community pattern (job-id/stream-id-keyed queue registry) but is **only safe with a single Uvicorn worker/process** — `asyncio.Queue` does not cross process boundaries, which is compatible with this phase's localhost-only, single-user scope.

The second major finding: because Phase 9 will eventually put a real browser frontend in front of this API (UI-06's login screen), and **browser `WebSocket` JavaScript clients cannot set custom headers** (only `fetch`/`XMLHttpRequest` can), the auth mechanism chosen now must work for both HTTP and WS without relying on headers for the WS leg. The recommended design is a single shared-secret check function that accepts the password from an `Authorization: Bearer` header (HTTP, and non-browser tools/tests), a `?password=` query parameter (WS handshake, since browser WS can't send headers), or an auth cookie (future-proofing for Phase 9's login flow, which will set a cookie once and let both HTTP and WS reuse it automatically). This avoids painting Phase 9 into a corner while keeping Phase 7 itself simple (no login endpoint or session store is required to satisfy API-05's literal criteria — every request just needs to *carry* the correct shared password).

**Primary recommendation:** Build the FastAPI app in a new top-level `webapp/backend/` package (importing `qa.session.ask_question`, `agent.session`, `agent.memory` directly from the existing root package — no dependency isolation needed here, unlike `bio_fm_worker/`, since `fastapi`/`uvicorn` have no conflicting pins with anything in `pyproject.toml`). Add `fastapi[standard]` (bundles `uvicorn`, `websockets`, `httpx`, `python-multipart`) as a new optional-dependencies group in the root `pyproject.toml`. Make `agent/session.py::build_options()`/`run_session()` and `qa/session.py::ask_question()` accept an additive `extra_hooks` list. Test with Starlette's synchronous `TestClient` (no `pytest-asyncio` needed — matches this repo's existing anti-`pytest-asyncio` convention from Phase 6), using `app.dependency_overrides` to replace `ask_question` with a fake in fast-tier tests; reserve exactly one `live_llm`-marked test for the true end-to-end path.

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-------------------|
| API-01 | FastAPI backend exposes an endpoint that accepts a natural-language question and returns the agent's answer, wrapping `qa/session.py::ask_question()` | See "Architecture Patterns" Pattern 1 (POST endpoint + dependency-injected `ask_question`) and "Code Examples" |
| API-02 | Backend streams tool-call activity to the client as it happens during agent execution, over WebSocket, not just the final answer | See "Architecture Patterns" Pattern 2 (stream-id-keyed `asyncio.Queue` registry + additive `extra_hooks`) — this is the highest-risk item, addressed in depth below |
| API-05 | All backend routes are gated behind a single shared password — unauthenticated requests are rejected | See "Architecture Patterns" Pattern 3 (multi-source shared-secret dependency: header / query param / cookie) and "Common Pitfalls" (browser WS header limitation, timing-safe comparison) |
</phase_requirements>

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|---------------|
| `fastapi[standard]` | 0.136.x (current stable, Sep 2026) | HTTP + WebSocket routing, dependency injection, request validation | De facto standard async Python web framework; `[standard]` extra bundles `uvicorn[standard]`, `websockets`, `httpx`, `python-multipart` in one install so the WS + testing + future-upload (Phase 8) needs are covered without separately pinning each |
| `uvicorn` | bundled via `fastapi[standard]` (0.47.x) | ASGI server to run the app locally | Official recommended server for FastAPI; ships as part of the `[standard]` extra |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `httpx` | bundled via `fastapi[standard]` | Already installed as a `TestClient`/async-client dependency | Only needed directly if a test wants `httpx.ASGITransport`-based async calls; not required for this phase's tests (see Architecture Patterns / testing) |
| stdlib `secrets`, `hmac`, `hashlib` | builtin | Constant-time shared-secret comparison, optional signed-cookie token | No new dependency needed for API-05's shared-password check |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| In-memory `asyncio.Queue` registry for streaming | Redis pub/sub, `encode/broadcaster` | Only needed once you run multiple Uvicorn workers/processes or need cross-process fanout; explicitly out of scope for a localhost, single-user Phase 7 (PKG-02 in Phase 10 also implies a single documented single-process run command) |
| Root `pyproject.toml` optional-dependencies group for `fastapi` | Separate `webapp/pyproject.toml` + its own venv (uv workspace member or fully isolated venv, mirroring `bio_fm_worker/`) | `bio_fm_worker/`'s isolation exists because `scgpt` pins conflicting/heavy transitive deps (`torch`, `scvi-tools<1.0`, `torchtext`). `fastapi`/`uvicorn` have no such conflict with anything currently in `pyproject.toml` (verified: `pydantic` 2.13.5 already present, no pin conflicts) — a separate venv here would only add packaging complexity without a corresponding dependency-conflict reason. Revisit only if Phase 8-10 introduce a genuinely conflicting dependency. |
| Per-request `asyncio.Queue` keyed by a client-generated `stream_id` | A single global broadcast queue (all WS clients see all events) | Global broadcast is simpler but leaks cross-session tool-call activity to any connected client — wrong even for a single-user tool once more than one browser tab/session exists; per-`stream_id` keying costs one dict lookup |
| Cookie/header/query-param shared-secret dependency | Full OAuth2/JWT (`OAuth2PasswordBearer`, `python-jose`) | JWT is the "textbook" FastAPI security tutorial, but this is explicitly a single shared secret, not per-user accounts (REQUIREMENTS.md, PROJECT.md, and v2's deferred `AUTH-01`) — a JWT library adds real complexity (signing keys, expiry, refresh) for no benefit over a plain shared-secret check |

**Installation:**
```bash
uv add "fastapi[standard]" --optional web
```
(Adds a `[project.optional-dependencies] web = [...]` group so the base `bioclaw` install — ingest/agent/qa/CLI use — does not require FastAPI; the webapp entrypoint installs with `uv sync --extra web`.)

## Architecture Patterns

### Recommended Project Structure
```
webapp/
└── backend/
    ├── __init__.py
    ├── main.py          # FastAPI() app instance, route registration, lifespan
    ├── auth.py          # shared-password dependency (HTTP + WS variants)
    ├── streaming.py      # stream_id -> asyncio.Queue registry, event shape, hook factory
    ├── deps.py           # Depends()-injected ask_question / SessionMemory factories (overridable in tests)
    └── schemas.py         # Pydantic request/response models (AskRequest, AskResponse, ToolEvent)
tests/
└── test_webapp_backend.py   # fast-tier: dependency_overrides, no real API key
└── test_webapp_integration.py  # live_llm-marked: real ask_question() end-to-end
```
`webapp/backend/` imports directly from the root `qa`, `agent`, `agent.memory` packages (no subprocess boundary, unlike `bio_fm_worker/` — there is no dependency conflict forcing isolation here). This keeps PKG-01's "own directory" requirement (Phase 10) satisfiable without needing "own dependencies" to mean "own venv" — it means "the base package doesn't require these deps," achieved via the `web` optional-dependencies group.

### Pattern 1: `ask_question()` wrapped as a POST endpoint
**What:** A `POST /api/ask` (exact path is Claude's discretion — no CONTEXT.md constrains naming) endpoint takes `{"question": str, "session_id": str | None, "stream_id": str | None}`, calls `ask_question(question, session_memory=..., extra_hooks=[...])`, and returns `{"answer": str, "session_id": str, "citations": [...]}`.
**When to use:** This is the only HTTP surface API-01 requires for Phase 7 (session list/resume is API-03/Phase 8; upload is API-04/Phase 8).
**Example:**
```python
# webapp/backend/main.py — pattern synthesized from FastAPI's official
# dependency-injection + testing-dependencies docs (fastapi.tiangolo.com)
from fastapi import APIRouter, Depends
from qa.session import ask_question
from webapp.backend.auth import require_password
from webapp.backend.streaming import make_stream_hook, get_or_create_queue
from webapp.backend.schemas import AskRequest, AskResponse

router = APIRouter()

@router.post("/api/ask", dependencies=[Depends(require_password)])
async def ask(req: AskRequest) -> AskResponse:
    extra_hooks = []
    if req.stream_id:
        queue = get_or_create_queue(req.stream_id)
        extra_hooks.append(make_stream_hook(queue))
    answer, session_id, citations = await ask_question(
        req.question,
        extra_hooks=extra_hooks,  # new additive param, see Pattern 2
    )
    return AskResponse(answer=answer, session_id=session_id, citations=citations)
```

### Pattern 2: Additive `extra_hooks` — the tool-call streaming mechanism (highest-risk item)
**What:** `agent/session.py::build_options()` already wires a static `PostToolUse` `HookMatcher` with two hooks (`_make_log_hook`, `record_dataset_reference`). Extend it, `run_session()`, and `qa/session.py::ask_question()` with an additive `extra_hooks: list[Callable] | None = None` parameter appended to that same `HookMatcher`'s hooks list — mirroring exactly how Phase 6's `system_prompt` kwarg was added ("additive on `build_options`/`run_session` with existing constant as default — zero behavioral change for existing callers," per `STATE.md`).
**When to use:** Any time a caller (the webapp) needs to observe tool-call activity as it happens, without changing `ask_question()`'s return contract.
**Example:**
```python
# agent/session.py — additive change, existing signature/behavior unchanged
def build_options(
    session_memory: SessionMemory,
    session_id: str,
    log_path: Path = DEFAULT_LOG_PATH,
    system_prompt: str = SYSTEM_PROMPT,
    extra_hooks: list | None = None,   # NEW
) -> ClaudeAgentOptions:
    hooks = [_make_log_hook(log_path), record_dataset_reference(session_memory, session_id)]
    hooks.extend(extra_hooks or [])
    return ClaudeAgentOptions(
        ...,
        hooks={"PostToolUse": [HookMatcher(hooks=hooks)]},
    )
```
```python
# webapp/backend/streaming.py — the hook the webapp injects.
# Must never raise (matches record_dataset_reference's own documented
# invariant: "this must never raise or otherwise crash the hook chain").
import asyncio

_QUEUES: dict[str, asyncio.Queue] = {}

def get_or_create_queue(stream_id: str) -> asyncio.Queue:
    return _QUEUES.setdefault(stream_id, asyncio.Queue(maxsize=100))

def make_stream_hook(queue: asyncio.Queue):
    async def _hook(input_data, tool_use_id, context):
        try:
            event = {
                "tool_name": input_data.get("tool_name", ""),
                "tool_input": input_data.get("tool_input", {}),
                "is_error": _tool_response_is_error(input_data.get("tool_response")),
            }
            queue.put_nowait(event)
        except Exception:
            pass
        return {}
    return _hook
```
```python
# webapp/backend/main.py — the WS endpoint that drains the same queue.
# Client MUST open this connection (and the server MUST accept() it)
# BEFORE the correlated POST /api/ask is issued, or early events are
# lost -- see Common Pitfalls.
from fastapi import WebSocket, WebSocketDisconnect
from webapp.backend.auth import require_password_ws

@app.websocket("/ws/{stream_id}")
async def stream_events(websocket: WebSocket, stream_id: str):
    await require_password_ws(websocket)  # raises WebSocketException before accept() if invalid
    await websocket.accept()
    queue = get_or_create_queue(stream_id)
    try:
        while True:
            event = await queue.get()
            await websocket.send_json(event)
    except WebSocketDisconnect:
        pass
    finally:
        _QUEUES.pop(stream_id, None)
```
Source pattern cross-verified against: FastAPI official WebSocket docs (`fastapi.tiangolo.com/advanced/websockets/`) for the accept/`WebSocketDisconnect`/`Depends`/`WebSocketException` shapes, and community job-id/queue-registry examples (see Sources) for the stream-id correlation idea — the correlation-by-shared-id design itself is this research's own synthesis over this repo's hook mechanism, not lifted verbatim from any single source.

### Pattern 3: Shared-password dependency, HTTP + WebSocket
**What:** One `secrets.compare_digest`-based check function, with two thin `Depends()`-compatible wrappers — one for HTTP (checks header, falls back to query/cookie), one for WebSocket (checks query param, falls back to cookie; browser JS `WebSocket` cannot set custom headers — see Pitfalls).
**When to use:** Every route (HTTP and WS) must depend on this per API-05's "any request to any backend route" wording.
**Example:**
```python
# webapp/backend/auth.py
import os
import secrets
from fastapi import Header, HTTPException, Query, Cookie, WebSocket, WebSocketException, status

def _valid(password: str | None) -> bool:
    expected = os.environ["BIOCLAW_WEB_PASSWORD"]
    return password is not None and secrets.compare_digest(password, expected)

async def require_password(
    authorization: str | None = Header(default=None),
    password: str | None = Query(default=None),
    session: str | None = Cookie(default=None),
) -> None:
    candidate = None
    if authorization and authorization.startswith("Bearer "):
        candidate = authorization.removeprefix("Bearer ")
    candidate = candidate or password or session
    if not _valid(candidate):
        raise HTTPException(status_code=401, detail="unauthorized")

async def require_password_ws(
    websocket: WebSocket,
    password: str | None = Query(default=None),
    session: str | None = Cookie(default=None),
) -> None:
    if not _valid(password or session):
        raise WebSocketException(code=status.WS_1008_POLICY_VIOLATION)
```
Source: FastAPI official docs for `WebSocketException`/`Query`/`Cookie` in WS dependencies (`fastapi.tiangolo.com/advanced/websockets/`), confirmed the browser-header limitation via cross-referenced community sources (see Sources).

### Anti-Patterns to Avoid
- **String `==` for password comparison:** Not constant-time; use `secrets.compare_digest`. A textbook timing-attack surface, trivial to avoid.
- **Relying on `Authorization` header for the WebSocket leg:** Works for `curl`/`websockets`-library test clients, silently impossible for a real browser `WebSocket` client (Phase 9). Design the query-param/cookie fallback into the auth dependency now.
- **Running Uvicorn with `--workers > 1` (or multiple processes) for this phase:** breaks the in-memory `asyncio.Queue` registry — a WS connection and its correlated POST can land on different worker processes and never share state. PKG-02 (Phase 10)'s "single documented command" should default to a single worker; document this constraint now so it isn't silently violated later.
- **Blocking `await queue.get()` forever after a client disconnects:** wrap the WS loop in `try/except WebSocketDisconnect/finally: _QUEUES.pop(...)` so a queue for a dead connection doesn't leak indefinitely (per the FastAPI docs's own disconnect-handling pattern and cross-referenced community "leaking resources" caveat).

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|--------------|-----|
| Request/response body validation | Manual `dict` key checking | Pydantic models (`AskRequest`, `AskResponse`) — already a transitive dependency via `claude-agent-sdk`/`fastapi` | FastAPI auto-generates 422 errors and OpenAPI docs from these for free |
| WebSocket connection/accept/disconnect lifecycle | Raw `asyncio`/socket handling | `fastapi.WebSocket` + `WebSocketDisconnect` | Handles the HTTP Upgrade handshake, ping/pong, and close codes correctly; hand-rolling this is exactly the kind of "deceptively complex" problem the philosophy section warns about |
| Timing-safe secret comparison | `if password == expected` | `secrets.compare_digest` | Constant-time comparison prevents a timing side-channel; trivial to get wrong by hand |

**Key insight:** Everything genuinely novel in this phase (the stream-id correlation, the additive-hooks plumbing) is small, explicit, in-repo code — there is nothing here that justifies a new heavyweight dependency (no job queue system, no pub/sub broker, no auth library) given the phase's explicit localhost/single-user/single-shared-secret scope.

## Common Pitfalls

### Pitfall 1: Browser WebSocket clients cannot send custom headers
**What goes wrong:** An HTTP-only `Authorization: Bearer` auth design works in tests/curl but silently fails once Phase 9 builds a real browser frontend, because the browser `WebSocket` constructor has no API for custom headers (a deliberate browser security restriction — the `Sec-` header prefix cannot be set by JS).
**Why it happens:** Browsers intentionally prevent forging arbitrary WS handshake headers to stop `fetch`/XHR-based handshake spoofing.
**How to avoid:** Design the auth dependency to also accept the password via a `?password=` query parameter (WS handshake) or a cookie (set later by Phase 9's login flow) from day one — see Pattern 3.
**Warning signs:** A Phase 9 code review finds the frontend trying to pass `Authorization` to `new WebSocket(url, ...)` and failing, or silently connecting unauthenticated because a header-only check was bypassed by omission.
(Cross-verified across multiple independent sources; MEDIUM-HIGH confidence.)

### Pitfall 2: Losing early tool-call events to a race between WS connect and POST
**What goes wrong:** If the client issues the correlated `POST /api/ask` before its `stream_id`'s WebSocket connection is open and accepted, any tool calls that happen in the first few hundred milliseconds are enqueued into a queue nobody is draining yet — not lost (the queue buffers them), but not seen live either if the WS never connects at all before the POST completes.
**Why it happens:** Two independent HTTP/WS connections correlated only by an app-level `stream_id`, with no built-in ordering guarantee between them.
**How to avoid:** Document (for the Phase 9 frontend, and enforce loosely in Phase 7's own test/verification steps) that the client must open and confirm the WebSocket connection *before* issuing the POST. Bound the queue (`maxsize=`) so a client that never connects doesn't leak memory across many abandoned questions, and clear queues in a `finally` block on WS disconnect.
**Warning signs:** A manual verification (Success Criteria #2) shows the final answer but zero or partial tool-call events on the WS.

### Pitfall 3: Multi-worker Uvicorn breaks the in-memory queue registry
**What goes wrong:** Running `uvicorn ... --workers 4` (or behind a process-forking supervisor) puts the WS connection and its correlated POST request on two different OS processes with two different Python interpreters and `asyncio` event loops — the `_QUEUES` dict is per-process, so the WS side's queue lookup silently returns nothing or a different queue than the POST side wrote to.
**Why it happens:** `asyncio.Queue` (and any plain in-process dict) is inherently single-process.
**How to avoid:** Run a single Uvicorn worker for Phase 7 (and ideally state this constraint in Phase 10's packaging docs too — a Redis-backed registry would be the fix if multi-worker is ever needed, out of scope here).
**Warning signs:** Streaming "sometimes works, sometimes doesn't" in a way that correlates with process/worker count, not with request content.

### Pitfall 4: PostToolUse hook exceptions silently breaking the hook chain
**What goes wrong:** Per this repo's own Phase 3 decision log (`STATE.md`), an uncaught exception inside a `PostToolUse` hook previously dispatched as a distinct, unobserved `PostToolUseFailure` SDK event rather than surfacing normally. A hastily-written streaming hook that raises (e.g. on a malformed/oversized event, or a full queue with `put_nowait` raising `QueueFull`) can silently break tool-call logging/citation-hash injection for the *entire* request, not just streaming.
**Why it happens:** Multiple hooks share one `HookMatcher` list; the SDK's error handling for a hook exception is not obviously "log and continue" by default (per this repo's prior finding).
**How to avoid:** Wrap the entire streaming hook body in `try/except: pass` (mirroring `record_dataset_reference`'s own documented invariant: "this must never raise or otherwise crash the hook chain"), and use `put_nowait` with the exception swallowed (or a bounded `asyncio.Queue` where you drop the oldest event instead of raising) rather than `await queue.put(...)`, which could deadlock the whole session if a WS consumer stalls.
**Warning signs:** Citation hashes (`[ref:TOOL_NAME:SHA256_PREFIX]`, QA-02/03 from Phase 6) stop resolving once streaming is added — a regression signal that the new hook is interfering with the existing logging hook via a chain-level failure, not its own logic.

### Pitfall 5: Testing WebSocket + concurrent HTTP incorrectly
**What goes wrong:** Assuming you need `httpx.AsyncClient` + `pytest-asyncio` to test "WS receives events during a POST," when Starlette's plain synchronous `TestClient` already supports this out of the box.
**Why it happens:** `TestClient` runs the ASGI app in a background thread via an `anyio` blocking portal (`anyio.from_thread.start_blocking_portal()`), so `with client.websocket_connect(...) as ws:` opens a connection that stays live in that background thread's event loop while the *calling* test code continues sequentially — a subsequent (still-synchronous) `client.post(...)` call runs the whole request (including the streaming hook enqueuing events) inside that same background loop concurrently with the WS connection, and `ws.receive_json()` calls made afterward correctly drain what accumulated.
**How to avoid:** Test pattern: open `with client.websocket_connect(f"/ws/{stream_id}?password=...") as ws:`, then call `client.post("/api/ask", json={...})` (still inside the `with` block, still synchronous), then loop `ws.receive_json()` to assert on buffered events. No `pytest-asyncio` needed — this matches the existing project convention (`STATE.md` Phase 6 decision: "uses `asyncio.run()` inside sync tests ... rather than adding pytest-asyncio -- keeps dev-dependency footprint stable").
**Warning signs:** Reaching for `pytest-asyncio`/`httpx.AsyncClient` as a first instinct for this test — it works too, but is unnecessary complexity given `TestClient`'s existing threading model, and is a new dev-dependency this repo has previously deliberately avoided.

## Code Examples

### Fast-tier test pattern (no real ANTHROPIC_API_KEY)
```python
# tests/test_webapp_backend.py
from fastapi.testclient import TestClient
from webapp.backend.main import app
from webapp.backend import deps

async def _fake_ask_question(question, session_memory=None, extra_hooks=None, log_path=None):
    # Manually drive the injected hooks exactly as the real PostToolUse
    # dispatch would, so the streaming plumbing is exercised without a
    # live SDK/API call.
    for hook in extra_hooks or []:
        await hook(
            {"tool_name": "mcp__bioclaw__analyze_dataset", "tool_input": {"name": "x"},
             "tool_response": [{"type": "text", "text": "{}"}]},
            "tool-use-1", {},
        )
    return "fake answer [ref:mcp__bioclaw__analyze_dataset:aaaaaaaaaaaa]", "sess-1", []

def test_ask_streams_tool_events(monkeypatch):
    monkeypatch.setenv("BIOCLAW_WEB_PASSWORD", "testpass")
    app.dependency_overrides[deps.get_ask_question] = lambda: _fake_ask_question
    client = TestClient(app)
    with client.websocket_connect("/ws/stream-1?password=testpass") as ws:
        resp = client.post(
            "/api/ask",
            json={"question": "how many clusters?", "stream_id": "stream-1"},
            headers={"Authorization": "Bearer testpass"},
        )
        assert resp.status_code == 200
        event = ws.receive_json()
        assert event["tool_name"] == "mcp__bioclaw__analyze_dataset"
    app.dependency_overrides.clear()

def test_ask_rejected_without_password():
    client = TestClient(app)
    resp = client.post("/api/ask", json={"question": "x"})
    assert resp.status_code == 401
```
Source: pattern synthesized from FastAPI's official "Testing Dependencies with Overrides" docs (`fastapi.tiangolo.com/advanced/testing-dependencies/`) and Starlette's `TestClient` websocket-session docs (`starlette.dev/testclient/`).

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|-------------------|---------------|--------|
| Server-Sent Events (SSE) for one-way progress streams | WebSocket for bidirectional or FastAPI `StreamingResponse` for one-way | Both remain valid in FastAPI's current docs; WebSocket was already specified by this phase's own success criteria, so SSE is not a live alternative here — noted only because some blog sources default to recommending SSE for "just show me progress" use cases | Not applicable — API-02 explicitly mandates WebSocket |
| `python-jose`/manual JWT for lightweight auth | `secrets.compare_digest` shared-secret check for single-secret (non-multi-tenant) cases | N/A — this is a scope-appropriateness choice, not a library deprecation | Avoids an unnecessary dependency and attack surface (signing keys, algorithm confusion) for a case that isn't actually multi-user |

**Deprecated/outdated:** None identified as deprecated within FastAPI/Starlette's current (0.136.x) API surface for the patterns used here.

## Open Questions

1. **Exact wire shape of the WebSocket event payload (tool name/args-summary/status fields)**
   - What we know: `PostToolUseHookInput` gives `tool_name`, `tool_input`, `tool_response` (verified live in Phase 3/6). "Args summary" and "status" (success/error/in-progress) are not literally present — `is_error` can be derived from `tool_response`, but there is no explicit "started" event (only `PostToolUse`, i.e. after-the-fact) unless a `PreToolUse` hook is also wired in for a "running" status.
   - What's unclear: Whether UI-02 (Phase 9) needs a "tool call started" event in addition to "tool call completed," which would require also hooking `PreToolUse` (not currently wired anywhere in this repo).
   - Recommendation: For Phase 7, ship only `PostToolUse`-derived events (name, redacted/truncated args, is_error) — sufficient for API-02's literal "as they happen... not only the final answer" criterion since PostToolUse events already arrive well before the final answer. Revisit `PreToolUse` in Phase 9 if the UI genuinely needs a "running" spinner state per tool call.

2. **Route/path naming and exact JSON envelope shapes**
   - What we know: No CONTEXT.md exists for this phase, so nothing is locked; PROJECT.md/REQUIREMENTS.md do not specify exact paths.
   - What's unclear: Whether the planner should pick `/api/ask` + `/ws/{stream_id}` (this research's working example) or another convention.
   - Recommendation: Treat naming as Claude's/the planner's discretion; keep it consistent so Phase 8 (which adds session list/resume/upload under the same auth) and Phase 9 (which consumes all of it) don't need a rename.

3. **Does the SDK expose a real `session_id`/stream correlation that could replace the app-level `stream_id`?**
   - What we know: `run_session()`'s own `session_id` is a process-local UUID generated by the caller, not derived from the SDK; `03-RESEARCH.md` (referenced in this repo's own code comments) already flagged the SDK's internal session id as "unconfirmed... inside a hook callback."
   - What's unclear: Whether reusing the existing `session_id` (instead of a separate `stream_id`) as the WS correlation key is sufficient, or whether a fresh per-request `stream_id` is needed because one session can span multiple sequential questions/requests over time (per Phase 8's planned session-resume feature).
   - Recommendation: Use a separate, per-*request* `stream_id` (not the longer-lived `session_id`) for the streaming correlation, since a single session may be resumed across multiple HTTP requests and each one needs its own live WS attached independently.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest >= 8 (already a dev dependency; no new test framework needed) |
| Config file | `pyproject.toml` (`[tool.pytest.ini_options]`) — add no new markers for Phase 7 unless a `live_llm`-marked webapp integration test is added, which reuses the existing `live_llm` marker |
| Quick run command | `pytest tests/test_webapp_backend.py -m "not live_llm" -x` |
| Full suite command | `pytest tests/ -m "not live_llm and not bio_fm_smoke and not vcc_data"` (matches this repo's existing convention of excluding markers documented as "excluded from fast/CI runs" in `pyproject.toml`) |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|---------------------|--------------|
| API-01 | POST endpoint returns `ask_question()`'s answer | unit (dependency-overridden) | `pytest tests/test_webapp_backend.py::test_ask_returns_answer -x` | ❌ Wave 0 |
| API-02 | WS connection receives tool-call events during a concurrent POST | unit (dependency-overridden, hooks driven manually) | `pytest tests/test_webapp_backend.py::test_ask_streams_tool_events -x` | ❌ Wave 0 |
| API-05 | Unauthenticated request rejected; correct-password request succeeds (HTTP + WS) | unit | `pytest tests/test_webapp_backend.py::test_ask_rejected_without_password tests/test_webapp_backend.py::test_ws_rejected_without_password -x` | ❌ Wave 0 |
| API-01/02 (true e2e) | Real `ask_question()` call, real Claude API, real tool invocation, real streamed events | live_llm smoke | `pytest tests/test_webapp_integration.py -m live_llm -x` | ❌ Wave 0 |

### Sampling Rate
- **Per task commit:** `pytest tests/test_webapp_backend.py -m "not live_llm" -x`
- **Per wave merge:** `pytest tests/ -m "not live_llm and not bio_fm_smoke and not vcc_data"`
- **Phase gate:** Full suite green, plus the one `live_llm`-marked webapp integration test run manually with a real `ANTHROPIC_API_KEY` (mirrors Phase 6's own `06-03` human-verify checkpoint pattern) before `/gsd:verify-work`.

### Wave 0 Gaps
- [ ] `webapp/backend/__init__.py`, `main.py`, `auth.py`, `streaming.py`, `deps.py`, `schemas.py` — new package, does not exist yet
- [ ] `tests/test_webapp_backend.py` — fast-tier tests (dependency_overrides, no real API key)
- [ ] `tests/test_webapp_integration.py` — single `live_llm`-marked end-to-end test
- [ ] Additive `extra_hooks` parameter on `agent/session.py::build_options()`/`run_session()` and `qa/session.py::ask_question()` — small, backward-compatible signature change to existing, already-tested modules; existing tests (`tests/test_agent_session_wiring.py`, `tests/test_qa_session.py`) must still pass unmodified after this change (default `extra_hooks=None` preserves current behavior, per the same additive pattern already used for `system_prompt`)
- [ ] `fastapi[standard]` install: `uv add "fastapi[standard]" --optional web` — not yet installed in `.venv` (verified: no `fastapi`/`uvicorn`/`websockets`/`httpx`/`pytest-asyncio` currently installed)

## Sources

### Primary (HIGH confidence)
- FastAPI official docs — WebSockets (`https://fastapi.tiangolo.com/advanced/websockets/`) — accept/`WebSocketDisconnect`/`Depends`/`Query`/`Cookie`/`WebSocketException` patterns for WS auth
- FastAPI official docs — Testing WebSockets (`https://fastapi.tiangolo.com/advanced/testing-websockets/`) — `TestClient.websocket_connect` basic usage
- FastAPI official docs — Testing Dependencies with Overrides (`https://fastapi.tiangolo.com/advanced/testing-dependencies/`) — `app.dependency_overrides` pattern
- This repo's own source: `qa/session.py`, `agent/session.py`, `agent/logging.py`, `agent/memory.py`, `agent/tools.py`, `pyproject.toml`, `.planning/STATE.md`, `.planning/REQUIREMENTS.md`, `.planning/PROJECT.md`, `.planning/ROADMAP.md` — read directly for this research
- Starlette `TestClient` internals verified via GitHub source discussion (`anyio.from_thread.start_blocking_portal()` background-thread mechanism) — `https://github.com/encode/starlette/blob/master/starlette/testclient.py` and linked discussions

### Secondary (MEDIUM confidence)
- Community job-id/queue-registry WebSocket patterns (multiple independent sources agreeing on the pattern shape): `https://github.com/greed2411/fastapi_ws_producer_consumer`, community articles on FastAPI WS + background task correlation
- Browser WebSocket header limitation, cross-verified across 3+ independent sources: `https://earezki.com/ai-news/2026-06-03-the-websocket-auth-problem-cookies-vs-bearer-tokens/`, `https://websocket.org/reference/headers/`, `https://websockets.readthedocs.io/en/stable/topics/authentication.html`
- uv workspace / multi-pyproject monorepo pattern (considered, not adopted for this phase): `https://itnext.io/python-workspaces-monorepos-d1ce81c74818`
- FastAPI/uvicorn current version numbers (Sep 2026): general WebSearch results, cross-referenced against PyPI project page pattern

### Tertiary (LOW confidence)
- None retained as load-bearing — all WebSearch findings used above were cross-verified against at least one official-docs or multi-source agreement before being stated as fact.

## Metadata

**Confidence breakdown:**
- Standard stack (FastAPI/uvicorn choice, versions, install extras): HIGH — official docs + PyPI-adjacent sources agree, no ecosystem ambiguity
- Architecture (streaming via additive hooks + asyncio.Queue registry, auth via multi-source shared secret): MEDIUM — the FastAPI/WebSocket primitives are HIGH confidence (official docs), but the specific integration with this repo's `claude_agent_sdk` hook mechanism is original synthesis with no existing precedent to copy — flagged accordingly; should be validated by the planner writing an explicit Wave 0 spike/test before building the full endpoint
- Pitfalls (browser WS header limitation, multi-worker queue breakage, hook-exception chain failure): MEDIUM-HIGH — cross-verified across multiple sources for the general patterns; the hook-exception-chain-failure risk specifically is HIGH confidence because it's this repo's own documented Phase 3 finding, not a general web claim

**Research date:** 2026-09-11
**Valid until:** ~30 days for the FastAPI/uvicorn version specifics (fast-moving 0.x ecosystem); the architecture patterns (hooks, queue registry, auth design) are stable regardless of point-release churn and don't need re-validation on that timescale
