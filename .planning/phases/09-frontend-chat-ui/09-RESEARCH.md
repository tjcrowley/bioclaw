# Phase 9: Frontend Chat UI — Research

**Researched:** 2026-09-12
**Domain:** Vanilla JS SPA, FastAPI StaticFiles, cookie auth, WebSocket client, citation rendering
**Confidence:** HIGH (all patterns are direct extensions of the Phase 7-8 auth/streaming contracts already live in this repo; the frontend tech choices below are conservative by design — no build step minimizes Phase 10 packaging risk)

## Summary

Phase 9 builds the researcher-facing web frontend that consumes the Phase 7-8 API. The backend is complete and correct: `POST /api/ask`, `WS /ws/{stream_id}`, `GET /api/sessions[/{id}]`, `POST /api/upload`, all gated by shared-password auth that already accepts cookies (`session` cookie in `auth.py`). Phase 9's job is to mount that backend surface in a browser-usable form.

**Primary tech decision: Vanilla JS + CSS, no build step.** Rationale: (1) Phase 10 requires "a single documented command" — adding `npm install && npm run build` to that command makes it two undocumented steps; (2) the UI surface is modest (login, chat thread, sidebar, upload, citation popovers — no complex reactive graph); (3) FastAPI's `StaticFiles` mounts a directory of HTML/CSS/JS directly, no adapter needed; (4) the primary risk in Phase 9 is wiring five distinct features correctly against a real async backend, not the richness of the component model. A JS framework would add complexity without reducing risk here.

The backend needs exactly two additive changes: (a) `POST /api/login` endpoint (validates password, returns a session cookie) and (b) a `StaticFiles` mount at `/app` serving `webapp/frontend/`. Everything else (the cookie-based auth, the WebSocket streaming, the session/upload APIs) is already in place.

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| UI-01 | Chat-style message thread showing question/answer turns | Pattern 1: DOM-append thread, session_id sticky |
| UI-02 | Live tool-call activity view sourced from the WS stream | Pattern 2: browser WebSocket client, inline activity panel |
| UI-03 | Citation tags render as inspectable elements resolving to audit log entries | Pattern 3: AskResponse.citations map + citation renderer |
| UI-04 | Session sidebar listing past sessions, resumable | Pattern 4: GET /api/sessions polling, session_id cookie |
| UI-05 | Dataset upload control (drag-drop or picker) in composer | Pattern 5: FormData POST /api/upload, progress inline |
| UI-06 | Login screen; no chat UI reachable before authenticating | Pattern 6: POST /api/login → Set-Cookie, JS gate |
| UI-07 | Visual style modeled on OpenClaw web UI — dark theme, sidebar+panel, replicated not imported | Pattern 7: CSS custom properties, layout grid |
</phase_requirements>

## Standard Stack

| Layer | Choice | Why |
|-------|--------|-----|
| Frontend language | Vanilla JS (ES2022, modules) | No build step; no Node/npm in Phase 10 command |
| Bundler | None — FastAPI serves raw `.js` files as ES modules | `<script type="module">` supported by all modern browsers |
| CSS | Custom properties (`--color-*`, `--spacing-*`) + CSS Grid/Flex | Replicates OpenClaw dark theme without importing any OpenClaw code |
| Static serving | `fastapi.staticfiles.StaticFiles` mounted at `/app` | Already in `fastapi[standard]` install; zero new dependency |
| Auth | `POST /api/login` → `Set-Cookie: session=<password>; Path=/; SameSite=Strict; HttpOnly` | Cookie reuse pattern already wired in `auth.py`; browser sends it on every request automatically, including WS upgrade |
| WS client | Browser-native `WebSocket` | No library needed; same `?password=<...>` or cookie pattern already tested in Phase 7 WS auth |
| Testing | pytest + `starlette.testclient.TestClient` (existing) | Matches project convention (no `pytest-asyncio`, no JS test framework); fast-tier tests verify Python-side: static serving, login endpoint, HTML file content |

## Architecture Patterns

### Pattern 1: FastAPI StaticFiles mount + /api/login endpoint

```python
# webapp/backend/main.py — two additive changes
from fastapi.staticfiles import StaticFiles

# After all /api/* routes are registered, mount static files.
# /app/index.html is the single HTML page; JS/CSS served from same dir.
app.mount("/app", StaticFiles(directory="webapp/frontend", html=True), name="frontend")

@app.post("/api/login")
async def login(
    req: LoginRequest,
    response: Response,
) -> LoginResponse:
    from webapp.backend.auth import _valid
    if not _valid(req.password):
        raise HTTPException(status_code=401, detail="unauthorized")
    response.set_cookie(
        key="session",
        value=req.password,
        httponly=True,
        samesite="strict",
        path="/",
    )
    return LoginResponse(ok=True)
```

`LoginRequest(password: str)` and `LoginResponse(ok: bool)` are new Pydantic models in `schemas.py`.

**Key constraint:** `require_password` already reads `session: str | None = Cookie(default=None)` — so after `POST /api/login` sets the cookie, every subsequent `/api/*` and `/ws/*` call automatically carries it without any JS header-injection. This is the same cookie path Phase 7's RESEARCH.md anticipated for Phase 9 ("future-proofing for Phase 9's login flow, which will set a cookie once and let both HTTP and WS reuse it automatically").

### Pattern 2: Frontend file layout

```
webapp/frontend/
├── index.html          # App shell: login overlay + chat layout; no framework
├── style.css           # Dark theme, sidebar + main panel layout, chat bubbles, activity view
├── main.js             # Entry: detect auth state → show login or chat; imports modules
├── api.js              # Fetch wrapper (reads session cookie via include:"credentials"),
│                       # WebSocket manager, all endpoint functions
├── chat.js             # Chat thread component: message rendering, composer, upload
├── citations.js        # Citation renderer: parse [ref:…], lookup from AskResponse.citations
└── sessions.js         # Session sidebar: GET /api/sessions, session_id resume logic
```

All `.js` files are ES modules: `<script type="module" src="./main.js">` in `index.html`.

### Pattern 3: Login flow (UI-06)

```
index.html loads
  → main.js: try GET /api/sessions (credentialed)
    → 401 → show #login-overlay (hidden by default behind #app)
    → 200 → hide #login-overlay, show #app, boot chat
  
  #login-overlay submit:
    → POST /api/login {password}
    → 200 + Set-Cookie → reload page (triggers auth check again → boot chat)
    → 401 → show error message in login form
```

No client-side cookie reading (HttpOnly); the auth check uses a sentinel API call (`GET /api/sessions`) — if it returns 200, the cookie is valid; if 401, show login.

### Pattern 4: Chat thread + live activity (UI-01, UI-02)

```javascript
// chat.js — message submission flow
async function sendMessage(question, sessionId) {
    const streamId = crypto.randomUUID();
    
    // 1. Open WS before POST (required by streaming.py — events arrive during POST)
    const ws = api.openToolStream(streamId, {
        onEvent: (event) => renderActivityEvent(event),
        onClose: () => closeActivityView(),
    });
    
    // 2. Render "user" message bubble immediately
    appendMessage({ role: "user", content: question });
    
    // 3. Show live activity panel
    openActivityView();
    
    // 4. POST to /api/ask with session_id sticky
    const resp = await api.askQuestion(question, sessionId, streamId);
    
    // 5. Close WS, render agent answer with citations
    ws.close();
    appendMessage({ role: "assistant", content: resp.answer, citations: resp.citations });
    closeActivityView();
}
```

The WS must be opened before the POST. The `stream_id` is a client-generated UUID — same UUID passed to both `/api/ask` (as `stream_id`) and `/ws/{stream_id}`. The WS URL is `ws://localhost:PORT/ws/{stream_id}?session=<password>` — however, since `Set-Cookie: session=...; HttpOnly` means JS can't read it, the browser sends it automatically on the WS upgrade request as a cookie, matching `require_password_ws`'s `Cookie` parameter. No password injection in the WS URL is needed.

**Pitfall (from Phase 7 07-RESEARCH.md):** browser WS clients cannot set custom headers; the WS upgrade carries cookies but not `Authorization`. `require_password_ws` already reads the `session` cookie — this pattern is already implemented and tested in Phase 7.

### Pattern 5: Citation rendering (UI-03)

The `AskResponse` already contains `citations: list` — a list of `(tag, record_or_None)` tuples from `qa/session.py::verify_answer_citations()`. The frontend receives them as part of the JSON response.

```javascript
// citations.js
const CITATION_RE = /\[ref:([^:]+):([a-f0-9]{12})\]/g;

function renderAnswerWithCitations(answerText, citations) {
    // Build a lookup map: sha_prefix → citation record
    const citationMap = {};
    for (const [tag, record] of citations || []) {
        const match = CITATION_RE.exec(tag);
        if (match) citationMap[match[2]] = record;
    }
    CITATION_RE.lastIndex = 0;
    
    // Replace [ref:TOOL:SHA] with <button class="citation-ref" data-sha="SHA">
    return answerText.replace(CITATION_RE, (_, toolName, sha) => {
        const record = citationMap[sha];
        return `<button class="citation-ref" data-sha="${sha}" 
                        data-tool="${toolName}"
                        title="${toolName} — click to inspect">[${toolName}]</button>`;
    });
}

// Citation click → modal/overlay with the raw audit log record
function showCitationDetail(sha, citations) {
    const [_, record] = (citations || []).find(([tag]) => tag.includes(sha)) || [];
    if (!record) { showError("Citation not found in audit log"); return; }
    showModal(JSON.stringify(record, null, 2));
}
```

No backend request needed — the full citation records are already in `AskResponse.citations`.

**Note:** `citations` in `AskResponse` is typed as `list` (untyped in schemas.py). The actual shape from `qa/session.py::verify_answer_citations()` is `list[tuple[str, dict | None]]` where the dict is the raw JSONL audit log entry. The frontend treats it as an array of `[tag, record_or_null]` pairs.

### Pattern 6: Session sidebar (UI-04)

```javascript
// sessions.js
async function loadSessionList() {
    const {sessions} = await api.listSessions();
    renderSessionList(sessions);  // populates #session-list sidebar
}

function resumeSession(sessionId) {
    currentSessionId = sessionId;
    clearChatThread();
    // Re-fetch session's recent_datasets for display (no full history replay — API-03
    // returns metadata only, not the full message log; history is agent-internal SQLite).
    api.getSession(sessionId).then(renderSessionDetail);
    updateSessionTitle(sessionId);
}
```

**Known limitation (document in PLAN):** The Phase 7-8 API does not expose the full message history for a session — only `recent_datasets` and metadata from `GET /api/sessions/{session_id}`. "Resuming" a session means re-associating subsequent questions with that `session_id` so the agent has its `SessionMemory` context; the visual message thread does not replay prior messages. This is correct behavior for this milestone (the thread shows turns from the current browser session, not stored prior turns).

### Pattern 7: Dataset upload (UI-05)

```javascript
// In chat.js composer
async function uploadDataset(files, name) {
    const formData = new FormData();
    formData.append("name", name);
    for (const f of files) formData.append("files", f);
    
    appendMessage({ role: "system", content: `Uploading ${name}...` });
    const result = await api.uploadDataset(formData);
    
    if (result.status === "success") {
        appendMessage({ role: "system", content: 
            `Dataset "${name}" ingested as ${result.dataset_id}. Session: ${result.session_id}.`});
        currentSessionId = result.session_id;
    } else {
        appendMessage({ role: "system", content: `Upload failed: ${result.detail}` });
    }
}
```

Drag-and-drop: `dragover/drop` event listeners on the composer area; file picker: `<input type="file" multiple accept=".h5,.h5ad,.mtx,.tsv.gz">`.

### Pattern 8: OpenClaw visual style (UI-07)

OpenClaw's web UI uses a dark theme with:
- Background: `#0d0d0d` (page) / `#1a1a1a` (panels) / `#2a2a2a` (input areas)
- Text: `#e0e0e0` (primary) / `#888` (secondary)
- Accent: `#6b7cff` (blue-purple), `#4ade80` (green for success)
- Layout: 240px fixed sidebar on left, main panel fills remaining width
- Font: system-ui / monospace for code blocks
- Message bubbles: user = right-aligned with subtle border, assistant = left-aligned, wider

Replication strategy: CSS custom properties in `:root` (e.g., `--bg-page`, `--bg-panel`, `--accent-primary`) + CSS Grid for the outer shell layout. No OpenClaw CSS is imported; these values are harvested by visual inspection of the OpenClaw web UI and expressed as independent CSS.

## Pitfalls

| # | Pitfall | Risk | Mitigation |
|---|---------|------|------------|
| 1 | WS opened after POST — early tool events lost | HIGH | `api.openToolStream(streamId)` must return before `api.askQuestion()` is called; document order in chat.js |
| 2 | StaticFiles mount shadow `/api/*` routes | MEDIUM | Mount at `/app` not `/` — all `/api/*` and `/ws/*` routes remain unaffected; mount order: API routes registered first, StaticFiles mounted last |
| 3 | Citation `citations` list is `list` (untyped) in schemas.py — frontend can't rely on exact shape | LOW | Treat as array of `[tag, record_or_null]` pairs; null-guard everywhere |
| 4 | HttpOnly cookie → JS can't read it to inject into WS URL | RESOLVED | browser sends cookie on WS upgrade automatically; `require_password_ws` already reads `session` cookie; tested in Phase 7 |
| 5 | Session history replay — users expect to see prior messages on resume | DESIGN | Document explicitly: Phase 9 shows current-tab thread only; full history replay deferred (API-03 returns metadata, not message log). Show session's `recent_datasets` as thread context. |
| 6 | `StaticFiles(html=True)` serves `index.html` for unmatched paths — conflicts with SPA routing | LOW | Only one "page" (index.html); no client-side routing needed; `/app` → index.html is the only entrypoint |
| 7 | ES module `import` cross-origin from `file://` — won't work if opened directly in browser | LOW | Frontend only served via FastAPI (`uvicorn`); opening `index.html` directly is unsupported, documented in Phase 10 |
| 8 | `POST /api/login` is unauthenticated — must NOT depend on `require_password` | CRITICAL | `POST /api/login` has no `Depends(require_password)` — it IS the authentication step; `_valid()` is called directly inside the handler |

## Test Strategy

All fast-tier tests are Python pytest via `TestClient`. No JS test framework is added.

| Test | Requirement | Command |
|------|-------------|---------|
| GET /app/ returns 200 HTML with login form | UI-06 | `pytest tests/test_webapp_frontend.py::test_login_page_served -x` |
| POST /api/login with correct password → 200 + Set-Cookie | UI-06 | `pytest tests/test_webapp_frontend.py::test_login_sets_cookie -x` |
| POST /api/login with wrong password → 401 | UI-06 | `pytest tests/test_webapp_frontend.py::test_login_rejects_bad_password -x` |
| GET /app/api.js, /app/chat.js etc. → 200 text/javascript | all | `pytest tests/test_webapp_frontend.py::test_static_js_files_served -x` |
| index.html contains #login-overlay, #app, #session-list | UI-06, UI-04 | `pytest tests/test_webapp_frontend.py::test_html_structure -x` |
| api.js contains askQuestion, openToolStream, uploadDataset, listSessions | UI-01..05 | `pytest tests/test_webapp_frontend.py::test_api_js_exports -x` |
| chat.js contains sendMessage, appendMessage, renderActivityEvent | UI-01..02 | `pytest tests/test_webapp_frontend.py::test_chat_js_exports -x` |
| citations.js contains renderAnswerWithCitations, showCitationDetail | UI-03 | `pytest tests/test_webapp_frontend.py::test_citations_js_exports -x` |
| sessions.js contains loadSessionList, resumeSession | UI-04 | `pytest tests/test_webapp_frontend.py::test_sessions_js_exports -x` |
| POST /api/login does NOT have require_password dependency | UI-06 (security) | verify by calling without cookie → still gets 401 on wrong password, but does not 401 before trying |
| style.css contains --bg-page, --bg-panel, --accent-primary | UI-07 | `pytest tests/test_webapp_frontend.py::test_css_design_tokens -x` |

**Browser / manual testing** is reserved for Phase 10's human-verify checkpoint (run `uvicorn`, open browser, exercise all seven UI requirements manually).

## Validation Architecture

The Phase 9 validation strategy uses the existing `pytest` infrastructure with one new test file (`tests/test_webapp_frontend.py`) focused on:
1. Static file serving (FastAPI `StaticFiles` integration)
2. `POST /api/login` endpoint correctness (cookie set, bad-password rejection)
3. HTML structure assertions (key IDs present in `index.html`)
4. JS/CSS file content assertions (function names, CSS custom properties)

No Wave 0 dependency on new external libraries — `starlette.testclient.TestClient` (already in `fastapi[standard]`) handles all fast-tier tests. No `pytest-asyncio` needed (matches project convention).

**Quick run:** `uv run --extra web pytest tests/test_webapp_frontend.py -m "not live_llm" -x`
**Full suite:** `uv run --extra web pytest tests/ -x -q -m "not live_llm and not bio_fm_smoke and not vcc_data"`
**Max feedback latency:** ~15 seconds (static file tests are pure HTTP, no LLM calls)

## RESEARCH COMPLETE
