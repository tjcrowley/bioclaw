# Architecture Research

**Domain:** Agent-orchestrated bioinformatics (BioClaw v1.2 feature integration)
**Researched:** 2026-09-16
**Confidence:** HIGH — all integration points are grounded in direct codebase inspection (September 2026 state), not training-data inference.

---

## v1.2 Integration Analysis

This document answers six specific architectural questions for the v1.2 milestone features. It replaces the earlier (2026-09-03) speculative architecture with concrete analysis of what the code actually looks like today and where each new feature slots in.

---

## System Overview (current state, pre-v1.2)

```
┌──────────────────────────────────────────────────────────────┐
│                     FRONTEND (vanilla JS)                     │
│  index.html + main.js + chat.js + sessions.js + api.js +     │
│  citations.js + style.css                                     │
│  Served by FastAPI StaticFiles at /app                        │
└─────────────────────────────┬────────────────────────────────┘
                               │ HTTP / WebSocket
┌──────────────────────────────▼────────────────────────────────┐
│                     WEBAPP BACKEND (FastAPI)                   │
│  main.py: POST /api/ask, GET /api/sessions,                   │
│  GET /api/sessions/{id}, POST /api/upload, WS /ws/{id},       │
│  POST /api/login                                               │
│  deps.py: SessionMemory singleton, ask_question injectable    │
│  streaming.py: in-memory asyncio.Queue registry (single proc) │
│  auth.py: shared-password cookie gate                         │
└──────────────────────────────┬────────────────────────────────┘
                               │ function call (same process)
┌──────────────────────────────▼────────────────────────────────┐
│                    QA LAYER (qa/session.py)                    │
│  ask_question() → run_session() + verify_answer_citations()   │
└──────────────────────────────┬────────────────────────────────┘
                               │
┌──────────────────────────────▼────────────────────────────────┐
│                 AGENT SESSION (agent/session.py)               │
│  ClaudeSDKClient agentic loop                                 │
│  PostToolUse hooks: log_tool_call + record_dataset_reference  │
│  +extra_hooks (streaming, future hooks)                       │
└──────────────────────────────┬────────────────────────────────┘
                               │ MCP tool calls (in-process)
┌──────────────────────────────▼────────────────────────────────┐
│              TOOL SURFACE (agent/tools.py)                    │
│  @tool ingest_10x_tool                                        │
│  @tool analyze_dataset_tool                                   │
│  @tool annotate_cell_type_tool                                │
│  @tool predict_perturbation_tool                              │
└──────────────────────────────┬────────────────────────────────┘
                               │ function calls
┌──────────────────────────────▼────────────────────────────────┐
│                PIPELINE LAYER                                  │
│  ingest/pipeline.py::ingest_10x()                             │
│  analysis/pipeline.py::analyze()                              │
│  annotation/pipeline.py::annotate()                           │
│  perturbation/pipeline.py::predict()                          │
└──────────────────────────────┬────────────────────────────────┘
                               │
┌──────────────────────────────▼────────────────────────────────┐
│                DATA / STATE LAYER                              │
│  ingest/store.py::DatasetStore (SQLite registry + .h5ad files)│
│  agent/memory.py::SessionMemory (SQLite, dataset refs only)   │
│  tool_calls.jsonl (citation audit log)                        │
└──────────────────────────────┬────────────────────────────────┘
                               │ subprocess (isolation boundary)
┌──────────────────────────────▼────────────────────────────────┐
│          BIO FM WORKER (bio_fm_worker/, Python 3.9.6)         │
│  bio_fm_worker/.venv: scgpt, torch==2.3.0, torchtext==0.18.0 │
│  run_scgpt_embed.py: reads .h5ad, runs scGPT, prints JSON     │
│  annotation/fm_client.py: subprocess shim (main venv side)    │
└───────────────────────────────────────────────────────────────┘
```

---

## Q1: cellxgene-census Query Tool

### Where it slots in

The census query tool is a new `@tool`-decorated handler in `agent/tools.py`, exactly parallel to `ingest_10x_tool`. It is **not** a separate ingest branch — it is an alternative *data acquisition path* that feeds the existing ingest pipeline.

The split:
- `query_census_tool` in `agent/tools.py`: calls a new `ingest/census.py::ingest_from_census()` function, receives a `dataset_id` back, records it in session memory via the existing `record_dataset_reference` PostToolUse hook (unchanged).
- `ingest/census.py` (new file): wraps `cellxgene_census.get_anndata()` to fetch a named slice by `organism`/`tissue`/`assay`/`obs_value_filter` + optional `n_cells` cap, then routes the resulting in-memory AnnData through the existing `ingest_10x()` pipeline (starting after the `loaders.load()` call, since the data is already in memory). Returns a `dataset_id`.

`cellxgene-census` is already in `pyproject.toml` (confirmed: `cellxgene-census>=1.18.0`). The tool needs no new top-level dependency. The existing `annotation/reference.py::build_reference_index()` already contains a working pattern for querying the census (`get_anndata`, `obs_value_filter`, S3 throttle config) that `ingest/census.py` can follow directly.

### Tool schema

```python
@tool(
    "query_census",
    "Fetch a public single-cell dataset from CELLxGENE Census by tissue, "
    "organism, and/or assay, ingest it with standard QC, and return a "
    "dataset_id the analysis tools can use. 'tissue' (e.g. 'blood', 'lung'), "
    "'organism' ('Homo sapiens' or 'Mus musculus'), and 'name' (the local "
    "dataset name) are required. Optionally pass 'assay', 'obs_value_filter' "
    "(additional CELLxGENE filter expression), and 'n_cells' (cap, default 5000).",
    {"name": str, "tissue": str},  # organism has a sensible default; others optional
)
```

### Data flow

```
Agent calls query_census(name, tissue, organism, assay?, n_cells?)
    ↓
ingest/census.py::ingest_from_census()
    cellxgene_census.open_soma() [existing pattern from annotation/reference.py]
    cellxgene_census.get_anndata(organism, obs_value_filter="tissue_general == ...",
                                  obs_column_names=[...])  → AnnData in memory
    contract.set_counts_layer(adata)   [same as ingest_10x]
    qc.run(adata)                      [same as ingest_10x]
    store.save(name, adata, ...)       [same as ingest_10x]
    returns dataset_id
    ↓
PostToolUse hook records dataset_id in SessionMemory  [unchanged]
Agent receives {"dataset_id": "name@1"} and can call analyze_dataset next
```

### Component map

| Component | Status | Change |
|-----------|--------|--------|
| `agent/tools.py` | MODIFIED | Add `query_census_tool` |
| `ingest/census.py` | NEW | Census fetch + pipeline wiring |
| `ingest/pipeline.py` | UNCHANGED | Existing `ingest_10x()` re-used for post-fetch steps |
| `annotation/reference.py` | UNCHANGED | Pattern donor only |
| `pyproject.toml` | UNCHANGED | `cellxgene-census` already present |

---

## Q2: Session Message Storage (History Replay)

### Schema change to SessionMemory

`agent/memory.py` currently has two tables: `session_memory` (dataset refs) and `sessions` (session index). A third table is needed:

```sql
CREATE TABLE IF NOT EXISTS messages (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL,
    role      TEXT NOT NULL,          -- 'user' | 'assistant'
    content   TEXT NOT NULL,          -- message text
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS messages_session_idx ON messages (session_id, id);
```

New methods on `SessionMemory`:
- `record_message(session_id, role, content)` — called from the agentic loop after each turn
- `get_messages(session_id) -> list[dict]` — returns `[{role, content, created_at}, ...]` ordered by id

### Where messages get written

`agent/session.py::run_session()` already runs a `for prompt in prompts:` loop. After each `client.query(...)` / `client.receive_response()` pair, append:
1. `session_memory.record_message(session_id, "user", prompt)` (before the query)
2. `session_memory.record_message(session_id, "assistant", final_text)` (after the response)

This is a pure addition — no existing hook or pipeline logic changes.

### API change to GET /api/sessions/{id}

`webapp/backend/main.py::get_session()` currently returns `SessionSummary` with only `session_id` and `recent_datasets`. The response schema needs `messages` added:

```python
# schemas.py
class MessageRecord(BaseModel):
    role: str
    content: str
    created_at: str

class SessionSummary(BaseModel):
    session_id: str
    created_at: str | None = None
    last_active_at: str | None = None
    recent_datasets: list[str] = []
    messages: list[MessageRecord] = []  # NEW
```

`get_session()` in `main.py` calls `session_memory.get_messages(session_id)` and populates the field. The endpoint path stays `GET /api/sessions/{session_id}` — no new route needed.

### Frontend change to sessions.js

`sessions.js::resumeSession()` currently calls `getSession(sessionId)` and renders a single "Resuming session — last used: ..." stub message via `appendMessage()`.

Change: iterate over `summary.messages` and call `appendMessage({role, content})` for each, in order, before the "Resuming…" stub. If `messages` is empty or absent (old sessions pre-v1.2), fall back to the existing stub behavior.

`chat.js::appendMessage()` already handles both `role: 'user'` and `role: 'assistant'` (confirmed from frontend structure — chat thread renders both roles). No change needed to `chat.js`.

`api.js::getSession()` requires no change — it already returns the full JSON body and `messages` will just be present in the response.

### Component map

| Component | Status | Change |
|-----------|--------|--------|
| `agent/memory.py` | MODIFIED | Add `messages` table, `record_message()`, `get_messages()` |
| `agent/session.py` | MODIFIED | Call `record_message()` around each turn in `run_session()` |
| `webapp/backend/schemas.py` | MODIFIED | Add `MessageRecord`, extend `SessionSummary.messages` |
| `webapp/backend/main.py` | MODIFIED | `get_session()` populates `messages` field |
| `webapp/frontend/sessions.js` | MODIFIED | `resumeSession()` renders historical messages |
| `webapp/frontend/api.js` | UNCHANGED | Already returns full JSON |
| `webapp/frontend/chat.js` | UNCHANGED | Already handles user/assistant roles |

---

## Q3: Geneformer Isolation

### Separate venv from scGPT — required

Geneformer requires Python >=3.10 (confirmed from `setup.py`). The existing `bio_fm_worker/.venv` is Python 3.9.6 (confirmed from `pyvenv.cfg`). These cannot share a venv.

The correct structure is a new `bio_fm_worker/geneformer_worker/` directory with its own `.venv` on Python 3.10+, parallel to the existing scGPT isolation:

```
bio_fm_worker/
├── .venv/                      # existing — Python 3.9.6, scGPT + torch==2.3.0
├── run_scgpt_embed.py           # existing — scGPT subprocess entry point
├── geneformer_worker/
│   ├── .venv/                   # NEW — Python 3.10+, Geneformer + torch (unpinned)
│   └── run_geneformer_perturb.py  # NEW — Geneformer subprocess entry point
├── checkpoints/
│   ├── scGPT_human/             # existing
│   └── geneformer/              # NEW — Geneformer checkpoint download
└── reference/
    └── reference.h5ad           # existing
```

### Subprocess shim pattern (identical to fm_client.py)

A new `perturbation/geneformer_client.py` mirrors `annotation/fm_client.py` exactly:
- `call_geneformer_perturb(query_h5ad_path, target_gene, worker_python, script_path, model_dir)` shells out to `run_geneformer_perturb.py`
- The worker script reads the `.h5ad`, runs Geneformer in-silico perturbation, prints JSON to stdout, exits 0 on success
- Same `ensure_worker_compatible_h5ad()` serialization fix applies (pandas 3.0 StringDtype)

### perturbation/pipeline.py change

`perturbation/pipeline.py::predict()` currently calls `fit_from_adata()` (linear additive model). v1.2 adds Geneformer as an optional second prediction alongside the linear model. The function signature should add a `use_geneformer: bool = False` flag. When true, it calls `geneformer_client.call_geneformer_perturb(...)` and appends a third `PerturbationCall(method="geneformer", ...)` to the summary. The existing linear + naive_baseline pair is always computed first; Geneformer is additive, not a replacement.

`perturbation/summary.py` will need a `geneformer_call: PerturbationCall | None = None` field on `PerturbationSummary`.

### torch version risk

Geneformer's `setup.py` lists `torch` without a version pin. This means `pip install geneformer` in the new `.venv` will pull the latest torch (currently 2.8.x), which is fine for a Python 3.10+ environment. There is no torchtext dependency in Geneformer (unlike scGPT), so the ABI mismatch that required `torch==2.3.0` in the scGPT venv does not apply here. No pre-emptive pin needed — but if a new conflict surfaces during installation it should be captured in `geneformer_worker/README.md` using the same pattern as the existing `bio_fm_worker/README.md`.

### Component map

| Component | Status | Change |
|-----------|--------|--------|
| `bio_fm_worker/geneformer_worker/.venv` | NEW | Python 3.10+, Geneformer installed |
| `bio_fm_worker/geneformer_worker/run_geneformer_perturb.py` | NEW | Subprocess entry point |
| `bio_fm_worker/checkpoints/geneformer/` | NEW | Model weights |
| `perturbation/geneformer_client.py` | NEW | Subprocess shim (mirrors fm_client.py) |
| `perturbation/pipeline.py` | MODIFIED | Add Geneformer call path (opt-in flag) |
| `perturbation/summary.py` | MODIFIED | Add `geneformer_call` field |
| `agent/tools.py::predict_perturbation_tool` | MODIFIED | Pass `use_geneformer` arg |
| `bio_fm_worker/.venv` (scGPT) | UNCHANGED | Python 3.9.6 isolation preserved |

---

## Q4: Docker Compose Architecture

### Single-process constraint and its impact on Docker design

`webapp/backend/streaming.py` uses an in-process `asyncio.Queue` registry (`_QUEUES: dict[str, asyncio.Queue]`). This is documented as a "Single Uvicorn worker assumption" — the queue is local to the process. Multi-worker Uvicorn (e.g., `--workers 4`) would break streaming because a WebSocket request to `/ws/{id}` could land on a different worker than the `/api/ask` that created the queue.

This constraint means: **the backend service must run as a single Uvicorn worker** in Docker. `CMD ["uvicorn", "webapp.backend.main:app", "--host", "0.0.0.0", "--port", "8000"]` — no `--workers N` flag.

### Service layout

Two services: `backend` + `gpu-worker` (optional/profile-gated). No separate nginx — the frontend is already served by FastAPI's `StaticFiles` mount at `/app`.

```yaml
# docker-compose.yml

services:
  backend:
    build:
      context: .
      dockerfile: Dockerfile
    ports:
      - "8000:8000"
    volumes:
      - ./data:/app/data               # dataset store (persisted)
      - ./agent/memory.sqlite:/app/agent/memory.sqlite  # session memory
      - ./tool_calls.jsonl:/app/tool_calls.jsonl        # audit log
    environment:
      - BIOCLAW_PASSWORD=${BIOCLAW_PASSWORD}
      - ANTHROPIC_API_KEY=${ANTHROPIC_API_KEY}
      - BIOCLAW_STORE_ROOT=/app/data
    command: ["uvicorn", "webapp.backend.main:app",
              "--host", "0.0.0.0", "--port", "8000"]

  gpu-worker:
    build:
      context: bio_fm_worker
      dockerfile: Dockerfile.gpu-worker
    volumes:
      - ./bio_fm_worker/checkpoints:/checkpoints:ro
      - ./bio_fm_worker/reference:/reference:ro
    profiles:
      - gpu                            # opt-in: docker compose --profile gpu up
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              count: 1
              capabilities: [gpu]
```

### Dockerfile strategy: multi-stage, NOT multi-service for the main app

The main backend Dockerfile uses two stages to keep the final image lean:

```
Stage 1 (builder): python:3.12-slim
  - Install uv
  - Copy pyproject.toml, uv.lock
  - uv sync --frozen (installs all deps incl. scanpy, anndata, cellxgene-census)

Stage 2 (runtime): python:3.12-slim
  - Copy .venv from builder
  - Copy source (agent/, analysis/, annotation/, ingest/, perturbation/, qa/, webapp/)
  - Expose 8000
  - CMD uvicorn (single worker)
```

The bio_fm_worker/scGPT isolation is handled **at Docker build time** within the `gpu-worker` service's own `Dockerfile.gpu-worker`, using Python 3.9 as the base. The scGPT venv creation steps from `bio_fm_worker/README.md` (pip install scgpt, pin torch==2.3.0) become RUN commands in that Dockerfile. This removes the manual `bio_fm_worker/.venv` setup step from the user's `docker compose up` experience.

The `backend` service's Docker container does **not** include `bio_fm_worker/` at all. The `annotation/fm_client.py` subprocess shim currently hardcodes paths like `bio_fm_worker/.venv/bin/python` — these paths need to be overridable via environment variables in Docker (`SCGPT_WORKER_PYTHON`, `GENEFORMER_WORKER_PYTHON`) so the backend can call into the `gpu-worker` container. This is the main architectural evolution Docker introduces: the subprocess shim becomes an optional network/inter-container call rather than a local filesystem call.

**Inter-container subprocess path**: The cleanest v1.2 approach is to expose the `gpu-worker` as a minimal HTTP service (FastAPI or Flask, one endpoint per model) rather than a raw subprocess target. The backend then calls `http://gpu-worker:8080/annotate` instead of shelling out. The `fm_client.py` shim's `subprocess.run(...)` is replaced by `httpx.post(...)`. This also fixes the single-process constraint issue — HTTP calls work fine across workers if the queue constraint is ever lifted later.

If the HTTP refactor is deferred for v1.2, the simpler fallback is shared bind-mounted filesystems (input .h5ad written to a shared volume, worker reads it, writes result JSON, backend reads result JSON). This is lower complexity but couples the two containers via filesystem state.

### Component map

| Component | Status | Change |
|-----------|--------|--------|
| `Dockerfile` | NEW | Multi-stage, main backend |
| `docker-compose.yml` | NEW | backend + gpu-worker (profiled) |
| `bio_fm_worker/Dockerfile.gpu-worker` | NEW | scGPT + Geneformer in Python 3.9/3.10 |
| `.env.example` | NEW | `BIOCLAW_PASSWORD`, `ANTHROPIC_API_KEY` |
| `annotation/fm_client.py` | MODIFIED | Worker path overridable via env var (or HTTP refactor) |
| `perturbation/geneformer_client.py` | MODIFIED | Same env-var override |
| `webapp/backend/streaming.py` | UNCHANGED | Single-worker constraint documented, honored |

---

## Q5: Result Export

### Two distinct export surfaces

**Surface A: Direct API endpoint — `GET /api/export/{dataset_id}`**

Returns a CSV of the current dataset's obs metadata (cluster labels, cell-type annotations, perturbation results). This is the download button a researcher clicks in the UI. It is a pure FastAPI route — no agent involvement.

The endpoint:
1. Loads the named dataset from `DatasetStore`
2. Extracts `adata.obs` as a pandas DataFrame
3. Returns `StreamingResponse` with `media_type="text/csv"` and `Content-Disposition: attachment`

Schema:
```python
@app.get("/api/export/{dataset_name}", dependencies=[Depends(require_password)])
async def export_dataset(dataset_name: str, version: int | None = None): ...
```

`api.js` gets a new `exportDataset(datasetName, version)` function that opens the URL in a new tab (triggers browser download).

**Surface B: Agent tool — `export_analysis_script`**

An agent-callable tool that generates a reproducible Python script (scanpy code) representing the analysis steps performed in the conversation. The tool reads the session's `recent_datasets` from `SessionMemory` and the `tool_calls.jsonl` log entries for the session, then generates a script that reproduces the ingest → QC → cluster → annotate sequence.

This is a new `@tool` in `agent/tools.py`:
```python
@tool(
    "export_analysis_script",
    "Generate a reproducible Python/scanpy script that reproduces the analysis "
    "performed in this session. Returns the script as text the user can save and run.",
    {"session_id": str},
)
```

The generated script is returned as the tool's text content — the agent pastes it into its answer. No file is written server-side by this tool.

### Why two surfaces, not one

The CSV download is a synchronous, user-initiated browser action that should not require an agent turn (it's just data access, not a reasoning task). The script export requires reasoning (ordering the steps correctly, translating tool calls to scanpy API calls) and benefits from the agent's system prompt context. Combining them into one endpoint would either force every CSV download through an LLM call or strip the script generation of its reasoning layer.

### Component map

| Component | Status | Change |
|-----------|--------|--------|
| `webapp/backend/main.py` | MODIFIED | Add `GET /api/export/{dataset_name}` |
| `webapp/backend/schemas.py` | UNCHANGED | No new schema needed (CSV response) |
| `agent/tools.py` | MODIFIED | Add `export_analysis_script` tool |
| `webapp/frontend/api.js` | MODIFIED | Add `exportDataset()` function |
| `webapp/frontend/chat.js` or `main.js` | MODIFIED | Add export button/trigger in UI |

---

## Q6: Build Order

Dependencies between the seven v1.2 features determine this ordering. Features with no external dependencies on other v1.2 features can be built in parallel; those with dependencies must wait.

### Dependency graph

```
.h5ad upload fix (independent — ingest/loaders.py already handles .h5ad)
    ↓ (blocks nothing — already partially done per uploads.py)

scGPT ABI fix (independent — bio_fm_worker/.venv only)
    ↓
    └─→ Geneformer isolation (depends on scGPT fix being validated first,
            and requires a working bio_fm_worker pattern to replicate)

cellxgene-census query tool (independent — cellxgene-census already in pyproject.toml,
    reference.py has working query pattern)

Session history replay (independent of all FM/ingest features —
    only touches memory.py, session.py, schemas.py, sessions.js)

Result export: CSV endpoint (independent — DatasetStore already loads datasets)
Result export: script tool (depends on session history replay — needs message log
    from memory.py to generate the script accurately)

Docker compose (depends on ALL of the above being stable — it packages the final state)
```

### Recommended build order

**Phase 1 — No dependencies, highest value unlocked**

1. `.h5ad` upload fix
   - `uploads.py` already accepts `.h5ad` single-file uploads (confirmed: `_SINGLE_FILE_SUFFIXES = (".h5", ".h5ad")`)
   - `ingest/loaders.py::load()` already handles `.h5ad` via `sc.read_h5ad()`
   - The fix may be a test-and-verify, not a code change — check if `/api/upload` is fully wired for `.h5ad` end-to-end, including the frontend upload UI accepting `.h5ad` MIME/extension
   - Confidence: this may already be working; verify before treating it as a build task

2. Session history replay
   - Pure backend + frontend change, no FM or ingest dependency
   - Unblocks the script export tool (needs message log)
   - Schema migration is additive (new table + new field), safe to land early

3. Result export: CSV endpoint
   - Independent FastAPI route + DatasetStore read
   - No FM, no message history needed
   - Can be built and shipped before session replay is done

**Phase 2 — Unlocked after Phase 1**

4. Result export: analysis script tool
   - Depends on session history replay (Phase 1 item 2) having landed so `get_messages()` exists
   - Builds on the `@tool` pattern already established in `agent/tools.py`

5. cellxgene-census query tool
   - No dependency on Phase 1 items, but sequenced here because it requires a test against the live Census API (network-dependent), making it slower to iterate on than Phase 1 items
   - `annotation/reference.py` is the pattern template; adapt for ingest rather than reference building

**Phase 3 — FM isolation work**

6. scGPT ABI fix (real inference)
   - Isolated to `bio_fm_worker/.venv` and `run_scgpt_embed.py`
   - The README documents the fix was partially done (torch==2.3.0 applied, `import scgpt` works) but real inference against a checkpoint was not yet validated end-to-end
   - Sequenced before Geneformer because it validates the subprocess pattern before introducing a second isolated venv

7. Geneformer isolation + perturbation tool
   - Requires scGPT pattern to be stable (item 6)
   - Requires `bio_fm_worker/geneformer_worker/` setup, new subprocess shim, `perturbation/pipeline.py` extension
   - Sequenced last in Phase 3 because it's the highest-risk item (new venv, new model API, new subprocess protocol)

**Phase 4 — Packaging**

8. Docker compose
   - Depends on all seven features being stable
   - The inter-container communication decision for the FM worker (shared volume vs HTTP) is the main architectural choice to resolve here
   - Recommendation: HTTP service in the gpu-worker container — cleaner boundary, avoids shared-filesystem coupling, makes the worker independently restartable
   - Build the main backend Dockerfile first (simpler, no GPU toolchain), validate `docker compose up` works without `--profile gpu`, then add the gpu-worker Dockerfile

### Parallelizable pairs

Phase 1 items 1/2/3 are fully independent and can be worked in parallel if there are parallel development streams.

Phase 3 items 6 and 5 (cellxgene-census) are independent and can run in parallel.

Phase 3 item 7 (Geneformer) must wait for item 6 (scGPT) to be validated.

---

## Component Boundaries: New vs Modified vs Unchanged

```
NEW FILES
─────────────────────────────────────────────────────────────────
ingest/census.py                    # census query + ingest pipeline
perturbation/geneformer_client.py   # Geneformer subprocess shim
bio_fm_worker/geneformer_worker/
  .venv/                            # Python 3.10+, Geneformer
  run_geneformer_perturb.py         # Geneformer subprocess entry point
bio_fm_worker/checkpoints/geneformer/ # model weights
Dockerfile                          # main backend multi-stage
docker-compose.yml
bio_fm_worker/Dockerfile.gpu-worker
.env.example

MODIFIED FILES (additive changes only — no existing logic removed)
─────────────────────────────────────────────────────────────────
agent/tools.py                      # +query_census_tool, +export_analysis_script_tool
                                    #  predict_perturbation_tool: +use_geneformer arg
agent/memory.py                     # +messages table, +record_message(), +get_messages()
agent/session.py                    # +record_message() calls around each turn
perturbation/pipeline.py            # +Geneformer call path (opt-in)
perturbation/summary.py             # +geneformer_call field
annotation/fm_client.py             # worker path → env-var overridable
webapp/backend/main.py              # +GET /api/export/{dataset_name}
webapp/backend/schemas.py           # +MessageRecord, +SessionSummary.messages
webapp/frontend/api.js              # +exportDataset()
webapp/frontend/sessions.js         # resumeSession() renders history
webapp/frontend/main.js or chat.js  # +export trigger in UI

UNCHANGED (confirmed by codebase inspection)
─────────────────────────────────────────────────────────────────
ingest/loaders.py                   # .h5ad already handled
ingest/pipeline.py                  # ingest_10x() reused by census tool
ingest/store.py                     # no change
webapp/backend/uploads.py           # .h5ad already accepted
webapp/backend/streaming.py         # single-process constraint honored
webapp/backend/auth.py
webapp/backend/deps.py
webapp/frontend/api.js (getSession) # already returns full JSON body
webapp/frontend/chat.js             # already handles user/assistant roles
bio_fm_worker/.venv (scGPT)         # Python 3.9.6 isolation preserved
bio_fm_worker/run_scgpt_embed.py    # scGPT shim unchanged
annotation/pipeline.py
analysis/pipeline.py
qa/session.py
```

---

## Data Flow Changes for v1.2

### New flow: Census query → dataset

```
Agent: query_census(name="pbmc_lung", tissue="lung", n_cells=5000)
    ↓
ingest/census.py::ingest_from_census()
    open_soma() → get_anndata(obs_value_filter="tissue_general == 'lung'", ...)
    → AnnData in memory (skips loaders.load(), data already in memory)
    contract.set_counts_layer() → qc.run() → store.save()
    returns "pbmc_lung@1"
    ↓
Agent receives dataset_id, proceeds to analyze_dataset
```

### New flow: session history → frontend replay

```
GET /api/sessions/{id}
    → session_memory.get_messages(session_id)  [new method]
    → SessionSummary(messages=[{role, content, created_at}, ...])
Frontend sessions.js::resumeSession()
    → iterates summary.messages
    → appendMessage({role, content}) for each  [existing chat.js function]
    → user sees full prior conversation in chat thread
```

### New flow: CSV export

```
Frontend: user clicks "Export CSV" for dataset_name
    → api.js::exportDataset(dataset_name) → GET /api/export/{dataset_name}
    → FastAPI loads adata from DatasetStore
    → returns StreamingResponse(adata.obs.to_csv(), media_type="text/csv")
    → browser downloads file
```

### Existing flows: unchanged

All existing `/api/ask`, `/api/upload`, `/ws/{id}`, `/api/sessions`, and `/api/sessions/{id}` flows are unaffected by v1.2 changes. The session memory additive schema migration (new `messages` table) is backward-compatible — old sessions without messages get `messages: []` in the API response.

---

## Pitfalls Specific to This Integration

### Single-process constraint in Docker

If the backend container is accidentally started with `--workers 2` (e.g., via a Gunicorn wrapper), the `asyncio.Queue` streaming registry breaks silently: the WebSocket for `/ws/{id}` may land on a different worker than the `/api/ask` that registered the queue. The Dockerfile `CMD` must use bare `uvicorn` (not `gunicorn`), and the compose file must not set `WORKERS` env vars that a startup script might pick up. Document this constraint in a `# SINGLE WORKER REQUIRED` comment in the Dockerfile.

### anndata wire format gap in Geneformer worker

The same pandas 3.0 StringDtype → anndata 0.10.x incompatibility documented in `annotation/fm_client.py` applies to any `.h5ad` written by the main venv (Python 3.12, anndata 0.13) and read by `geneformer_worker/.venv`. The `ensure_worker_compatible_h5ad()` call must precede every `.write_h5ad()` in the new Geneformer shim, exactly as it does in `annotation/pipeline.py`.

### Census query cell count and memory

`cellxgene_census.get_anndata()` with a tissue filter and no `n_cells` cap can return millions of cells. The census query tool must enforce a hard cap (5,000 cells by default, user-overridable up to a documented limit) and communicate this constraint clearly in the tool description. The existing `annotation/reference.py::_fetch()` uses a contiguous joinid window (not a full scatter) for the same reason.

### Message transcript storage size

`agent/session.py::run_session()` prepends `_recall_preamble()` to every prompt. If message transcripts are stored verbatim and then also replayed on every turn, the preamble grows with session length. The `record_message()` implementation should store only the original user prompt and final assistant response, not the preamble-extended string that was actually sent to the SDK.

---

## Sources

All findings in this document are based on direct codebase inspection (September 2026 state) of:
- `/Users/darren/.openclaw/workspace/bioclaw/agent/` (tools.py, memory.py, session.py)
- `/Users/darren/.openclaw/workspace/bioclaw/webapp/backend/` (main.py, streaming.py, uploads.py, schemas.py, deps.py)
- `/Users/darren/.openclaw/workspace/bioclaw/webapp/frontend/` (sessions.js, api.js, chat.js)
- `/Users/darren/.openclaw/workspace/bioclaw/ingest/` (loaders.py, pipeline.py, store.py)
- `/Users/darren/.openclaw/workspace/bioclaw/annotation/` (fm_client.py, pipeline.py, reference.py)
- `/Users/darren/.openclaw/workspace/bioclaw/perturbation/` (pipeline.py, model.py)
- `/Users/darren/.openclaw/workspace/bioclaw/bio_fm_worker/` (run_scgpt_embed.py, README.md, .venv/pyvenv.cfg)
- `/Users/darren/.openclaw/workspace/bioclaw/pyproject.toml`
- Geneformer `setup.py` via HuggingFace (python_requires=">=3.10", no torch version pin, no torchtext dep) — MEDIUM confidence
- cellxgene-census `get_anndata()` API via official docs — HIGH confidence

---
*Architecture research for: BioClaw v1.2 feature integration*
*Researched: 2026-09-16*
