# Stack Research

**Domain:** Agentic single-cell biology — v1.2 new-feature additions
**Researched:** 2026-09-16
**Confidence:** HIGH (all key claims verified against official docs, PyPI, Docker Hub, or live SDK/venv introspection)

---

## Scope

This is a **v1.2 delta document**. It covers only what is new or changes in
v1.2. The validated v1.0/v1.1 stack (scanpy, anndata, fastapi, scrublet,
igraph, claude-agent-sdk, uv/pyproject.toml, SQLite SessionMemory) is
unchanged and not re-examined here unless v1.2 directly affects it.

---

## 1. cellxgene-census Query Tool

**No new packages.** `cellxgene-census>=1.18.0` is already declared in
`pyproject.toml`. Version 1.18.0 is the current stable release (June 2026 —
confirmed PyPI). `tiledbsoma>=1.15.3` is pulled as a transitive dependency
and needs no direct pin.

**Key API** (HIGH confidence — official docs):
```python
import cellxgene_census
with cellxgene_census.open_soma() as census:
    adata = cellxgene_census.get_anndata(
        census,
        organism="Homo sapiens",
        obs_value_filter="tissue == 'lung' and assay == '10x 3\\' v3'",
    )
```
`get_anndata()` returns a standard `AnnData` object directly compatible with
the existing scanpy pipeline. The only implementation work is a new MCP tool
that wraps this call and passes parameters from the agent.

---

## 2. Direct .h5ad Upload

**No new packages.** `scanpy.read_h5ad()` is already called in
`ingest/loaders.py` on the `.h5ad` branch. The loader already handles `.h5ad`
files correctly (`sc.read_h5ad(p)`, no `var_names_make_unique()` needed per
existing code comments). The only change required is in the upload endpoint:
accept `.h5ad` as a valid single-file upload alongside the MTX trio ZIP.

---

## 3. scGPT Annotation — bio_fm_worker Status

**The ABI mismatch is already fixed.** Confirmed via live `pip list` in
`bio_fm_worker/.venv`:

```
anndata       0.10.9
scgpt         0.2.4
torch         2.3.0    ← downgraded from 2.8.0 (the ABI fix)
torchtext     0.18.0   ← matched pair; was the mismatch root
scvi-tools    0.20.3
```

The fix applied: `bio_fm_worker/.venv/bin/pip install "torch==2.3.0"` after
`pip install scgpt`. `import scgpt` succeeds.

**Remaining work is code verification, not a stack change:** `run_scgpt_embed.py`
uses the `scgpt.tasks.embed_data()` API shape documented at LOW-MEDIUM
confidence. That API must be verified against the live installed API
(`help(scgpt.tasks)` in the worker venv) before the `bio_fm_smoke` test can
be trusted. This is a development task, not a package decision.

**If bio_fm_worker is ever rebuilt from scratch:**
```bash
python3 -m venv bio_fm_worker/.venv    # python3 must resolve to 3.9.x
bio_fm_worker/.venv/bin/pip install --upgrade pip
bio_fm_worker/.venv/bin/pip install scgpt
bio_fm_worker/.venv/bin/pip install "torch==2.3.0"   # ABI fix — run IMMEDIATELY
bio_fm_worker/.venv/bin/python -c "import scgpt; print('scgpt OK')"
```
The `torch==2.3.0` pin must be applied before any other code imports scgpt or
torch, since resolving deps later can silently re-upgrade torch.

---

## 4. Geneformer Perturbation Prediction — New Isolated Environment

### Package Source

**Geneformer has no PyPI package.** Installation is git-clone only from
Hugging Face Hub, then `pip install .` (HIGH confidence — confirmed via
official HF page and live setup.py fetch):

```bash
git lfs install
git clone https://huggingface.co/ctheodoris/Geneformer geneformer_worker/src
geneformer_worker/.venv/bin/pip install -e geneformer_worker/src
```

The cloned repo contains both the Python package (`geneformer/`) and the
model checkpoint files (managed by git-lfs). No separate checkpoint download
step is needed if git-lfs is working.

### Python Version Constraint

Geneformer `setup.py`: `python_requires=">=3.10"` (HIGH confidence — live
setup.py fetch). This is **incompatible with the existing bio_fm_worker venv
(Python 3.9.6)**. A second isolated venv is required.

**Python 3.10 is available on this machine:** `/opt/homebrew/bin/python3.10`.

| Environment | Python | Key Reason |
|-------------|--------|------------|
| `bio_fm_worker/.venv` (scGPT) | 3.9.6 | `scvi-tools<1.0` requires <=3.9; `anndata==0.10.9` ceiling |
| `geneformer_worker/.venv` (new) | **3.10.x** | Geneformer `python_requires=">=3.10"` |

### Geneformer Dependencies

From official `setup.py` (HIGH confidence):
`anndata`, `bitsandbytes`, `datasets`, `loompy`, `matplotlib`, `numpy`,
`optuna`, `optuna-integration`, `packaging`, `pandas`, `peft`, `pyarrow`,
`pytz`, `ray`, `scanpy`, `scikit-learn`, `scipy`, `seaborn`, `setuptools`,
`statsmodels`, `tdigest`, `tensorboard`, `torch`, `tqdm`, `transformers`

No version pins in `install_requires` — `pip install .` resolves current
compatible versions. The resolved torch will be a current 2.x release. No
`torchtext` dependency, so there is no ABI mismatch risk in this venv.

### Perturbation API

`geneformer.InSilicoPerturber` simulates gene knockdown/overexpression and
quantifies the shift in cell-state embeddings. `geneformer.InSilicoPerturberStats`
handles the statistical output analysis. The `emb_mode` parameter controls
whether CLS token, cell, and/or gene embeddings are output. (MEDIUM confidence
— readthedocs + HF discussions; exact parameter names need verification against
the installed package before the perturbation tool is written.)

### Subprocess Contract

Follows the exact same pattern as `annotation/fm_client.py`:
- Main venv never imports `geneformer` or torch from this venv
- A new `geneformer_worker/run_geneformer_perturb.py` script in the
  `geneformer_worker/.venv` environment accepts structured input via CLI args
  and prints a JSON result to stdout
- `perturbation/fm_client.py` (new file) calls this via `subprocess.run()`
  with a timeout, parses the JSON output

### Setup

```bash
python3.10 -m venv geneformer_worker/.venv
git lfs install
git clone https://huggingface.co/ctheodoris/Geneformer geneformer_worker/src
geneformer_worker/.venv/bin/pip install -e geneformer_worker/src
geneformer_worker/.venv/bin/python -c "import geneformer; print('geneformer OK')"
```

---

## 5. Session History Replay

**No new packages.** The installed `claude-agent-sdk==0.2.152` already
exposes the required APIs (confirmed via live SDK introspection):

```python
from claude_agent_sdk import list_sessions, get_session_messages, SessionMessage

# get_session_messages signature (live help() output):
get_session_messages(
    session_id: str,
    directory: str | None = None,
    limit: int | None = None,
    offset: int = 0,
) -> list[SessionMessage]

# SessionMessage fields:
# .type: Literal['user', 'assistant']
# .uuid: str
# .session_id: str
# .message: dict  ← raw Anthropic API message (role + content blocks)
```

`SessionMessage.message` is the raw Anthropic API dict. For frontend display,
extract `content` blocks of type `"text"` from `message["content"]`.

### Schema Addition to SQLite `agent/memory.sqlite`

The existing `SessionMemory` class manages `sessions` and `session_memory`
tables. A new `messages` table persists conversation turns for frontend
replay without depending on JSONL files on disk (important for Docker where
`~/.claude/projects/` may not be mounted):

```sql
CREATE TABLE IF NOT EXISTS messages (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id  TEXT    NOT NULL,
    role        TEXT    NOT NULL,    -- 'user' | 'assistant'
    content     TEXT    NOT NULL,    -- JSON-encoded content blocks array
    created_at  TEXT    NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_messages_session ON messages(session_id, id);
```

**Write strategy:** After each `ask()` call completes, call
`get_session_messages()` and upsert any new messages into this table (keyed
by `SessionMessage.uuid` to avoid duplicates). The new FastAPI endpoint
`GET /api/sessions/{session_id}/messages` returns these rows for the frontend
to render the thread on resume.

**Alternative (simpler but fragile in Docker):** Read from JSONL transcripts
directly via `get_session_messages()` at resume time, no schema change. Works
only if `~/.claude/projects/` is mounted into the backend container. For a
Docker-first deployment this is not reliable — use the SQLite approach.

---

## 6. Result Export

**No new packages.** Standard Python/pandas/FastAPI tools are sufficient:

| Export | Implementation | API Shape |
|--------|----------------|-----------|
| Cluster assignments CSV | `adata.obs[["leiden"]].reset_index().to_csv()` | `GET /api/datasets/{id}/export/clusters.csv` |
| DE results CSV | `sc.get.rank_genes_groups_df(adata, group=None).to_csv()` | `GET /api/datasets/{id}/export/de.csv` |
| Annotations CSV | `pd.DataFrame([a.__dict__ for a in annotations]).to_csv()` | `GET /api/datasets/{id}/export/annotations.csv` |
| Reproducible script | f-string template emitting scanpy calls | `GET /api/sessions/{id}/export/script.py` |

All return `fastapi.responses.StreamingResponse` with
`media_type="text/csv"` (or `"text/x-python"`) and
`Content-Disposition: attachment; filename="..."`. `StreamingResponse` is
already in the `fastapi[standard]` install — no additions needed.

The reproducible script is a string template that emits the equivalent
scanpy Python calls for the session's analysis (ingest path, QC parameters,
clustering resolution, annotation model used). It is not executed by the
server — it is generated as a static string and returned as a file download.

---

## 7. Docker Compose Deployment

### Backend Service (FastAPI + main venv)

**Base image:** `python:3.12-slim`

The main venv requires Python 3.12 (`pyproject.toml: requires-python = ">=3.12"`).
`python:3.12-slim` is the minimal Debian-based image with no GPU requirements.
Multi-stage build: builder stage installs `uv` and resolves deps into a venv,
runtime stage copies the venv only (keeps image small).

### GPU Worker Service (scGPT + Geneformer)

**Base image:** `pytorch/pytorch:2.14.0-cuda12.6-cudnn9-runtime`

Rationale: Latest stable PyTorch as of September 2026 (confirmed Docker Hub —
2.14.0 tags pushed ~14 days ago). The `-runtime` variant (3.69 GB) omits
compilation tools. scGPT and Geneformer do not compile native extensions at
install time; use `-devel` (13.31 GB) only if a transitive dep needs CUDA
headers at build time.

**Python version complexity in the GPU worker container:**

The `pytorch/pytorch:2.14.0` image ships Python 3.11. The worker needs:
- Python 3.9 for the scGPT venv
- Python 3.10 for the Geneformer venv

The Dockerfile for the GPU worker must install Python 3.9 and 3.10 explicitly.
On Ubuntu-based PyTorch images, use the `deadsnakes` PPA:
```dockerfile
RUN add-apt-repository ppa:deadsnakes/ppa && \
    apt-get update && \
    apt-get install -y python3.9 python3.9-venv python3.10 python3.10-venv
```
This is the known, supported way to install multiple Python versions alongside
the system Python on Ubuntu/Debian. The PyTorch runtime itself uses the
container's native Python 3.11 — the scGPT and Geneformer venvs use their
own interpreter paths and are fully isolated from it.

**Alternative base for GPU worker:** `nvidia/cuda:12.6.2-cudnn9-runtime-ubuntu22.04`
then install Python 3.9 + 3.10 + 3.11, pip, and both venvs from scratch.
More control over Python versions at the cost of a larger, more complex
Dockerfile. Worth considering if the PyTorch base image's Ubuntu version
causes `deadsnakes` compatibility issues.

**CPU-only fallback (no GPU host):**
Use `python:3.12-slim` as the worker base, set `CUDA_VISIBLE_DEVICES=""`.
scGPT and Geneformer run on CPU — extremely slow (scGPT reference embedding
takes ~38 minutes for 3000 cells on CPU per existing README) but functional
for smoke testing and development.

### Compose Structure

```yaml
services:
  backend:
    build:
      context: .
      dockerfile: Dockerfile.backend
    # python:3.12-slim; FastAPI + main venv; serves frontend via StaticFiles
    ports:
      - "8000:8000"
    volumes:
      - ./agent/memory.sqlite:/app/agent/memory.sqlite
      - ./data:/app/data

  worker:
    build:
      context: .
      dockerfile: docker/worker/Dockerfile
    # pytorch/pytorch:2.14.0-cuda12.6-cudnn9-runtime
    # + deadsnakes Python 3.9 (scGPT venv) + Python 3.10 (Geneformer venv)
    volumes:
      - ./bio_fm_worker:/app/bio_fm_worker
      - ./geneformer_worker:/app/geneformer_worker
      - ./data:/app/data
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              count: 1
              capabilities: [gpu]
    profiles: ["gpu"]    # opt-in; omit for CPU-only run
```

The backend calls worker scripts via `subprocess.run()` (existing pattern).
No message queue, no HTTP bridge between backend and worker — workers are
invoked as subprocesses from within the backend container, with shared
filesystem access via Docker volume mounts.

**Note:** For subprocess calls to cross container boundaries, the volumes
approach above works only if both services share a filesystem. For a fully
separated container model, the worker scripts must be invocable via a thin
HTTP endpoint in the worker container (or a shared volume with socket/pipe).
The simplest v1.2 approach is a single container that contains both services;
the `worker` service exists mainly for GPU resource reservation and to allow
CPU-only deployment via `--profile` flag. Decide during the Docker phase
whether to use single-container or two-container; the stack choices support
both.

---

## Isolation Summary

| Package | Environment | Python | Reason for Isolation |
|---------|-------------|--------|----------------------|
| `scgpt==0.2.4` + `torch==2.3.0` + `torchtext==0.18.0` | `bio_fm_worker/.venv` | 3.9.6 | `scvi-tools<1.0` requires Python <=3.9; `torchtext==0.18.0` must match `torch==2.3.0` exactly |
| `geneformer` (git install) + modern `torch` | `geneformer_worker/.venv` (new) | 3.10.x | `python_requires=">=3.10"` — incompatible with bio_fm_worker's Python 3.9 |
| `cellxgene-census`, `scanpy`, `fastapi`, `claude-agent-sdk` | root `.venv` | 3.12 | No conflicts; main app dependencies |

The subprocess JSON protocol is the only integration boundary. The main venv
never imports torch, scgpt, or geneformer.

---

## What NOT to Add

| Package | Why Not | What to Use Instead |
|---------|---------|---------------------|
| `celery` / `rq` / `redis` | Message queue is over-engineering for a one-researcher internal tool; subprocess is already working for scGPT | `subprocess.run()` — existing, validated pattern |
| `alembic` | Schema is two existing tables + one new `messages` table; no migration framework needed at this scale | Raw `CREATE TABLE IF NOT EXISTS` in `SessionMemory.__init__()` |
| `cell-gears` (GEARS) | Separate PyTorch Geometric stack; adds a third isolated venv for a feature not in v1.2 scope (Geneformer is the second perturbation model for v1.2) | Geneformer `InSilicoPerturber` |
| `scgenept` | CZI's experimental scGPT+GPT-4 wrapper; adds Anthropic API dependency in the worker venv | Native `scgpt.tasks` |
| `bionemo` | NVIDIA BioNeMo has a Geneformer re-implementation but requires an NVIDIA NGC account; not the reference implementation | Official `ctheodoris/Geneformer` from HuggingFace |
| `gunicorn` | Single-researcher tool; single Uvicorn worker is already working and sufficient | `uvicorn` (already in `fastapi[standard]`) |
| `fastmcp` / external MCP server | v1.2 tools are in-process; adding an out-of-process MCP server adds latency and operational complexity with no benefit at current scale | Direct function calls within the FastAPI process for pipeline tools; subprocess for FM workers |

---

## Version Compatibility Matrix — v1.2 Critical Pins

| Package | Version | Constraint | Notes |
|---------|---------|------------|-------|
| `torch` (bio_fm_worker) | `==2.3.0` | HARD PIN | `torchtext==0.18.0` ABI match. Do NOT upgrade without rebuilding torchtext |
| `torchtext` (bio_fm_worker) | `==0.18.0` | Fixed by scgpt install | Unmaintained upstream since 2023; version is non-negotiable |
| `anndata` (bio_fm_worker) | `==0.10.9` | Fixed by Python 3.9 floor | `anndata>=0.11` requires Python >=3.10 |
| `cellxgene-census` (main) | `>=1.18.0` | Already declared | `tiledbsoma>=1.15.3` pulled transitively; no direct pin needed |
| Geneformer | git main | No PyPI release | `python_requires=">=3.10"`; modern torch (no torchtext dep) |
| `claude-agent-sdk` | `>=0.2.152` | Already declared | `list_sessions()` + `get_session_messages()` confirmed present in 0.2.152 |
| `fastapi[standard]` | `>=0.141.1` | Already declared | `StreamingResponse` for CSV export is in the standard install |
| `pytorch/pytorch` (Docker) | `2.14.0-cuda12.6-cudnn9-runtime` | Docker base image pin | Latest stable Sept 2026; pin full tag for reproducibility |

---

## Sources

- `bio_fm_worker/.venv` live `pip list` — torch==2.3.0, torchtext==0.18.0, scgpt==0.2.4, anndata==0.10.9 (HIGH — direct observation)
- `claude_agent_sdk` v0.2.152 live introspection — `list_sessions`, `get_session_messages`, `SessionMessage` API shapes (HIGH — direct observation)
- https://pypi.org/project/cellxgene-census/ — v1.18.0, Python >=3.10 (HIGH)
- https://chanzuckerberg.github.io/cellxgene-census/ — `open_soma()` / `get_anndata()` API (HIGH — official docs)
- https://huggingface.co/ctheodoris/Geneformer/raw/main/setup.py — `python_requires=">=3.10"`, full `install_requires` list (HIGH — live fetch)
- https://huggingface.co/ctheodoris/Geneformer — git-clone-only installation, no PyPI package (HIGH)
- https://geneformer.readthedocs.io/en/latest/geneformer.in_silico_perturber.html — `InSilicoPerturber` API (MEDIUM)
- https://hub.docker.com/r/pytorch/pytorch/tags — 2.14.0-cuda12.6-cudnn9-runtime is latest stable as of Sept 2026 (HIGH — live fetch)
- https://code.claude.com/docs/en/agent-sdk/sessions — official session API docs confirming `list_sessions()` / `get_session_messages()` are public APIs (HIGH — official docs)

---
*Stack research for: BioClaw v1.2 new features*
*Researched: 2026-09-16*
