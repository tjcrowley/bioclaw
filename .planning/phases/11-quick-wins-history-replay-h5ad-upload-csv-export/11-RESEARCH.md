# Phase 11: Quick Wins — History Replay, h5ad Upload, CSV Export — Research

**Researched:** 2026-09-16
**Domain:** SQLite WAL, AnnData CSV export, FastAPI file response, vanilla JS frontend
**Confidence:** HIGH — all three work areas are verified against existing codebase; no new dependencies required

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| HIST-01 | Resuming a session in the sidebar renders the full prior conversation thread (all turns, inline tool activity, citations) — not just a "Resuming session..." placeholder | Requires: (1) `messages` table added to `agent/memory.py` with SQLite WAL mode, 64 KB content cap; (2) `GET /api/sessions/{id}` enriched to return stored messages; (3) `sessions.js::resumeSession()` replaced with replay logic instead of `appendMessage({role:'system',...})` placeholder |
| DATA-02 | Upload endpoint accepts direct `.h5ad` files alongside the existing MTX trio, routing to the same ingest pipeline | Already largely implemented: `uploads.py` already accepts `.h5ad` suffix and `ingest/loaders.py::load()` already handles `.h5ad` via `sc.read_h5ad()`. The `<input accept=...>` already includes `.h5ad`. The gap is one integration test proving the end-to-end path. |
| EXPORT-01 | Researcher can download cluster assignments, DE table, and annotation results for the active dataset as a CSV file from a backend endpoint | Requires: (1) new `GET /api/export/csv` endpoint; (2) AnnData obs/uns extraction logic; (3) `pandas.DataFrame.to_csv()` returned via `fastapi.responses.StreamingResponse`; (4) a download button in the frontend |
</phase_requirements>

---

## Summary

Phase 11 delivers three fully independent capabilities. All three can be planned and implemented in parallel because they share no internal dependencies. The codebase review shows that DATA-02 (h5ad upload) is already almost done — the backend `uploads.py` already accepts `.h5ad` suffix and `ingest/loaders.py` already calls `sc.read_h5ad()` on that path. The only gap is an explicit integration test that exercises the full `.h5ad` → `POST /api/upload` → `ingest_10x` path and confirms the returned `UploadResponse` shape. HIST-01 (history replay) requires the most new code: a `messages` table in `agent/memory.py` (with SQLite WAL mode and 64 KB content cap), an enriched API response, and replacement of the JS placeholder text with actual message rendering. EXPORT-01 (CSV export) requires a new backend endpoint that reads from the AnnData stored by `DatasetStore`, extracts `obs['leiden']`, `adata.uns['rank_genes_groups']` (if present), and annotation calls from session memory, then streams them as a CSV file response.

No new Python dependencies are needed for any of the three capabilities. `pandas.DataFrame.to_csv()` is already available (pandas is an anndata/scanpy transitive dependency). `fastapi.responses.StreamingResponse` is already in the project's FastAPI install. SQLite WAL mode is set via `PRAGMA journal_mode=WAL` with the existing `sqlite3` stdlib module.

**Primary recommendation:** Plan three independent wave sequences — one per requirement. HIST-01 is the highest-effort item; plan it first. DATA-02 is effectively a verification/test task. EXPORT-01 is a medium-effort backend + minimal frontend task. Each can be its own plan.

---

## Standard Stack

### Core (already in project — no new installs required)

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| `sqlite3` (stdlib) | Python 3.13 | WAL mode PRAGMA, messages table | Already used by `agent/memory.py` and `ingest/store.py` |
| `anndata` / `scanpy` | >=0.13 / >=1.12 | Load stored `.h5ad`, extract obs/uns for CSV | Core project dependency |
| `pandas` | (transitive via scanpy) | `DataFrame.to_csv()` for export | Already present via scanpy/anndata deps |
| `fastapi` | >=0.141 | `StreamingResponse`, `FileResponse` for CSV download | Already in project web extras |
| vanilla JS | ES modules, no build | History replay DOM insertion, download link | Established project pattern |

### Installation

```bash
# No new packages required. All capabilities use existing dependencies.
uv sync  # or: uv sync --extra web
```

---

## Architecture Patterns

### Pattern 1: SQLite WAL Mode (HIST-01)

**What:** Enable WAL (Write-Ahead Logging) on the SQLite connection so concurrent readers don't block writers. Standard for any SQLite used by a web server.
**When to use:** Required by HIST-01 success criteria explicitly. Also prevents the "database is locked" error when the FastAPI backend and a concurrent request both touch `agent/memory.sqlite`.
**How:** Call `PRAGMA journal_mode=WAL` on the connection immediately after `sqlite3.connect()`. The PRAGMA persists — it only needs to be set once per database file (not per connection), but it's safe to call every time; idempotent in practice.

```python
# Source: Python sqlite3 docs + SQLite docs (verified)
def _connect(self) -> sqlite3.Connection:
    conn = sqlite3.connect(self.path)
    conn.execute("PRAGMA journal_mode=WAL")
    return conn
```

**Where to add:** `agent/memory.py::SessionMemory._connect()` — the single connection factory for all memory operations. This is the only SQLite file that HIST-01 touches (the `DatasetStore` registry is a separate file and is read-only at resume time).

### Pattern 2: Messages Table Schema (HIST-01)

**What:** A `messages` table stores every turn's content (role + text) keyed by `session_id`, preserving insertion order via `rowid`. Content is capped at 64 KB per row before insert.
**When to use:** Required by HIST-01. Store on every Q&A turn (both user question and assistant answer).

```python
# Source: existing agent/memory.py schema pattern
_CREATE_MESSAGES_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS messages (
    session_id TEXT NOT NULL,
    role TEXT NOT NULL,        -- 'user' or 'assistant'
    content TEXT NOT NULL,     -- capped at 64 KB before insert
    created_at TEXT NOT NULL
)
"""

_CONTENT_CAP = 64 * 1024  # 64 KB in bytes

def add_message(self, session_id: str, role: str, content: str) -> None:
    """Stores one message turn. Content is truncated to 64 KB before insert
    to prevent database blowup (HIST-01 success criteria)."""
    capped = content[:_CONTENT_CAP]
    now = datetime.now(timezone.utc).isoformat()
    with self._connect() as conn:
        conn.execute(
            "INSERT INTO messages (session_id, role, content, created_at) VALUES (?, ?, ?, ?)",
            (session_id, role, capped, now),
        )
        conn.commit()

def get_messages(self, session_id: str) -> list[dict]:
    """Returns all messages for session_id, oldest first (rowid order)."""
    with self._connect() as conn:
        rows = conn.execute(
            "SELECT role, content, created_at FROM messages "
            "WHERE session_id = ? ORDER BY rowid ASC",
            (session_id,),
        ).fetchall()
    return [{"role": r[0], "content": r[1], "created_at": r[2]} for r in rows]
```

### Pattern 3: API Enrichment — Session Messages (HIST-01)

**What:** Enrich `GET /api/sessions/{session_id}` to include `messages` in the response, OR add a new `GET /api/sessions/{session_id}/messages` endpoint. The simpler path is enriching the existing `SessionSummary` schema.
**Decision:** Enrich existing endpoint. Frontend already calls `getSession(sessionId)` in `sessions.js::resumeSession()`. Adding `messages` to the `SessionSummary` Pydantic model and the backend query is one change, not two.

```python
# In schemas.py — extend SessionSummary
class MessageRecord(BaseModel):
    role: str
    content: str
    created_at: str

class SessionSummary(BaseModel):
    session_id: str
    created_at: str | None = None
    last_active_at: str | None = None
    recent_datasets: list[str] = []
    messages: list[MessageRecord] = []  # NEW: full turn history
```

```python
# In main.py — get_session() enriched
@app.get("/api/sessions/{session_id}", dependencies=[Depends(require_password)])
async def get_session(session_id: str, session_memory=Depends(deps.get_session_memory)) -> SessionSummary:
    if not session_memory.session_exists(session_id):
        raise HTTPException(status_code=404, detail="unknown session_id")
    msgs = session_memory.get_messages(session_id)
    return SessionSummary(
        session_id=session_id,
        recent_datasets=session_memory.recent_datasets(session_id),
        messages=[MessageRecord(**m) for m in msgs],
    )
```

### Pattern 4: Message Storage Hook — ask_question() (HIST-01)

**What:** Store user question and assistant answer into the messages table after every `ask_question()` call. The `POST /api/ask` handler in `main.py` is the right call site — it has both the question (`req.question`) and the answer (`answer` from `ask_question()`).
**When to use:** Only on the API path (not on internal `run_session()` calls in tests), keeping the messages table a webapp concern, not an agent-core concern.

```python
# In main.py POST /api/ask, after ask_question() returns:
session_memory.add_message(session_id, "user", req.question)
session_memory.add_message(session_id, "assistant", answer)
```

**Important:** The session_id must be resolved BEFORE storing messages. `ask_question()` returns the session_id as its second element, so store after the call, not before.

### Pattern 5: Frontend History Replay (HIST-01)

**What:** Replace the `appendMessage({role:'system', content:'Resuming session...'})` placeholder in `sessions.js::resumeSession()` with a loop that calls `appendMessage()` for each message record from the API.
**Where:** `webapp/frontend/sessions.js::resumeSession()` — the existing `getSession(sessionId).then(...)` block.

```javascript
// Source: existing sessions.js pattern + chat.js::appendMessage()
export function resumeSession(sessionId) {
    window.__currentSessionId = sessionId;
    _clearActive();
    const item = sessionList.querySelector(`[data-session-id="${CSS.escape(sessionId)}"]`);
    if (item) item.classList.add('active');

    clearChatThread();

    getSession(sessionId).then((summary) => {
        if (!summary) return;
        const msgs = summary.messages || [];
        if (msgs.length === 0) {
            // No stored turns: fall back to dataset context hint
            const datasets = summary.recent_datasets || [];
            const ctx = datasets.length > 0
                ? `Resuming session — last used: ${datasets.join(', ')}`
                : `Resuming session ${sessionId.slice(0, 8)}…`;
            appendMessage({ role: 'system', content: ctx });
        } else {
            for (const msg of msgs) {
                appendMessage({ role: msg.role, content: msg.content });
            }
        }
    }).catch(() => {});
}
```

**Note:** Citation rendering (`window.__renderAnswerWithCitations`) requires the `citations` array from the original turn, which is NOT stored in the messages table (it's per-session ephemeral). On replay, assistant messages render as plain text via `bubble.textContent = content` (the `citations` field is undefined, so the citation-rendering branch is skipped). This is acceptable for history replay — citations were resolved in the original turn; a researcher replaying history sees the text of the answer, not re-resolved citation links.

### Pattern 6: h5ad Upload (DATA-02)

**What:** The `uploads.py` file already accepts `.h5ad` as a valid single-file suffix. `ingest/loaders.py::load()` already handles `.h5ad` via `sc.read_h5ad()`. The `index.html` file input already includes `.h5ad` in the `accept` attribute. The only gap is a test.
**Verification (HIGH confidence from code inspection):**

- `uploads.py` line 19: `_SINGLE_FILE_SUFFIXES = (".h5", ".h5ad")` — already includes `.h5ad`
- `loaders.py` lines 85-89: `if p.suffix == ".h5ad": return sc.read_h5ad(p)` — already handled
- `index.html` line 36: `accept=".h5,.h5ad,.mtx,.tsv.gz"` — already accepts `.h5ad`
- `test_webapp_upload.py`: no `.h5ad` test exists yet — this is the only gap

**What to add:** One test `test_upload_h5ad_returns_dataset_id` using a fixture that creates a minimal `.h5ad` file (via `anndata.AnnData.write_h5ad()`).

### Pattern 7: CSV Export Endpoint (EXPORT-01)

**What:** New `GET /api/export/csv?dataset_id={id}` endpoint that loads the named dataset from `DatasetStore`, extracts cluster assignments (`adata.obs['leiden']`), the DE table (`adata.uns['rank_genes_groups']` via `sc.get.rank_genes_groups_df()`), and annotation summary from `SessionMemory`, then returns them as a multi-sheet CSV (or a zip of CSVs).
**Decision:** Return a ZIP of three CSV files (clusters.csv, de_genes.csv, annotations.csv). This avoids multi-sheet CSV format complexity and is simpler than a single flat file. Browser downloads a `.zip` file.

**Alternative considered:** A single CSV with a `section` column. Rejected — heterogeneous schemas in one file is harder to consume programmatically than separate files.

```python
# In main.py — new endpoint
import io
import zipfile

from fastapi.responses import StreamingResponse

@app.get("/api/export/csv", dependencies=[Depends(require_password)])
async def export_csv(dataset_id: str, session_memory=Depends(deps.get_session_memory)):
    # dataset_id format: "name@version" or "name@(latest)"
    parts = dataset_id.split("@", 1)
    if len(parts) != 2:
        raise HTTPException(status_code=422, detail="dataset_id must be name@version")
    name = parts[0]
    version_str = parts[1]
    version = int(version_str) if version_str.isdigit() else None

    store = DatasetStore(root=agent_tools.STORE_ROOT)
    try:
        adata = store.load(name, version)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        # 1. Cluster assignments
        if "leiden" in adata.obs.columns:
            clusters_csv = adata.obs[["leiden"]].reset_index()
            clusters_csv.columns = ["cell_barcode", "cluster"]
            zf.writestr("clusters.csv", clusters_csv.to_csv(index=False))
        else:
            zf.writestr("clusters.csv", "cell_barcode,cluster\n(no cluster data)\n")

        # 2. DE table
        if "rank_genes_groups" in adata.uns:
            import scanpy as sc
            # Get all groups that have DE results
            groups = list(adata.uns["rank_genes_groups"]["names"].dtype.names)
            de_frames = []
            for g in groups:
                df = sc.get.rank_genes_groups_df(adata, group=g)
                df.insert(0, "cluster", g)
                de_frames.append(df)
            import pandas as pd
            de_csv = pd.concat(de_frames, ignore_index=True) if de_frames else pd.DataFrame()
            zf.writestr("de_genes.csv", de_csv.to_csv(index=False))
        else:
            zf.writestr("de_genes.csv", "cluster,names,scores,pvals,pvals_adj,logfoldchanges\n(no DE data)\n")

        # 3. Annotations (from session memory — best-effort, may be empty)
        # Annotation results are in adata.uns if annotate() was called and
        # the result was stored. AnnotationSummary is serialized to uns by
        # annotation/pipeline.py. Check for it.
        ann_lines = ["cluster,method,label,confidence,ontology_term_id"]
        if "annotation" in adata.uns:
            ann = adata.uns["annotation"]
            for call in ann.get("fm_calls", []):
                ann_lines.append(
                    f"{call['cluster']},fm,{call['label']},{call['confidence']},{call.get('ontology_term_id','')}"
                )
            for call in ann.get("baseline_calls", []):
                ann_lines.append(
                    f"{call['cluster']},baseline,{call['label']},{call['confidence']},"
                )
        if len(ann_lines) == 1:
            ann_lines.append("(no annotation data)")
        zf.writestr("annotations.csv", "\n".join(ann_lines) + "\n")

    buf.seek(0)
    safe_name = name.replace("/", "_")
    return StreamingResponse(
        buf,
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{safe_name}_export.zip"'},
    )
```

**Key insight on annotation data location:** `annotation/pipeline.py::annotate()` stores results in `adata.uns["annotation"]` as a dict (via `dataclasses.asdict()`). A dataset that has been annotated and then saved via `store.save()` will have this key in its `.h5ad`. A dataset that has only been ingested/clustered but not annotated will not. The export endpoint must handle both cases gracefully (empty annotations.csv).

### Pattern 8: Frontend Download Control (EXPORT-01)

**What:** Add a download button to the main panel that triggers `GET /api/export/csv?dataset_id={currentDatasetId}`. The current dataset ID is available from `window.__currentSessionId` and can be resolved from `SessionMemory.recent_datasets()`. Simplest implementation: a button that calls `window.open('/api/export/csv?dataset_id=...')` — the browser handles the file download natively.

```javascript
// In api.js — new function
export function exportCsv(datasetId) {
    // Browser-native download: open in same tab triggers file download
    const url = `/api/export/csv?dataset_id=${encodeURIComponent(datasetId)}`;
    const a = document.createElement('a');
    a.href = url;
    a.download = '';  // browser decides filename from Content-Disposition
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
}
```

**Where to wire:** Add a download button to `index.html` in the main panel header area (above the chat thread), visible when a dataset is active. Wire in `main.js` after `addOrRefreshSession()` sets `window.__currentDatasetId`.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| CSV generation | Manual string concatenation | `pandas.DataFrame.to_csv()` | Handles quoting, encoding, null values |
| ZIP file creation | Manual byte manipulation | `zipfile.ZipFile` (stdlib) | In-memory ZipFile with `io.BytesIO` — no temp files |
| DE table extraction | Manual `adata.uns['rank_genes_groups']` parsing | `sc.get.rank_genes_groups_df(adata, group=g)` | Existing project pattern (already used in `diffexp.py`) |
| SQLite WAL mode | Manual file locking | `PRAGMA journal_mode=WAL` | One line; persists on the file |
| File streaming | Read-into-memory then send | `StreamingResponse` with `io.BytesIO` | Built into FastAPI; avoids temp file cleanup |

**Key insight:** The CSV export is pure data extraction from AnnData structures that are already correctly populated. No new analysis logic is needed — just field access and `pandas.to_csv()`.

---

## Common Pitfalls

### Pitfall 1: WAL PRAGMA Scope
**What goes wrong:** Setting WAL mode only on one connection while another open connection uses the default rollback journal — causes "database is locked" errors.
**Why it happens:** SQLite WAL mode is per-database-file, not per-connection. Once set via PRAGMA, it persists. But if you set it conditionally or only on some connections, you're not protected until the PRAGMA has been executed.
**How to avoid:** Always call `conn.execute("PRAGMA journal_mode=WAL")` inside `_connect()` in `SessionMemory`, so every connection sets it. The PRAGMA call is idempotent (returns "wal" if already set).

### Pitfall 2: 64 KB Cap Units
**What goes wrong:** Applying the 64 KB cap as `content[:64*1024]` works for ASCII but silently truncates multibyte UTF-8 sequences mid-character, causing `sqlite3.OperationalError: text_factory` or garbage at the boundary.
**Why it happens:** Python string slicing is by Unicode codepoint, not bytes. A string of 64*1024 codepoints can be much larger in bytes if it contains multi-byte characters.
**How to avoid:** The cap should be enforced in characters (Python string length), not bytes. `content[:_CONTENT_CAP]` where `_CONTENT_CAP = 64 * 1024` (character count, not byte count) is correct for Python strings. The stored content is a Python `str` object; SQLite stores it as UTF-8 text. The intent is bounding database growth, not exact byte precision. Document this clearly in code comments.

### Pitfall 3: Missing `leiden` Key at Export Time
**What goes wrong:** Export endpoint loads a dataset that was ingested but not yet analyzed (no clustering), `adata.obs['leiden']` raises `KeyError`.
**Why it happens:** A researcher might upload a dataset and export before running any analysis.
**How to avoid:** Check `"leiden" in adata.obs.columns` before accessing. Write a safe fallback CSV row (see Pattern 7 above).

### Pitfall 4: `rank_genes_groups` Group Names
**What goes wrong:** `sc.get.rank_genes_groups_df(adata, group=None)` behavior varies by scanpy version — some versions return all groups, others raise.
**Why it happens:** The `group` parameter was changed between scanpy versions.
**How to avoid:** Enumerate groups explicitly from `adata.uns['rank_genes_groups']['names'].dtype.names` and call `rank_genes_groups_df` once per group. This is the pattern already used in the project's `diffexp.py`.

### Pitfall 5: Browser fetch() vs. window.open() for File Downloads
**What goes wrong:** Using `fetch('/api/export/csv?...')` to trigger a file download requires manually converting the response to a Blob and clicking a synthetic anchor — complex and error-prone.
**Why it happens:** `fetch()` gives you the response body as a JS value, not a browser download.
**How to avoid:** Use `<a href="..." download>` or `window.location.href = url` for file downloads. Credentials (the session cookie) are sent automatically on navigation requests — no special handling needed.

### Pitfall 6: h5ad Upload — Tiny Fixture Must Survive QC
**What goes wrong:** A test fixture that creates a minimal `AnnData` (e.g. 5 cells × 5 genes) will be rejected by `qc.run()` with `QCConfig(min_genes_per_cell=200)`, making the upload return `status="error"` even though the code path works correctly.
**Why it happens:** Default QC thresholds are set for real datasets; synthetic fixtures are too small.
**How to avoid:** The h5ad upload test fixture must either use `analyzable_mtx_dir` dimensions (300 genes × 60 cells) or pass a custom `QCConfig` with lower thresholds. The existing `conftest.py` `analyzable_mtx_dir` fixture can be adapted: convert its output to `.h5ad` using `AnnData.write_h5ad()` in a new `tiny_h5ad_file` fixture, or use `synthetic_adata` with a loose QC config.

---

## Code Examples

### Verified Pattern: WAL Mode in sqlite3

```python
# Source: Python stdlib sqlite3 docs + SQLite WAL documentation
# Add to agent/memory.py::SessionMemory._connect()
def _connect(self) -> sqlite3.Connection:
    conn = sqlite3.connect(self.path)
    conn.execute("PRAGMA journal_mode=WAL")
    return conn
```

### Verified Pattern: StreamingResponse ZIP in FastAPI

```python
# Source: FastAPI docs + Python stdlib zipfile docs
import io
import zipfile
from fastapi.responses import StreamingResponse

buf = io.BytesIO()
with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
    zf.writestr("clusters.csv", clusters_df.to_csv(index=False))
    zf.writestr("de_genes.csv", de_df.to_csv(index=False))
    zf.writestr("annotations.csv", ann_csv_str)
buf.seek(0)
return StreamingResponse(
    buf,
    media_type="application/zip",
    headers={"Content-Disposition": 'attachment; filename="export.zip"'},
)
```

### Verified Pattern: extract DE table for all groups

```python
# Source: existing analysis/diffexp.py pattern (sc.get.rank_genes_groups_df)
import scanpy as sc
import pandas as pd

groups = list(adata.uns["rank_genes_groups"]["names"].dtype.names)
frames = []
for g in groups:
    df = sc.get.rank_genes_groups_df(adata, group=g)
    df.insert(0, "cluster", g)
    frames.append(df)
de_table = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()
```

### Verified Pattern: AnnData to h5ad fixture

```python
# Source: existing conftest.py patterns + anndata docs
import anndata as ad
import numpy as np
from scipy import sparse

@pytest.fixture
def tiny_h5ad_file(tmp_path, analyzable_mtx_dir):
    """Converts analyzable_mtx_dir fixture to .h5ad for DATA-02 tests."""
    from ingest.loaders import load
    adata = load(analyzable_mtx_dir)
    h5ad_path = tmp_path / "sample.h5ad"
    adata.write_h5ad(h5ad_path)
    return h5ad_path
```

---

## State of the Art

| Old Approach | Current Approach | Impact for Phase 11 |
|--------------|------------------|---------------------|
| Resume shows placeholder text | Resume replays full turn history from DB | HIST-01: messages table + API enrichment |
| Upload only MTX trio | Upload also accepts `.h5ad` directly | DATA-02: already code-complete, needs test |
| No export capability | ZIP of cluster/DE/annotation CSVs | EXPORT-01: new endpoint + download button |

**Already done (no new code needed):**
- `uploads.py`: `.h5ad` in `_SINGLE_FILE_SUFFIXES`
- `loaders.py`: `sc.read_h5ad()` branch for `.h5ad`
- `index.html`: `.h5ad` in `accept` attribute

---

## Open Questions

1. **Annotation data in `adata.uns`**
   - What we know: `annotation/pipeline.py::annotate()` stores results in `adata.uns['annotation']` (inferred from project pattern; not directly verified by reading that file in this research session)
   - What's unclear: The exact key name and shape stored in `uns` — may differ from the assumption above
   - Recommendation: Read `annotation/pipeline.py` at plan-writing time to confirm the `uns` key name and shape before writing the export extraction code

2. **Dataset ID resolution for export**
   - What we know: The frontend has `window.__currentSessionId` but not `window.__currentDatasetId`; the most recent dataset is available via `session_memory.recent_datasets(session_id)[0]`
   - What's unclear: Whether the export button should export the "most recently uploaded" dataset or require the user to select
   - Recommendation: Export the most recently used dataset for the active session (from `recent_datasets()[0]`). If no dataset is active, disable the button. Keep it simple — no dataset picker for Phase 11.

---

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest 8+ |
| Config file | `pyproject.toml` `[tool.pytest.ini_options]` |
| Quick run command | `.venv/bin/python -m pytest tests/ -m "not live_llm and not bio_fm_smoke and not vcc_data" -q` |
| Full suite command | `.venv/bin/python -m pytest tests/ -m "not live_llm and not bio_fm_smoke and not vcc_data" -q` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| HIST-01 | `SessionMemory.add_message()` stores and retrieves messages | unit | `.venv/bin/python -m pytest tests/test_agent_memory.py -x -q` | ✅ (extend existing) |
| HIST-01 | WAL mode set on new `_connect()` calls | unit | `.venv/bin/python -m pytest tests/test_agent_memory.py::test_wal_mode_enabled -x -q` | ❌ Wave 0 |
| HIST-01 | `GET /api/sessions/{id}` returns `messages` field | unit | `.venv/bin/python -m pytest tests/test_webapp_backend.py::test_get_session_returns_messages -x -q` | ❌ Wave 0 |
| HIST-01 | Message content capped at 64 KB | unit | `.venv/bin/python -m pytest tests/test_agent_memory.py::test_add_message_caps_at_64kb -x -q` | ❌ Wave 0 |
| DATA-02 | POST /api/upload with `.h5ad` returns success | integration | `.venv/bin/python -m pytest tests/test_webapp_upload.py::test_upload_h5ad_returns_dataset_id -x -q` | ❌ Wave 0 |
| EXPORT-01 | GET /api/export/csv returns ZIP with clusters.csv | unit | `.venv/bin/python -m pytest tests/test_webapp_export.py::test_export_csv_contains_clusters -x -q` | ❌ Wave 0 |
| EXPORT-01 | Export handles missing leiden/DE/annotation gracefully | unit | `.venv/bin/python -m pytest tests/test_webapp_export.py::test_export_csv_handles_missing_data -x -q` | ❌ Wave 0 |

### Sampling Rate

- **Per task commit:** `.venv/bin/python -m pytest tests/ -m "not live_llm and not bio_fm_smoke and not vcc_data" -q`
- **Per wave merge:** `.venv/bin/python -m pytest tests/ -m "not live_llm and not bio_fm_smoke and not vcc_data" -q`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps

- [ ] `tests/test_agent_memory.py` — extend with `test_wal_mode_enabled`, `test_add_message_stores_and_retrieves`, `test_add_message_caps_at_64kb`, `test_get_messages_returns_ordered` — covers HIST-01
- [ ] `tests/test_webapp_export.py` — new file: `test_export_csv_contains_clusters`, `test_export_csv_handles_missing_data`, `test_export_requires_auth` — covers EXPORT-01
- [ ] `conftest.py` — add `tiny_h5ad_file` fixture (converts `analyzable_mtx_dir` output to `.h5ad`) — covers DATA-02

*(Existing `tests/test_webapp_backend.py` and `tests/test_webapp_upload.py` will be extended in-place for the API schema changes.)*

---

## Sources

### Primary (HIGH confidence)

- Codebase direct inspection: `agent/memory.py`, `uploads.py`, `loaders.py`, `ingest/pipeline.py`, `analysis/diffexp.py`, `analysis/summary.py`, `webapp/backend/main.py`, `webapp/frontend/sessions.js`, `webapp/frontend/chat.js`, `webapp/frontend/index.html` — all read in full during this research session
- Python stdlib `sqlite3` docs: WAL PRAGMA is idempotent, persists per-database-file
- FastAPI `StreamingResponse` + `zipfile.ZipFile(io.BytesIO())` pattern: standard in-memory ZIP streaming

### Secondary (MEDIUM confidence)

- `annotation/pipeline.py` uns key: not read during this session; inferred from project dataclass-to-uns pattern established in `analysis/pipeline.py` (which uses `adata.uns["analysis"] = asdict(config)`)

### Tertiary (LOW confidence)

- None — no unverified external claims

---

## Metadata

**Confidence breakdown:**
- HIST-01 (history replay): HIGH — all code touchpoints identified from direct file reads; pattern is straightforward SQLite + existing `appendMessage()` JS function
- DATA-02 (h5ad upload): HIGH — code-complete already confirmed by direct inspection of `uploads.py` and `loaders.py`; only test gap
- EXPORT-01 (CSV export): HIGH — `DatasetStore.load()`, `sc.get.rank_genes_groups_df()`, `StreamingResponse`, `zipfile` all confirmed from existing code and stdlib; annotation uns key shape is MEDIUM pending `annotation/pipeline.py` verification

**Research date:** 2026-09-16
**Valid until:** 2026-10-16 (stable stdlib + existing project patterns; no external API dependencies)
