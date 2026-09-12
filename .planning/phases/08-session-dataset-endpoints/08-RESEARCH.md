# Phase 8: Session & Dataset Endpoints - Research

**Researched:** 2026-09-12
**Domain:** FastAPI HTTP endpoints extending an existing password-gated backend (Phase 7); SQLite-backed session listing; multipart file upload feeding an existing ingest pipeline
**Confidence:** MEDIUM-HIGH (FastAPI multipart-upload and dependency patterns are official-docs-verified HIGH confidence; the session-listing schema extension and the upload-to-conversation wiring are original synthesis over this repo's existing `SessionMemory`/`ingest_10x`/`run_session` code, since neither has any precedent to copy — flagged MEDIUM and called out explicitly below)

## Summary

Phase 8 adds two capabilities to the `webapp/backend/` FastAPI app Phase 7 already built and verified (`POST /api/ask`, `WS /ws/{stream_id}`, shared-password gate in `auth.py`): session list/resume (API-03) and dataset upload (API-04). Both requirements say "backed by the existing `SessionMemory`" / "invokes `ingest_10x`" — the intent is clearly to wrap what already exists, not build new pipelines. But direct inspection of the existing code surfaces two real gaps the planner must close, not just wrap:

1. **`ask_question()`/`main.py::ask()` currently drop `session_id` on the floor.** `AskRequest.session_id` already exists in `schemas.py` but `main.py`'s `ask()` handler never reads it, and `qa/session.py::ask_question()` has no `session_id` parameter at all (only `session_memory`). Every `POST /api/ask` today generates a brand-new random `session_id` via `run_session()`'s internal `uuid.uuid4()` fallback, regardless of what the client sends. **Resume is structurally impossible until this is fixed** — this is the single highest-priority finding of this research.
2. **`SessionMemory` (agent/memory.py) has no way to enumerate sessions.** Its one table (`session_memory`) stores `(session_id, dataset_id, note, created_at)` rows written only when a tool call happens to produce a `dataset_id` — there is no `sessions` table, no `list_sessions()` method, and no row written just because a session started. A session where the user never triggers a dataset-producing tool call is invisible to any query. This needs an additive schema/method extension, not just a new read query.

The recommended design is fully additive, following this repo's own established pattern (Phase 6's `system_prompt` kwarg, Phase 7's `extra_hooks` kwarg): add a `session_id: str | None = None` parameter to `ask_question()` forwarded to `run_session()`'s existing `session_id` parameter (already present, just never reached from the web layer); add a `sessions` table + `touch()`/`list_sessions()`/`session_exists()` methods to `SessionMemory`, called once per `run_session()` invocation so every session — not just ones with a dataset-producing tool call — becomes listable. For upload (API-04), the standard FastAPI multipart pattern (`UploadFile` + `Form`) applies directly, but the real-world 10x MEX (`.mtx`) format is **three separate gzipped files** (`matrix.mtx.gz`, `barcodes.tsv.gz`, `features.tsv.gz`), not one — confirmed against this repo's own `loaders.py`/`conftest.py` fixtures and scanpy's `read_10x_mtx` docstring. The upload endpoint must accept `list[UploadFile]` (1 file for `.h5`/`.h5ad`, 3 exact-named files for `.mtx`), stage them into a temp directory/file, invoke `ingest_10x()` with the **same `store_root`** the agent's MCP tools already use (`agent.tools.STORE_ROOT`), and — to make the result "part of the conversation flow" per API-04's literal wording — call `SessionMemory.record()` for the resulting `dataset_id` against the request's `session_id`, so the very next question in that session recalls it via the already-existing `_recall_preamble()` mechanism.

**Primary recommendation:** Fix the `session_id` plumbing gap first (small, additive, testable in isolation, unblocks resume); extend `SessionMemory` with a `sessions` table and three new methods (additive, does not touch the existing `session_memory` table or its tests); add `GET /api/sessions` (list) sourced from the new table; treat "resume" as reusing the now-fixed `POST /api/ask` with an existing `session_id` (no separate no-op "resume" endpoint needed) plus an optional `GET /api/sessions/{session_id}` detail/existence-check route; add `POST /api/upload` accepting `list[UploadFile]` + `name` + optional `session_id` Form fields, staging to a temp path, calling `ingest_10x(..., store_root=agent.tools.STORE_ROOT)`, and recording the result into `SessionMemory` for conversational continuity.

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-------------------|
| API-03 | Backend exposes endpoints to list existing sessions and to resume a session by ID, backed by the existing `SessionMemory` (SQLite) layer | See "Architecture Patterns" Pattern 1 (session_id plumbing fix) and Pattern 2 (`sessions` table + list/resume endpoints) — this is the highest-risk item, addressed in depth below |
| API-04 | Backend exposes an upload endpoint that accepts a `.mtx`/`.h5` dataset and invokes `ingest_10x` as part of the conversation flow | See "Architecture Patterns" Pattern 3 (multipart upload, `.mtx` three-file reality) and Pattern 4 (tying upload result into `SessionMemory` for conversational recall) |
</phase_requirements>

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|---------------|
| `fastapi[standard]` | 0.141.1 (already installed, confirmed via `uv run python -c "import fastapi; print(fastapi.__version__)"`) | `UploadFile`/`Form`/`File` multipart handling, existing routing | Already the project's chosen web framework (Phase 7); no new dependency needed |
| `python-multipart` | 0.0.32 (already installed, bundled transitively via `fastapi[standard]`) | Parses `multipart/form-data` request bodies for file uploads | Required by FastAPI for any `UploadFile`/`Form` parameter; confirmed present, no `uv add` needed |
| stdlib `tempfile`, `shutil` | builtin | Stage uploaded bytes to a real filesystem path/directory before calling `ingest_10x()` (which takes a `path`, not bytes) | No new dependency; matches this repo's convention of hand-rolling only genuinely small glue code |
| stdlib `sqlite3` | builtin | Extend `agent/memory.py::SessionMemory`'s existing connection/table pattern with a new `sessions` table | Mirrors the exact pattern already used for the `session_memory` table and `ingest/store.py::DatasetStore`'s `datasets` table — no new dependency, no ORM |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| none new | — | — | This phase introduces zero new third-party dependencies — everything needed (multipart parsing, SQLite, tempfile) is already installed or stdlib |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Hand-rolled `sessions` table on `SessionMemory` | A separate "chat transcript" store persisting full question/answer text per turn | Requirements explicitly say "backed by the existing `SessionMemory` (SQLite) layer" and this repo's own AGENT-03 precedent already defines "session context" as *dataset references*, not raw transcript replay — see Open Questions below for the one real product-level ambiguity here |
| Accepting upload as a single `UploadFile` | Accepting a `.zip`/`.tar` archive and extracting server-side | A single-file model cannot represent real 10x MEX (`.mtx`) data, which is inherently 3 files; a zip-upload model adds an extraction step and a new failure mode (malformed archive) for no benefit over `list[UploadFile]`, which FastAPI supports natively and which lets a future frontend (Phase 9, UI-05) use a native multi-file `<input type="file" multiple>` |
| Recording upload result into `SessionMemory` directly | Routing the upload through a full `ask_question()` call with a synthesized prompt (e.g. "I uploaded dataset X") | Round-tripping through the LLM just to log an upload wastes a full agent turn/API call and risks the model paraphrasing/hallucinating around a mechanical fact; a direct `session_memory.record()` call (exactly what `record_dataset_reference()` already does for in-agent tool calls) is cheaper, deterministic, and immediately visible to the next real question via the existing recall-preamble mechanism |

**Installation:**
```bash
# No new dependencies -- fastapi[standard] (Phase 7) already bundles python-multipart.
# Confirm before starting Wave 0:
uv run python -c "import multipart; print('ok')"
```

## Architecture Patterns

### Recommended Project Structure
```
webapp/backend/
├── main.py          # ADD: GET /api/sessions, GET /api/sessions/{id}, POST /api/upload
├── auth.py          # unchanged -- reuse require_password on all new routes
├── streaming.py      # unchanged
├── deps.py           # ADD: get_session_memory() overridable factory
├── schemas.py         # ADD: SessionSummary, SessionListResponse, UploadResponse
└── uploads.py        # NEW: staging helper (write UploadFile(s) to temp path/dir, dispatch by count/suffix)
agent/
├── memory.py         # ADD: sessions table + touch()/list_sessions()/session_exists() on SessionMemory
└── session.py         # MODIFY: run_session() calls session_memory.touch(session_id) once per call
qa/
└── session.py         # MODIFY: ask_question() gains session_id: str | None = None, forwarded to run_session()
tests/
├── test_agent_memory.py         # ADD: touch/list_sessions/session_exists tests (existing file, additive)
├── test_qa_session.py            # ADD: session_id forwarding test (existing file, additive)
├── test_webapp_backend.py        # ADD: /api/sessions, /api/sessions/{id} tests (existing file, additive)
└── test_webapp_upload.py         # NEW: /api/upload fast-tier tests (.h5 single-file + .mtx 3-file cases)
```
This keeps every change additive to already-tested, already-verified modules (`agent/memory.py`, `agent/session.py`, `qa/session.py` all have passing test suites from Phases 3/6/7 that must keep passing unmodified) — the same discipline Phase 7's research and verification both called out explicitly.

### Pattern 1: Close the `session_id` plumbing gap (prerequisite for all of API-03)
**What:** `run_session()` already accepts and honors `session_id: str | None = None` (generates a fresh `uuid.uuid4()` only when `None`). `ask_question()` does not expose this parameter at all, and `webapp/backend/main.py::ask()` never reads `req.session_id` even though `AskRequest.session_id` already exists in `schemas.py`. Without this fix, passing a known `session_id` back to `/api/ask` has **zero effect** — a "resumed" session silently becomes a brand-new one every time, and Success Criterion 2 cannot be satisfied.
**When to use:** Wave 0 / first task of this phase — every other resume-related behavior depends on this.
**Example:**
```python
# qa/session.py -- additive parameter, mirrors extra_hooks's own precedent
async def ask_question(
    question: str,
    session_memory: SessionMemory | None = None,
    session_id: str | None = None,   # NEW
    log_path: Path = Path("tool_calls.jsonl"),
    extra_hooks: list | None = None,
) -> tuple[str, str, list]:
    texts, session_id = await run_session(
        question,
        session_memory=session_memory,
        session_id=session_id,        # NEW -- forwarded, not dropped
        log_path=log_path,
        system_prompt=QA_SYSTEM_PROMPT,
        extra_hooks=extra_hooks,
    )
    ...
```
```python
# webapp/backend/main.py -- read req.session_id, pass a shared SessionMemory
@app.post("/api/ask", dependencies=[Depends(require_password)])
async def ask(
    req: AskRequest,
    ask_question=Depends(deps.get_ask_question),
    session_memory=Depends(deps.get_session_memory),
) -> AskResponse:
    extra_hooks = []
    if req.stream_id:
        queue = streaming.get_or_create_queue(req.stream_id)
        extra_hooks.append(streaming.make_stream_hook(queue))
    answer, session_id, citations = await ask_question(
        req.question,
        session_memory=session_memory,
        session_id=req.session_id,     # NEW -- was previously ignored
        extra_hooks=extra_hooks,
    )
    return AskResponse(answer=answer, session_id=session_id, citations=citations)
```
**Verification:** existing `tests/test_webapp_backend.py::test_ask_returns_answer` passes an `_fake_ask_question` whose signature is `(question, session_memory=None, extra_hooks=None, log_path=None)` — it must be updated to also accept `session_id=None` or the dependency-injected real signature check will fail; a new fast-tier test should assert that a second `/api/ask` call with the same `session_id` produces a request to `ask_question` carrying that exact `session_id` (verified via a spy/fake, not the live SDK).

### Pattern 2: `SessionMemory` gains a `sessions` table for listing (API-03, "list existing sessions")
**What:** Add a second table to the same SQLite file `SessionMemory` already manages, plus three new methods. This is additive — the existing `session_memory` table, its schema, and all of `tests/test_agent_memory.py`'s five existing tests are untouched.
**When to use:** Any session must become listable the moment it starts, not only once a dataset-producing tool call happens to fire.
**Example:**
```python
# agent/memory.py -- additive table + methods, existing session_memory table/tests untouched
_CREATE_SESSIONS_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS sessions (
    session_id TEXT PRIMARY KEY,
    created_at TEXT NOT NULL,
    last_active_at TEXT NOT NULL
)
"""

class SessionMemory:
    def __init__(self, root: str | Path = "agent/memory.sqlite"):
        self.path = Path(root)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as conn:
            conn.execute(_CREATE_TABLE_SQL)
            conn.execute(_CREATE_SESSIONS_TABLE_SQL)   # NEW

    def touch(self, session_id: str) -> None:
        """Marks a session as active now, creating its row on first call.
        Must be called once per run_session() invocation -- this is what
        makes every session listable, not just ones with a dataset
        reference recorded."""
        now = datetime.now(timezone.utc).isoformat()
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO sessions (session_id, created_at, last_active_at) "
                "VALUES (?, ?, ?) "
                "ON CONFLICT(session_id) DO UPDATE SET last_active_at = excluded.last_active_at",
                (session_id, now, now),
            )
            conn.commit()

    def list_sessions(self, limit: int = 50) -> list[dict]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT session_id, created_at, last_active_at FROM sessions "
                "ORDER BY last_active_at DESC, rowid DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [
            {
                "session_id": r[0],
                "created_at": r[1],
                "last_active_at": r[2],
                "recent_datasets": self.recent_datasets(r[0]),
            }
            for r in rows
        ]

    def session_exists(self, session_id: str) -> bool:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT 1 FROM sessions WHERE session_id = ?", (session_id,)
            ).fetchone()
        return row is not None
```
```python
# agent/session.py -- one new line inside the existing run_session() body
session_memory = session_memory or SessionMemory()
session_id = session_id or str(uuid.uuid4())
session_memory.touch(session_id)   # NEW -- makes every session listable (API-03)
options = build_options(...)
```
```python
# webapp/backend/main.py
@app.get("/api/sessions", dependencies=[Depends(require_password)])
async def list_sessions(session_memory=Depends(deps.get_session_memory)) -> SessionListResponse:
    return SessionListResponse(sessions=session_memory.list_sessions())

@app.get("/api/sessions/{session_id}", dependencies=[Depends(require_password)])
async def get_session(session_id: str, session_memory=Depends(deps.get_session_memory)) -> SessionSummary:
    if not session_memory.session_exists(session_id):
        raise HTTPException(status_code=404, detail="unknown session_id")
    return SessionSummary(
        session_id=session_id,
        recent_datasets=session_memory.recent_datasets(session_id),
    )
```
**"Resume" is not a separate write-side endpoint** — resuming means the client already has a `session_id` (from `GET /api/sessions`) and includes it in a normal `POST /api/ask` body; Pattern 1's fix is what makes that actually continue the same session's dataset-reference context via `_recall_preamble()`. `GET /api/sessions/{session_id}` exists to let a frontend validate/display a session before the user types their next question (Phase 9, UI-04) — this is Claude's-discretion API shape, not literally specified by REQUIREMENTS.md.

### Pattern 3: Multipart upload with the real `.mtx` 3-file shape (API-04)
**What:** FastAPI's official pattern for multiple files under one field name is `files: Annotated[list[UploadFile], File()]`, combined with `Form()` fields for `name`/`session_id` in the same `multipart/form-data` request (verified against current FastAPI docs, `fastapi.tiangolo.com/tutorial/request-files/`, Sep 2026). This repo's own `ingest/loaders.py::load()` and `tests/conftest.py` fixtures confirm the real shape: a `.h5`/`.h5ad` upload is **one file**, but a `.mtx` (10x MEX format) upload is **three files with fixed names** — `matrix.mtx.gz`, `barcodes.tsv.gz`, `features.tsv.gz` (scanpy's `sc.read_10x_mtx` reads a directory and expects exactly these names, or a shared `prefix` — it does not fuzzy-match arbitrary filenames).
**When to use:** The one upload endpoint this phase needs.
**Example:**
```python
# webapp/backend/main.py
from typing import Annotated
from fastapi import File, Form, UploadFile

@app.post("/api/upload", dependencies=[Depends(require_password)])
async def upload_dataset(
    name: Annotated[str, Form()],
    files: Annotated[list[UploadFile], File()],
    session_id: Annotated[str | None, Form()] = None,
    session_memory=Depends(deps.get_session_memory),
) -> UploadResponse:
    try:
        staged_path = await uploads.stage(files)          # tempfile dir or single file path
        dataset_id = ingest_10x(staged_path, name, store_root=agent_tools.STORE_ROOT)
    except Exception as exc:
        return UploadResponse(status="error", detail=str(exc), dataset_id=None)
    finally:
        uploads.cleanup(staged_path)
    if session_id:
        session_memory.touch(session_id)
        session_memory.record(session_id, dataset_id, note=f"uploaded via /api/upload: {name}")
    return UploadResponse(status="success", dataset_id=dataset_id, detail=None)
```
```python
# webapp/backend/uploads.py -- staging helper
import shutil
import tempfile
from pathlib import Path
from fastapi import UploadFile

_MTX_NAMES = {"matrix.mtx.gz", "barcodes.tsv.gz", "features.tsv.gz"}

async def stage(files: list[UploadFile]) -> Path:
    if len(files) == 1:
        f = files[0]
        suffix = Path(f.filename or "").suffix
        if suffix not in (".h5", ".h5ad"):
            raise ValueError(
                f"Single-file upload must be .h5 or .h5ad, got {f.filename!r}. "
                "A .mtx (10x MEX) dataset requires 3 files: "
                "matrix.mtx.gz, barcodes.tsv.gz, features.tsv.gz."
            )
        tmp = Path(tempfile.mkdtemp()) / f.filename
        with tmp.open("wb") as out:
            shutil.copyfileobj(f.file, out)   # stream, don't load whole file into memory
        return tmp

    names = {f.filename for f in files}
    if names != _MTX_NAMES:
        raise ValueError(
            f"3-file upload must be exactly {sorted(_MTX_NAMES)}, got {sorted(names)}"
        )
    tmp_dir = Path(tempfile.mkdtemp())
    for f in files:
        with (tmp_dir / f.filename).open("wb") as out:
            shutil.copyfileobj(f.file, out)
    return tmp_dir

def cleanup(path: Path) -> None:
    root = path if path.is_dir() else path.parent
    shutil.rmtree(root, ignore_errors=True)
```
Source: FastAPI official docs (multipart `File`+`Form` pattern, verified live Sep 2026), this repo's own `ingest/loaders.py` docstring + `tests/conftest.py` fixture-writing code (exact `.mtx` filename requirements), scanpy `sc.read_10x_mtx` docstring (`prefix`/`compressed` parameters, confirmed via `inspect.signature` against the installed `scanpy` package).

### Pattern 4: Tie the upload result into the conversation (API-04's "as part of the conversation flow")
**What:** After a successful `ingest_10x()` call, calling `session_memory.record(session_id, dataset_id, note=...)` makes the new dataset visible to `_recall_preamble()` on the *next* question in that session — exactly the same mechanism `record_dataset_reference()` already uses for in-agent tool calls (AGENT-03). No LLM round-trip is needed just to log the fact of the upload.
**When to use:** Every successful upload where the client supplies a `session_id` (a client uploading with no session context yet should also get one minted — see Open Questions).
**Example:** shown inline in Pattern 3 above (`session_memory.touch(session_id); session_memory.record(session_id, dataset_id, ...)`).

### Anti-Patterns to Avoid
- **Reading `req.session_id` and forgetting to also pass it to `ask_question()`'s new parameter** — the schema field has existed since Phase 7 but was silently unused; a superficial code read of `main.py` could miss that this is a *live* bug, not a hypothetical one.
- **Using `agent/memory.py`'s default `SessionMemory()` root implicitly in the upload endpoint** while the `/api/ask` endpoint uses a different instance/path — always inject via `deps.get_session_memory()` so both routes share the exact same SQLite file (`agent/memory.sqlite` by default, overridable for tests).
- **Calling `ingest_10x()` with the default `store_root="data"` instead of `agent.tools.STORE_ROOT`** — `agent/tools.py`'s `ingest_10x_tool`/`analyze_dataset_tool` read `STORE_ROOT` (defaulting to `"data"`, overridable via `BIOCLAW_STORE_ROOT`) as a **module-level constant set once at import time**. If the upload endpoint hardcodes `"data"` instead of importing and reusing `agent.tools.STORE_ROOT`, an uploaded dataset could silently write to the wrong store root in any environment where `BIOCLAW_STORE_ROOT` is set, making it invisible to the agent's own `analyze_dataset`/`annotate_cell_type` tool calls in the same conversation — a subtle, hard-to-notice split-brain bug.
- **`await file.read()` on a large single-cell `.h5` file** — reads the entire upload into memory at once; prefer streaming via `shutil.copyfileobj(file.file, dest)` (as shown above) so multi-hundred-MB datasets don't spike process memory.
- **Requiring fuzzy/case-insensitive `.mtx` filename matching** — scanpy's `sc.read_10x_mtx` expects exact names (or an exact shared `prefix`); validate filenames explicitly at the API boundary and return a clear error rather than letting a cryptic scanpy `FileNotFoundError` leak through.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|--------------|-----|
| Multipart file parsing | Manual `Content-Type: multipart/form-data` boundary parsing | FastAPI's `UploadFile`/`File`/`Form` (backed by `python-multipart`, already installed) | Handles boundary parsing, streaming, and temp-file spooling for large uploads correctly; hand-rolling this is exactly the "deceptively complex" trap |
| Session enumeration | A brand-new bespoke session-tracking service/table outside `SessionMemory` | Extend `SessionMemory` itself with a `sessions` table (Pattern 2) | REQUIREMENTS.md is explicit that API-03 must be "backed by the existing `SessionMemory` (SQLite) layer" — a parallel tracking mechanism would violate that literally and create two sources of truth for "what sessions exist" |
| 10x MEX format parsing/validation | A custom `.mtx`/`.tsv` reader | `ingest_10x()` -> `ingest/loaders.py::load()` -> `scanpy.read_10x_mtx`/`read_10x_h5` (already built, tested, QC'd in Phase 1) | This is the entire point of the phase requirement's wording ("invokes `ingest_10x`") — the upload endpoint's only new-code responsibility is staging bytes to a filesystem path FastAPI hands you, not parsing genomics formats |

**Key insight:** Every genuinely new line of code this phase needs is either (a) a small additive fix to an existing, already-tested function's parameter list, (b) a new table/method on an existing SQLite-backed class following its own established pattern, or (c) a thin multipart-to-filesystem staging shim in front of a pipeline function that already exists and is already tested. There is no case here for a new dependency, framework, or subsystem.

## Common Pitfalls

### Pitfall 1: `session_id` silently dropped end-to-end (see Pattern 1)
**What goes wrong:** A client sends `{"question": "...", "session_id": "abc-123"}` expecting to resume; the backend accepts it (Pydantic validates fine, since the field already exists), returns 200, but the answer comes from a brand-new session with none of the prior dataset context — because `session_id` is validated but never forwarded past `main.py`.
**Why it happens:** The field was added to `AskRequest` in Phase 7 as forward-looking schema (for Phase 8), but the plumbing that would actually use it was correctly out of scope for Phase 7 and was never wired.
**How to avoid:** Pattern 1's fix, verified by a fast-tier test that asserts a spy `ask_question` receives the exact `session_id` passed in, and a second test that two sequential `/api/ask` calls with the same `session_id` produce the same `recent_datasets()` recall on the second call (using a fake `SessionMemory`/fake tool response, not the live SDK).
**Warning signs:** A manual resume test shows a correct-looking 200 response but the answer has no awareness of a dataset mentioned in an earlier turn.

### Pitfall 2: Sessions with no dataset-producing tool call are invisible to `GET /api/sessions`
**What goes wrong:** If session listing is implemented as `SELECT DISTINCT session_id FROM session_memory` (the *existing* table) instead of adding the new `sessions` table, any session where the user asked a question that never triggered a tool call that returns a `dataset_id` (e.g. an off-topic question, or a question answered from a prior recalled dataset without re-ingesting) simply never appears in the list.
**Why it happens:** `session_memory`'s only write path is `record_dataset_reference()`, itself only invoked from inside a `PostToolUse` hook when a tool response happens to contain a `dataset_id` key.
**How to avoid:** Add the separate `sessions` table + `touch()` call inside `run_session()` itself (Pattern 2), independent of whether any tool call happens during that turn.
**Warning signs:** A verification step that starts a session, asks a single non-ingest question, then checks `GET /api/sessions` and finds the session missing.

### Pitfall 3: Upload writes to a different `store_root` than the agent's tools read from
**What goes wrong:** A dataset uploaded via `/api/upload` returns a `dataset_id` string, but a follow-up chat question asking the agent to analyze that dataset fails with "unknown dataset" because `analyze_dataset_tool`'s `STORE_ROOT` constant points somewhere else.
**Why it happens:** `agent/tools.py::STORE_ROOT` is read from `BIOCLAW_STORE_ROOT` (or defaults to `"data"`) once at **module import time**; if the upload endpoint independently defaults `ingest_10x(..., store_root="data")` without importing the same constant, the two can diverge in any environment that overrides `BIOCLAW_STORE_ROOT` (e.g. a test fixture, a future deploy config).
**How to avoid:** Import and reuse `agent.tools.STORE_ROOT` directly in the upload endpoint rather than re-deriving/hardcoding it (see Pattern 3, Anti-Patterns).
**Warning signs:** An end-to-end test uploads a dataset, then asks the agent to analyze it by name, and gets a "dataset not found"-shaped tool error even though the upload endpoint reported success.

### Pitfall 4: `.mtx` upload treated as a single file
**What goes wrong:** A naive implementation (`file: UploadFile` singular) can only ever represent a `.h5`/`.h5ad` upload; there is no valid way to upload a real 10x MEX `.mtx` dataset through a single-file field, because MEX format is inherently 3 files, confirmed both by this repo's own test fixtures (`tests/conftest.py`'s `tiny_mtx_dir`) and scanpy's own `read_10x_mtx` API surface (reads a *directory*, not a file).
**Why it happens:** The requirement's plain-English phrasing ("accepts a `.mtx`/`.h5` dataset file") reads as if both are single files; `.h5` genuinely is, `.mtx` (as shorthand for the MEX format) is not.
**How to avoid:** Design the endpoint around `list[UploadFile]` from the start (Pattern 3) — it costs nothing extra for the `.h5` single-file case and is required for the `.mtx` case.
**Warning signs:** A verification step tries to `curl -F "files=@matrix.mtx.gz"` alone and gets a scanpy-level `FileNotFoundError` for `barcodes.tsv.gz` deep in a traceback instead of a clean 4xx.

### Pitfall 5: Uncaught `ingest_10x()` exceptions crash the request instead of surfacing as a conversational result
**What goes wrong:** `ingest_10x()` can raise (bad file format, QC threshold rejecting every cell, a duplicate dataset `name`/version race, etc.) — if the upload endpoint doesn't catch this, FastAPI returns a bare 500 with no structured body, which is a poor fit for "returns the ingest result/status as part of the conversation flow" (API-04's own wording implies the *failure* is also a conversational fact, not just success).
**Why it happens:** `agent/tools.py`'s existing MCP tool handlers (`ingest_10x_tool` etc.) already catch all exceptions and return a structured `is_error: True` result instead of propagating — the upload endpoint is the one new place in this phase that touches `ingest_10x()` directly and must adopt the same discipline independently.
**How to avoid:** Wrap the `ingest_10x()` call in `try/except Exception` and return a `UploadResponse(status="error", detail=str(exc))` with a 200 (or a deliberately chosen 4xx/5xx — Claude's discretion, but must be consistent and documented) rather than letting an unhandled exception produce a bare framework 500.
**Warning signs:** A verification step uploads a deliberately malformed dataset and gets an opaque 500 with a Python traceback in the body instead of a clean, renderable error.

## Code Examples

### Fast-tier test pattern for session resume (extends existing `tests/test_webapp_backend.py` conventions)
```python
async def _fake_ask_question(question, session_memory=None, session_id=None, extra_hooks=None, log_path=None):
    if session_memory is not None and session_id:
        session_memory.touch(session_id)
    return f"answer to: {question}", session_id or "new-sess", []

def test_ask_resumes_existing_session_id(monkeypatch, tmp_path):
    monkeypatch.setenv("BIOCLAW_WEB_PASSWORD", "testpass")
    app.dependency_overrides[deps.get_ask_question] = lambda: _fake_ask_question
    app.dependency_overrides[deps.get_session_memory] = lambda: SessionMemory(root=tmp_path / "m.sqlite")
    try:
        client = TestClient(app)
        resp = client.post(
            "/api/ask",
            json={"question": "q1", "session_id": "sess-42"},
            headers={"Authorization": "Bearer testpass"},
        )
        assert resp.json()["session_id"] == "sess-42"   # NOT a fresh uuid
    finally:
        app.dependency_overrides.clear()
```

### Fast-tier test pattern for upload (`.h5` single-file case)
```python
def test_upload_h5_returns_dataset_id(monkeypatch, tmp_path, tiny_h5_file):
    monkeypatch.setenv("BIOCLAW_WEB_PASSWORD", "testpass")
    monkeypatch.setattr(agent_tools, "STORE_ROOT", str(tmp_path / "store"))
    client = TestClient(app)
    with open(tiny_h5_file, "rb") as f:
        resp = client.post(
            "/api/upload",
            files={"files": ("sample.h5", f, "application/octet-stream")},
            data={"name": "uploaded-sample"},
            headers={"Authorization": "Bearer testpass"},
        )
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "success"
    assert body["dataset_id"].startswith("uploaded-sample@")
```
Source: pattern synthesized from FastAPI's official multipart-testing docs (`fastapi.tiangolo.com/tutorial/request-files/`, "Testing" section using `TestClient(...).post(url, files=...)`) combined with this repo's existing `tiny_h5_file`/`tiny_mtx_dir` fixtures (`tests/conftest.py`).

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|-------------------|---------------|--------|
| N/A | N/A | N/A | No FastAPI/multipart API surface used here has changed since Phase 7's research (both researched within the same week, Sep 2026); FastAPI 0.141.1 remains current |

**Deprecated/outdated:** None identified.

## Open Questions

1. **Is dataset-reference recall (`_recall_preamble`) a sufficient definition of "prior context intact" for Success Criterion 2, or does resume need literal raw conversation replay?**
   - What we know: This repo's own AGENT-03 requirement (v1.0, already shipped and verified) established "session context" to mean *dataset references recalled via a short preamble string*, not the SDK's own message history (which does not survive across separate `ClaudeSDKClient` instances/HTTP requests anyway — each `run_session()` call opens a fresh client). There is no mechanism anywhere in this codebase that persists actual question/answer text across requests.
   - What's unclear: Whether a researcher resuming a session tomorrow expects the agent to "remember" the literal prior Q&A exchange (which would require a new transcript-persistence mechanism beyond `SessionMemory`'s current scope) or just to have the previously-referenced dataset(s) back in context (which Pattern 1+2's fix already delivers).
   - Recommendation: Ship the dataset-reference-recall definition (consistent with AGENT-03 precedent and the requirement's own literal "backed by the existing SessionMemory" wording) for Phase 8. If Darren/the planner wants literal transcript replay, that is a materially larger change (a new persisted-turns table + prepending prior Q&A pairs into `run_session()`'s prompt) that should be called out as a distinct decision, not assumed silently.

2. **Exact HTTP status code / envelope for a failed upload (Pitfall 5)**
   - What we know: No CONTEXT.md exists for this phase (directory is empty) — nothing is locked. The existing agent tool-handler convention (`agent/tools.py`) returns success/failure as a body-level `is_error` flag with HTTP-agnostic semantics (it's not HTTP at all, it's an MCP tool result).
   - What's unclear: Whether the upload endpoint should mirror that (always 200, `status` field carries success/failure) or use standard HTTP semantics (4xx for validation errors like wrong file count/names, 200 only for a completed ingest, regardless of whether ingest itself found QC problems).
   - Recommendation: Use 422 for request-shape validation failures caught before `ingest_10x()` is even called (wrong file count/names — these are genuine client errors), and 200 with `status: "error"` for failures *inside* `ingest_10x()` itself (QC rejecting all cells, a malformed-but-present file) — this distinguishes "you sent the wrong thing" from "the pipeline ran and had a real result to report," and gives Phase 9's UI-05 a clean signal for whether to blame the user's file selection or render an in-thread ingest-failure message.

3. **Should an upload with no `session_id` still create/mint one, so the upload itself becomes a resumable session?**
   - What we know: `AskRequest.session_id` is optional; a first-ever interaction could plausibly be an upload (drag a file in before typing anything, per Phase 9's UI-05 composer-area upload control).
   - What's unclear: Whether the upload endpoint should generate a new `session_id` (via `str(uuid.uuid4())`) when none is supplied and return it in `UploadResponse`, so the frontend can carry it into the first `/api/ask` call, versus requiring the frontend to always call `/api/ask` first (which mints a `session_id` via existing `run_session()` behavior) before ever uploading.
   - Recommendation: Have the upload endpoint mint and return a `session_id` when none is supplied (cheap, `uuid.uuid4()` + `session_memory.touch()`), since Phase 9's most natural UX (upload-first) would otherwise have nowhere to attach the dataset reference. This is Claude's-discretion API shape, not a locked requirement.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest >= 8 (existing dev dependency, unchanged) |
| Config file | `pyproject.toml` (`[tool.pytest.ini_options]`) — no new markers needed; reuses `live_llm` only if a Phase 8 end-to-end checkpoint test is added (optional, discretion) |
| Quick run command | `pytest tests/test_webapp_backend.py tests/test_webapp_upload.py tests/test_agent_memory.py tests/test_qa_session.py -m "not live_llm" -x` |
| Full suite command | `pytest tests/ -m "not live_llm and not bio_fm_smoke and not vcc_data"` (unchanged convention from Phase 7) |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|---------------------|--------------|
| API-03 (session_id plumbing) | `ask_question()`/`/api/ask` forward `session_id` instead of discarding it | unit | `pytest tests/test_qa_session.py::test_ask_question_forwards_session_id tests/test_webapp_backend.py::test_ask_resumes_existing_session_id -x` | ❌ Wave 0 |
| API-03 (list) | `SessionMemory.touch()`/`list_sessions()` make every started session listable, most-recent-first | unit | `pytest tests/test_agent_memory.py::test_touch_creates_listable_session tests/test_agent_memory.py::test_list_sessions_orders_by_last_active -x` | ❌ Wave 0 |
| API-03 (list endpoint) | `GET /api/sessions` returns session IDs/metadata sourced from `SessionMemory`, password-gated | unit | `pytest tests/test_webapp_backend.py::test_list_sessions_returns_metadata tests/test_webapp_backend.py::test_list_sessions_rejected_without_password -x` | ❌ Wave 0 |
| API-03 (resume) | A second `/api/ask` call with a known `session_id` recalls dataset context recorded on a prior call | unit | `pytest tests/test_webapp_backend.py::test_resume_recalls_prior_dataset_reference -x` | ❌ Wave 0 |
| API-04 (upload, `.h5`) | `POST /api/upload` with one `.h5`/`.h5ad` file invokes `ingest_10x` and returns a `dataset_id` | unit | `pytest tests/test_webapp_upload.py::test_upload_h5_returns_dataset_id -x` | ❌ Wave 0 |
| API-04 (upload, `.mtx`) | `POST /api/upload` with the exact 3-file MEX set invokes `ingest_10x` and returns a `dataset_id` | unit | `pytest tests/test_webapp_upload.py::test_upload_mtx_trio_returns_dataset_id -x` | ❌ Wave 0 |
| API-04 (upload validation) | Wrong file count/names rejected with a clean 4xx, not a scanpy traceback | unit | `pytest tests/test_webapp_upload.py::test_upload_rejects_incomplete_mtx_set -x` | ❌ Wave 0 |
| API-04 (conversation flow) | A successful upload's `dataset_id` is recorded in `SessionMemory` and recalled by the next `/api/ask` call in the same session | unit | `pytest tests/test_webapp_upload.py::test_upload_result_recalled_in_next_question -x` | ❌ Wave 0 |
| API-04 (store_root consistency) | Upload endpoint writes to the same `store_root` `agent.tools`'s MCP tools read from | unit | `pytest tests/test_webapp_upload.py::test_upload_uses_agent_tools_store_root -x` | ❌ Wave 0 |
| API-03/API-04 (auth) | Both new endpoint families reject unauthenticated requests | unit | `pytest tests/test_webapp_backend.py::test_list_sessions_rejected_without_password tests/test_webapp_upload.py::test_upload_rejected_without_password -x` | ❌ Wave 0 |

### Sampling Rate
- **Per task commit:** `pytest tests/test_webapp_backend.py tests/test_webapp_upload.py tests/test_agent_memory.py tests/test_qa_session.py -m "not live_llm" -x`
- **Per wave merge:** `pytest tests/ -m "not live_llm and not bio_fm_smoke and not vcc_data"`
- **Phase gate:** Full fast suite green; if a `live_llm`-marked Phase 8 checkpoint is added (recommended, mirroring Phase 7's 07-03 pattern — real upload, real follow-up question, human-confirmed resume behavior), run it manually before `/gsd:verify-work`, matching Phase 7's precedent.

### Wave 0 Gaps
- [ ] `qa/session.py::ask_question()` — add `session_id: str | None = None` param, forward to `run_session()`
- [ ] `webapp/backend/main.py::ask()` — read and forward `req.session_id` (currently silently dropped — see Pitfall 1)
- [ ] `agent/memory.py::SessionMemory` — add `sessions` table + `touch()`/`list_sessions()`/`session_exists()` methods (additive; existing `session_memory` table/tests untouched)
- [ ] `agent/session.py::run_session()` — add one `session_memory.touch(session_id)` call so every session is listable regardless of tool-call activity
- [ ] `webapp/backend/deps.py` — add `get_session_memory()` overridable factory (mirrors `get_ask_question()`)
- [ ] `webapp/backend/schemas.py` — add `SessionSummary`, `SessionListResponse`, `UploadResponse` Pydantic models
- [ ] `webapp/backend/uploads.py` — new module: multipart staging helper (`.h5`/`.h5ad` single file vs. `.mtx` 3-file trio validation + tempfile write + cleanup)
- [ ] `webapp/backend/main.py` — add `GET /api/sessions`, `GET /api/sessions/{session_id}`, `POST /api/upload` routes, all password-gated
- [ ] `tests/test_agent_memory.py` — add touch/list_sessions/session_exists tests (existing file, additive)
- [ ] `tests/test_qa_session.py` — add session_id-forwarding test (existing file, additive)
- [ ] `tests/test_webapp_backend.py` — update `_fake_ask_question` signature to accept `session_id`; add session-list/resume tests (existing file, additive)
- [ ] `tests/test_webapp_upload.py` — new file: upload endpoint fast-tier tests
- [ ] No new pip/uv dependency install needed — `python-multipart` already present via `fastapi[standard]` (confirmed installed, v0.0.32)

## Sources

### Primary (HIGH confidence)
- FastAPI official docs — Request Files (`https://fastapi.tiangolo.com/tutorial/request-files/`) — `list[UploadFile]` + `Form()` multipart pattern, fetched live Sep 2026
- This repo's own source, read directly for this research: `webapp/backend/{main,auth,deps,schemas,streaming}.py`, `qa/session.py`, `agent/session.py`, `agent/memory.py`, `agent/tools.py`, `ingest/pipeline.py`, `ingest/loaders.py`, `ingest/store.py`, `tests/conftest.py`, `tests/test_webapp_backend.py`, `tests/test_agent_memory.py`, `.planning/REQUIREMENTS.md`, `.planning/STATE.md`, `.planning/phases/07-*/07-RESEARCH.md`, `.planning/phases/07-*/07-VERIFICATION.md`
- Installed package versions verified directly: `python -c "import fastapi; print(fastapi.__version__)"` → 0.141.1; `python -c "import multipart; print(multipart.__version__)"` → 0.0.32; `inspect.signature(scanpy.read_10x_mtx)` and its docstring, confirming `prefix`/`compressed` params and directory-based reading

### Secondary (MEDIUM confidence)
- None retained as load-bearing beyond the primary sources above — this phase's research relied almost entirely on direct code inspection (this repo) and one official-docs fetch, not general web search, since the questions were "what does *this* codebase's existing API look like" rather than "what does the ecosystem generally do."

### Tertiary (LOW confidence)
- None.

## Metadata

**Confidence breakdown:**
- Standard stack (no new dependencies, `python-multipart` already present): HIGH — verified by direct import check against the installed `.venv`, not assumed
- Architecture (session_id plumbing fix, `sessions` table extension, `.mtx` 3-file upload staging): MEDIUM — the FastAPI multipart mechanics are HIGH confidence (official docs), but the specific `SessionMemory` schema extension and the "record upload into SessionMemory for conversational recall" design are original synthesis over this repo's own code with no existing precedent to copy against; the planner should treat the `sessions` table shape and the touch()-on-every-run_session() call as the design to implement, not as an already-verified fact
- Pitfalls (session_id drop, `.mtx` 3-file reality, store_root split-brain): HIGH for the session_id drop and `.mtx`-is-3-files claims (both directly verified by reading this repo's own source/fixtures, not inferred); MEDIUM-HIGH for the store_root split-brain risk (verified `STORE_ROOT`'s import-time-constant behavior in `agent/tools.py`, but the exact failure mode depends on how the planner wires the upload endpoint)

**Research date:** 2026-09-12
**Valid until:** ~30 days for the FastAPI/scanpy version specifics; the architectural findings (session_id gap, `.mtx` file-count reality, `SessionMemory` schema gap) are facts about this repo's current code, not time-sensitive, and remain valid until the underlying code changes
