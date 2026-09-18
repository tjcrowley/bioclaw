# Phase 14: Docker Compose Deployment - Research

**Researched:** 2026-09-17
**Domain:** Docker / Docker Compose packaging of a multi-Python-environment bioinformatics agent (FastAPI backend + static frontend + two isolated FM subprocess workers)
**Confidence:** MEDIUM (architecture mapping is HIGH confidence — verified directly against this repo's code; Docker/Compose mechanics are HIGH confidence from official docs; the checkpoint/vendored-package reproducibility risk is the one area no amount of Docker best-practice research fully resolves — flagged explicitly)

## Summary

This phase is **not a normal "containerize a web app" job**. The real complexity is that `webapp/backend/main.py` (FastAPI, single Uvicorn process, already serves the vanilla-JS frontend itself via a `StaticFiles` mount at `/app` — there is no separate frontend build or server) is only the visible tip. Underneath, `annotation/fm_client.py` and `perturbation/geneformer_client.py` do **not** call a network service for FM inference — they `subprocess.run()` a *relative, repo-root-anchored* path to a second/third Python interpreter (`bio_fm_worker/.venv/bin/python`, `geneformer_worker/.venv/bin/python`) from *inside the backend process itself*. This means the "optional GPU worker" cannot be a separate networked container without rewriting those two client modules (out of scope for a packaging-only phase) — it has to be the **same container** as the backend, with all three Python environments baked in side by side, `cwd` fixed at the repo root so the hardcoded relative paths resolve, and GPU passthrough attached to that one container (not a distinct service).

The second major complexity is reproducibility of a genuinely "clean checkout." Three artifact classes required for the phase's own success criteria are `.gitignore`d and therefore **absent from a fresh `git clone`**: (1) `bio_fm_worker/checkpoints/scGPT_human/` (196 MB `best_model.pt`, fetched via `gdown` from a Google Drive-hosted zoo — an anti-automation-prone host, not a stable API); (2) `bio_fm_worker/reference/reference.h5ad` (a cellxgene-census-derived reference index, rebuildable via a documented one-liner, but requires live network access to census S3 which the codebase's own comments record as flaky/slow); (3) `geneformer_worker/src/` (a `git clone` + `git lfs pull` of `ctheodoris/Geneformer` from Hugging Face, editable-pip-installed, requiring a *specific two-step LFS include pattern* to get both the checkpoint and its gene-dictionary pickles) **plus an uncommitted, hand-patched fix to that vendored package's ~15 hardcoded `device="cuda"` call sites** that currently exists only on the researcher's local disk and is not captured anywhere in version control. None of this is solved by "more Docker best practice" — it needs a concrete decision in the plan about what gets baked into the image build vs. fetched at first-run vs. requires the phase to newly commit a patch file that doesn't exist in the repo today.

**Primary recommendation:** Ship **one** Docker image/service (`backend`) that installs the root project venv, `bio_fm_worker/.venv`, and `geneformer_worker/.venv` as three separate stages in one multi-stage Dockerfile (three different base images, one per required Python version), bakes in both checkpoints and the census-built reference index at build time (they are small — ~280 MB combined — well within normal image-size norms), commits a new `docker/geneformer_cuda_fallback.patch` file capturing the currently-untracked CUDA-fallback edit and applies it via `git apply` immediately after the Geneformer `git clone`+`pip install -e`, and runs `uvicorn webapp.backend.main:app --host 0.0.0.0 --port 8000 --workers 1` as the fixed CMD (never overridable via compose `environment:`). Attach GPU passthrough to this single service via `deploy.resources.reservations.devices` gated behind a Compose **profile** (`gpu`) so a bare `docker compose up` always works CPU-only and `docker compose --profile gpu up` opts in when an NVIDIA GPU + `nvidia-container-toolkit` are present — this is the only mechanism that makes "optional" actually mean optional under Compose's current behavior (a GPU device reservation that cannot be satisfied fails the service, it does not silently degrade).

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-------------------|
| DOCK-01 | Full stack (backend + optional GPU worker for bio FM inference) starts with a single `docker compose up` command from a clean checkout, requiring only environment variable configuration — hard-codes single-worker constraint | Architecture Patterns (single-container-with-3-venvs design, GPU-profile pattern), Common Pitfalls (relative subprocess paths, gitignored checkpoint/reference/vendored-clone reproducibility, untracked CUDA patch), Code Examples (multi-stage Dockerfile skeleton, compose GPU profile, entrypoint), Validation Architecture (compose smoke-test plan) |
</phase_requirements>

## Standard Stack

### Core
| Tool | Version | Purpose | Why Standard |
|------|---------|---------|---------------|
| Docker Engine | 29.x (confirmed installed: `29.3.1`) | Image build/run | Already present on this machine; no version gap to bridge |
| Docker Compose | v2 plugin, `compose spec` (confirmed installed: `v5.1.1`) | Multi-service orchestration | `docker compose` (not the legacy standalone `docker-compose` v1 binary) is the current, actively-developed tool; v1 is EOL |
| `uv` | already pinned via `uv.lock` in repo | Main-venv dependency install inside the Docker build | Project already standardizes on `uv`; official `astral-sh/uv` Docker guide documents the exact multi-stage pattern to use (`uv sync --frozen --no-install-project`, then copy `.venv`) |
| `python:3.13-slim` (Debian bookworm) | matches `.venv/pyvenv.cfg`'s actual resolved `3.13.12` (not just the `>=3.12` floor in `pyproject.toml`) | Base image for the main-venv build stage | Pin to the exact interpreter minor version already verified working locally, not just the floor |
| `python:3.9-slim` (Debian bookworm) | matches `bio_fm_worker/.venv`'s `3.9.6` | Base image for the scGPT-worker build stage | scGPT's `scvi-tools<1.0`/`torchtext` pins are only verified working under Python 3.9 in this repo — do not "upgrade" this during Dockerization |
| `python:3.10-slim` (Debian bookworm) | matches `geneformer_worker/.venv`'s `3.10.14` | Base image for the Geneformer-worker build stage | Geneformer's `setup.py` floor is `>=3.10`; this repo's working combination is 3.10.14 exactly |
| `git` + `git-lfs` | latest apt packages | Fetching Geneformer's vendored HF clone during image build | Required inside the *build* stage only (multi-stage build discards it from the final image) |

### Supporting
| Tool | Version | Purpose | When to Use |
|------|---------|---------|-------------|
| `gdown` | latest via pip | Automating the scGPT `best_model.pt` fetch from Google Drive during image build | Only if choosing "download during build" over "vendor a pre-fetched checkpoint into the build context" — see Common Pitfalls, this is the single highest-risk external dependency in the whole phase |
| NVIDIA Container Toolkit (`nvidia-container-toolkit`) | host-side install, not baked into the image | Lets a GPU-having host expose `/dev/nvidia*` + CUDA libs into a container via `--gpus`/Compose `deploy.resources.reservations.devices` | Only required on the *host* running `docker compose --profile gpu up`; irrelevant to the image build itself |
| Compose `profiles:` | Compose Specification (current) | Making the GPU device reservation truly opt-in per `docker compose up` invocation | This is the documented, current mechanism for "optional" service/config in Compose — not a Docker Engine feature |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| One multi-venv "backend" container | Split `backend`, `scgpt-worker`, `geneformer-worker` into three networked containers, with `fm_client.py`/`geneformer_client.py` rewritten to call an HTTP/RPC endpoint instead of `subprocess.run()` | Cleaner "microservices" shape and would let GPU passthrough attach to only the FM-worker containers — but requires rewriting two already-tested subprocess-shim modules, changing the annotation/perturbation pipeline call sites, and adding a queueing/serialization layer. This is a real architecture change, not a Docker packaging task, and is explicitly not implied by DOCK-01's wording ("optional GPU worker for bio FM inference" describes a *capability*, not necessarily a separate compose service) |
| Baking checkpoints/reference/vendored-clone into the image at build time | Download them at container **first-start** via an entrypoint script, caching into a named volume | Keeps the image build itself network-independent and image size smaller during CI, but pushes the same `gdown`/census-network fragility to `docker compose up` time instead of `docker build` time — does not remove the risk, only moves it. Given the artifacts here are small (~280 MB total, not multi-GB), bake-in is simpler and matches "no manual setup steps beyond env vars" more literally (a successful `docker build` is a one-time, repeatable, CI-able event; `docker compose up` failing on first run due to a Google Drive anti-bot wall is a worse researcher experience) |
| Separate `frontend` container (nginx serving static files, reverse-proxying `/api`/`/ws` to backend) | Nothing — the existing FastAPI app already serves `webapp/frontend/` via `StaticFiles(directory=..., html=True)` mounted at `/app`, with no build step (STATE.md: "Webapp is vanilla JS + no build step... v1.2 Docker should not require a build step either") | A separate frontend container would add an nginx image, a reverse-proxy config, and CORS/cookie-domain considerations the current same-origin design avoids entirely, for zero functional gain — do not add it |

**Installation (illustrative, exact syntax goes in the Dockerfile written during planning):**
```bash
# Stage 1 (main venv): python:3.13-slim + uv
# Stage 2 (scGPT worker venv): python:3.9-slim, pip install scgpt then pip install "torch==2.3.0"
# Stage 3 (Geneformer worker venv): python:3.10-slim, git clone + git lfs pull + pip install -e + pip install "transformers==4.46"
# Final stage: slim runtime base, COPY all three venvs + checkpoints + app code in
```

## Architecture Patterns

### Recommended Project Structure (new files this phase adds)
```
bioclaw/
├── Dockerfile                        # multi-stage: 3 builder stages + 1 runtime stage
├── .dockerignore                     # excludes .venv/, bio_fm_worker/.venv/, geneformer_worker/.venv/,
│                                      #   geneformer_worker/src/, data/, agent/logs/, .git/, tool_calls.jsonl
├── docker-compose.yml                # single `backend` service (serves API + frontend), no GPU by default
├── docker-compose.gpu.yml (or a `profiles: [gpu]` block in the base file)
├── docker/
│   ├── entrypoint.sh                 # exec uvicorn ... --workers 1 (fixed, not overridable)
│   └── geneformer_cuda_fallback.patch  # NEW — captures the currently-untracked device="cuda" fix
├── .env.example                      # ANTHROPIC_API_KEY=, BIOCLAW_WEB_PASSWORD=, (no secrets committed)
└── (existing repo layout unchanged — Docker must NOT require restructuring
     bio_fm_worker/, geneformer_worker/, webapp/, agent/, since fm_client.py/
     geneformer_client.py/agent/memory.py/qa/session.py's hardcoded default
     paths are all relative to the repo root and must keep resolving)
```

### Pattern 1: Single "backend" service hosts all three Python environments
**What:** One Dockerfile with three independent builder stages (one per Python version required — 3.13 main, 3.9 scGPT, 3.10 Geneformer), each producing a self-contained venv directory, all three `COPY --from=<stage>` into one final runtime image at their exact existing repo-relative paths (`/app/.venv`, `/app/bio_fm_worker/.venv`, `/app/geneformer_worker/.venv`). `WORKDIR /app` in the final stage, and the container's `CMD`/`ENTRYPOINT` runs the app from `/app` so every hardcoded relative path in `annotation/fm_client.py` (`worker_python="bio_fm_worker/.venv/bin/python"`), `perturbation/geneformer_client.py` (`worker_python="geneformer_worker/.venv/bin/python"`), `annotation/pipeline.py` (`reference_index_path="bio_fm_worker/reference/reference.h5ad"`), `agent/tools.py` (`STORE_ROOT = os.environ.get("BIOCLAW_STORE_ROOT", "data")`), `agent/memory.py` (`SessionMemory(root="agent/memory.sqlite")` — no env override exists), and `qa/session.py` (`log_path: Path = Path("tool_calls.jsonl")` — no env override exists) resolves exactly as it does in local dev.
**When to use:** Always, for this codebase, unless the phase is willing to also refactor `fm_client.py`/`geneformer_client.py` into network calls (not recommended — see Alternatives Considered).
**Example (illustrative Dockerfile skeleton — verify exact multi-stage COPY syntax against the official uv Docker guide during planning):**
```dockerfile
# --- Stage: main venv (root project, Python 3.13) ---
FROM python:3.13-slim AS main-builder
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/
WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --extra web --no-install-project
COPY . .
RUN uv sync --frozen --extra web

# --- Stage: scGPT worker venv (Python 3.9) ---
FROM python:3.9-slim AS scgpt-builder
RUN python -m venv /opt/bio_fm_worker_venv \
 && /opt/bio_fm_worker_venv/bin/pip install --upgrade pip \
 && /opt/bio_fm_worker_venv/bin/pip install scgpt \
 && /opt/bio_fm_worker_venv/bin/pip install "torch==2.3.0"   # repin, per bio_fm_worker/README.md

# --- Stage: Geneformer worker venv (Python 3.10) ---
FROM python:3.10-slim AS geneformer-builder
RUN apt-get update && apt-get install -y --no-install-recommends git git-lfs \
 && git lfs install
RUN python -m venv /opt/geneformer_worker_venv \
 && git clone https://huggingface.co/ctheodoris/Geneformer /opt/geneformer_src \
 && cd /opt/geneformer_src \
 && git lfs pull --include="Geneformer-V1-10M/*,geneformer/gene_dictionaries_30m/*,geneformer/*.pkl" \
 && /opt/geneformer_worker_venv/bin/pip install --upgrade pip \
 && /opt/geneformer_worker_venv/bin/pip install -e /opt/geneformer_src \
 && /opt/geneformer_worker_venv/bin/pip install "transformers==4.46"  # repin, per geneformer_worker/README.md
COPY docker/geneformer_cuda_fallback.patch /tmp/
RUN cd /opt/geneformer_src && git apply /tmp/geneformer_cuda_fallback.patch

# --- Final runtime stage ---
FROM python:3.13-slim AS runtime
WORKDIR /app
COPY --from=main-builder /app /app
COPY --from=scgpt-builder /opt/bio_fm_worker_venv /app/bio_fm_worker/.venv
COPY --from=geneformer-builder /opt/geneformer_worker_venv /app/geneformer_worker/.venv
COPY --from=geneformer-builder /opt/geneformer_src /app/geneformer_worker/src
# checkpoints/reference baked in — see Pattern 2
ENV BIOCLAW_STORE_ROOT=/app/data
EXPOSE 8000
CMD ["/app/.venv/bin/uvicorn", "webapp.backend.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
```
*(Source: pattern synthesized from the official `astral-sh/uv` Docker integration guide's documented multi-stage shape, `bio_fm_worker/README.md`'s and `geneformer_worker/README.md`'s exact "How it was created" commands verified directly in this repo, and the LFS include-path fix documented in `geneformer_worker/README.md`'s "Real-run fixes" section — this is a HIGH-confidence synthesis of already-proven repo-local commands, not a novel/unverified Docker pattern.)*

### Pattern 2: Bake checkpoints + reference index into the image, don't rely on a runtime mount
**What:** Add a build-context staging step (either a `COPY` of a pre-fetched checkpoint placed in the build context by a `make`/shell target run before `docker build`, or a `RUN gdown ...` step inside the Dockerfile) that produces `bio_fm_worker/checkpoints/scGPT_human/{args.json,vocab.json,best_model.pt}` and `bio_fm_worker/reference/reference.h5ad` inside the image, at their existing hardcoded default paths.
**When to use:** Given the combined size here is small (~280 MB: 196 MB scGPT checkpoint + a few-MB reference index + 79 MB Geneformer-V1-10M, which is *already* baked in during the `geneformer-builder` LFS pull), baking in is simpler and satisfies "no manual setup steps required beyond env vars" more literally than a runtime-download entrypoint would (see Common Pitfalls for the gdown fragility this doesn't eliminate either way).
**Example:**
```bash
# Reference index: rebuildable from cellxgene-census with a pinned CENSUS_VERSION
# (annotation/reference.py — already network-automatable, no anti-bot wall):
uv run python -c "from annotation.reference import build_reference_index; print(build_reference_index())"

# scGPT checkpoint: the ONLY artifact in this phase without a clean, API-stable
# automated fetch path (see Pitfall 2 below) — document the manual gdown command
# from bio_fm_worker/README.md and decide in planning whether the Dockerfile
# attempts it automatically (best-effort, may need a human checkpoint) or the
# build process requires a pre-populated build-context file.
```

### Pattern 3: Compose `profiles:` for optional GPU, not a bare `deploy.resources` block
**What:** Declare the GPU device reservation on the `backend` service but gate it behind a named profile so the *default* `docker compose up` invocation never attempts a GPU reservation. Compose (current spec, confirmed via official Docker docs) **does** honor `deploy.resources.reservations.devices` outside Swarm mode specifically for GPU access — but if `capabilities: [gpu]` is declared unconditionally and no GPU/`nvidia-container-toolkit` is present on the host, the service fails to start (it is not a silent, automatic CPU fallback at the Compose layer). The code's own CPU fallback (`torch.cuda.is_available()` checks) only matters *after* the container itself has started successfully.
**When to use:** Whenever DOCK-01's "optional" wording is implemented — this is the only mechanism the current Compose spec provides that keeps `docker compose up` working with zero flags on a GPU-less machine while still allowing a GPU-having machine to opt in.
**Example:**
```yaml
# docker-compose.yml
services:
  backend:
    build: .
    ports: ["8000:8000"]
    environment:
      - ANTHROPIC_API_KEY=${ANTHROPIC_API_KEY}
      - BIOCLAW_WEB_PASSWORD=${BIOCLAW_WEB_PASSWORD}
    volumes:
      - bioclaw-data:/app/data
      - bioclaw-memory:/app/agent   # NOTE: shadows code unless narrowed — see Open Questions
    command: ["/app/.venv/bin/uvicorn", "webapp.backend.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]

  backend-gpu:
    extends: backend
    profiles: ["gpu"]
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              count: 1
              capabilities: [gpu]

volumes:
  bioclaw-data:
  bioclaw-memory:
```
*(Illustrative — the exact "extend one service with a GPU variant" vs. "one service, GPU block behind a profile flag directly on it" shape should be finalized during planning by testing `docker compose config` against both; `profiles:` + `deploy.resources.reservations.devices` mechanics are HIGH confidence per official Docker Compose GPU-support docs, the specific extends-based split above is a MEDIUM-confidence illustrative composition, not verified against a real Compose file in this repo.)*

### Anti-Patterns to Avoid
- **Multi-worker Uvicorn or a process supervisor (gunicorn+uvicorn workers, `--workers N>1`, PM2, etc.):** `webapp/backend/streaming.py`'s `_QUEUES: dict[str, asyncio.Queue]` module-level registry is single-process, in-memory. This is an already-documented, already-enforced project constraint (`webapp/README.md`: "Never add `--workers` or run this behind a multi-process supervisor"). Hard-code `--workers 1` directly in the image's `CMD`/entrypoint (not just as a compose `environment:` default) so it cannot be casually overridden.
- **A separate frontend container/build step:** Contradicts the explicit STATE.md decision that Docker "should not require a build step either," and the frontend is already served same-origin by the one FastAPI process — a second container adds CORS/cookie-domain complexity for zero benefit.
- **Rewriting `fm_client.py`/`geneformer_client.py` to call a networked worker "to make GPU passthrough cleaner":** Out of scope for a packaging phase and changes tested, working code (Phase 4/13 already verified these subprocess shims end-to-end against real checkpoints).
- **Unconditional GPU `deploy.resources.reservations.devices` on the default `backend` service:** Breaks `docker compose up` on any machine without an NVIDIA GPU + toolkit — the opposite of "no manual setup steps beyond env vars."
- **Rebuilding `geneformer_worker/src/` from `git clone` without applying the CUDA-fallback patch:** Reproduces the exact upstream bug already found and fixed once (unconditional `device="cuda"` in `emb_extractor.py`/`in_silico_perturber.py`/`perturber_utils.py`), which will hard-crash the Geneformer pipeline on any CPU-only host, GPU-having host with the reservation not attached, or GPU-having host where CUDA silently isn't visible inside the container for any reason.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|--------------|-----|
| Multi-Python-version image | A custom pyenv/deadsnakes-PPA install-from-source script inside one base image | Multiple official `python:<version>-slim` base images, one per builder stage, each producing a self-contained venv copied into the final stage | Official Python Docker images are prebuilt, security-patched, and exactly version-pinned; compiling Python from source inside the image adds build time and a new class of build failures for no benefit here |
| uv-managed dependency install in Docker | A hand-rolled `pip install -r requirements.txt` flow for the main venv | `uv sync --frozen` following the official `astral-sh/uv` Docker integration guide's documented multi-stage pattern | The project already standardizes on `uv`/`uv.lock` for reproducible resolution; re-deriving a `requirements.txt` from `pyproject.toml` for Docker only would introduce a second, driftable dependency manifest |
| Optional GPU device access | Custom shell-script GPU detection (`nvidia-smi` probing) baked into the entrypoint to decide whether to pass `--gpus` at `docker run` time | Compose `profiles:` + `deploy.resources.reservations.devices` with `capabilities: [gpu]` | This is the documented, current Compose-native mechanism; a custom detection script reimplements what Compose profiles already solve, and gets out of sync with Compose version upgrades |
| Health/readiness signaling for the compose smoke test | A bespoke TCP-port-open poll loop | A lightweight `GET /api/health` (or reuse an existing unauthenticated route) + Docker `HEALTHCHECK`/Compose `healthcheck:` | No such endpoint currently exists in `webapp/backend/main.py` — this phase needs to add one (see Validation Architecture Wave 0 Gaps), but once added, standard Compose `healthcheck:` + `depends_on: condition: service_healthy` is the standard mechanism, not a hand-rolled poll script |

**Key insight:** Nearly everything in this domain (multi-stage builds, GPU passthrough, uv-in-Docker) has a current, official, documented pattern — the actual hard part of this phase is not "learn Docker," it's faithfully reproducing this specific repo's three already-hand-tuned Python environments and their gitignored large-file dependencies inside that standard Docker shape.

## Common Pitfalls

### Pitfall 1: Relative subprocess paths break if `cwd` isn't the repo root
**What goes wrong:** `annotation/fm_client.py::call_scgpt_annotate()` and `perturbation/geneformer_client.py::call_geneformer_perturb()` default `worker_python`/`script_path`/`model_dir` to plain relative strings (e.g. `"bio_fm_worker/.venv/bin/python"`). `subprocess.run()` resolves relative paths against the *parent process's current working directory*, not the script's own file location. If the container's `WORKDIR` isn't exactly the repo root, or if Uvicorn is somehow started from a different directory, every FM call fails with a confusing "file not found" from `subprocess.run`, not an import error.
**Why it happens:** These defaults were designed for "run everything from the repo root," which has always been true in local dev (`uv run uvicorn ...` from the repo root) and was never tested against a different `cwd`.
**How to avoid:** Set `WORKDIR /app` in the final Docker stage, `COPY` the entire repo layout preserved (not flattened/restructured) into `/app`, and ensure the Compose `command:`/entrypoint never `cd`s elsewhere before invoking uvicorn.
**Warning signs:** FM annotation/perturbation tool calls return `RuntimeError` with a subprocess exit/`FileNotFoundError`-shaped message, while everything else in the container works fine.

### Pitfall 2: The scGPT checkpoint has no stable, automatable download API
**What goes wrong:** `bio_fm_worker/checkpoints/scGPT_human/best_model.pt` (196 MB) was fetched via `gdown` from a Google-Drive-hosted "model zoo" folder (`bio_fm_worker/README.md`, `gdown.log` in this repo). Google Drive is well-known to intermittently serve an interactive "can't scan for viruses" confirmation page for larger files to automated/scripted clients, and to rate-limit/IP-block repeated automated downloads — this is explicitly *not* a stable API, and this repo's own 04-05-PLAN.md already anticipated this ("If the download fails ... stop attempting workarounds ... do not try to script around an anti-automation control").
**Why it happens:** scGPT's official checkpoint distribution is Google Drive, not a CDN/S3/HTTPS-direct-link/HuggingFace-hub location with a stable programmatic API.
**How to avoid:** Attempt the automated `gdown` fetch inside the Dockerfile build stage as a best-effort step, but the plan must explicitly account for a fallback: either the Dockerfile accepts a pre-populated build-context file (researcher runs the existing manual `gdown` command once locally, per `bio_fm_worker/README.md`, and the Docker build `COPY`s it in — trading "zero manual steps" for "one manual step done once, cached forever after"), or the phase's success criterion 1 ("no manual setup steps required beyond env vars") is explicitly scoped as "on a machine where the automated fetch succeeds" with a documented human-verify fallback, mirroring the `checkpoint:human-verify` gate pattern this repo already used in Phase 4/13.
**Warning signs:** `docker build` hangs, times out, or downloads a small HTML confirmation page (a few KB) instead of the real 196 MB `.pt` file — the classic Google Drive automation-wall failure signature.

### Pitfall 3: The Geneformer CUDA-fallback patch exists only on one developer's local disk
**What goes wrong:** `geneformer_worker/README.md` documents that `geneformer_worker/src/` (the vendored, git-lfs-pulled `ctheodoris/Geneformer` clone) required an **uncommitted, local-only** patch — ~15 call sites across `emb_extractor.py`, `in_silico_perturber.py`, and `perturber_utils.py` hardcode `device="cuda"`/`.to("cuda")` with no CPU fallback, and were hand-edited in place on this machine's checkout. `geneformer_worker/src/` is itself in `.gitignore` (it's a separate nested git clone, not tracked by this repo), so this fix is invisible to `git clone`/CI/a fresh Docker build entirely. Without it, any CPU-only or CUDA-unavailable-inside-the-container run of the Geneformer pipeline hard-crashes.
**Why it happens:** The patch was applied directly to the vendored clone's files as a quick local fix during Phase 13 verification, with no mechanism in place yet to persist it outside that one checkout.
**How to avoid:** This phase must **commit a new artifact this repo does not currently have** — a `.patch`/`.diff` file (or a small Python/sed script) capturing exactly those edits, checked into version control (e.g., `docker/geneformer_cuda_fallback.patch`), and apply it via `git apply` (or equivalent) as an explicit Docker build step immediately after the `git clone`+`pip install -e` of `geneformer_worker/src`, before any image layer that could be cached past that point. This is real, new work for this phase, not just Docker plumbing — flag it prominently in planning.
**Warning signs:** `ImportError`-free build, but `import geneformer`-based subprocess calls raise a CUDA-runtime error (`AssertionError: Torch not compiled with CUDA enabled` or similar) even in image layers with no GPU attached.

### Pitfall 4: `InSilicoPerturberStats.get_stats()` real-run fixes must survive the rebuild
**What goes wrong:** `geneformer_worker/README.md`'s "Real-run fixes" section documents three bugs found only by running the real (unmocked) pipeline — one of the three (`get_stats()` returns `None`, not the DataFrame) was fixed **in `run_geneformer_perturb.py` itself** (already committed, safe), but the LFS include-path fix (missing `geneformer/gene_dictionaries_30m/*.pkl`) is a *build-command* detail, not a code fix, and must be reproduced exactly in the Dockerfile's `git lfs pull --include=` step (see Pattern 1's example) or the container will hit the same `pickle.UnpicklingError: invalid load key, 'v'` this repo already diagnosed once.
**Why it happens:** LFS `--include` patterns are easy to under-scope (the original single-checkpoint-only include missed a sibling directory the tokenizer also needs).
**How to avoid:** Copy the exact, already-verified `git lfs pull --include="Geneformer-V1-10M/*,geneformer/gene_dictionaries_30m/*,geneformer/*.pkl"` pattern from `geneformer_worker/README.md`'s "Real-run fixes" section verbatim into the Dockerfile.
**Warning signs:** `TranscriptomeTokenizer` fails on first tokenize with an unpickling error inside the container, despite `import geneformer` succeeding cleanly.

### Pitfall 5: `agent/memory.sqlite` and `tool_calls.jsonl` have no env-var override, unlike `BIOCLAW_STORE_ROOT`
**What goes wrong:** `agent/tools.py`'s dataset store root is parametrized (`BIOCLAW_STORE_ROOT` env var, defaulting to `"data"`), but `webapp/backend/deps.py::get_session_memory()` instantiates `SessionMemory()` with no arguments (defaulting to the hardcoded `"agent/memory.sqlite"`), and `qa/session.py::ask_question()`'s `log_path` default is a bare `Path("tool_calls.jsonl")` — neither has an environment-variable override today. A Compose volume for session/audit-log persistence across container restarts therefore has to be mounted at those exact literal container-relative paths (`/app/agent/memory.sqlite` as a single-file bind mount, or `/app/tool_calls.jsonl`), not a clean, single top-level "data" directory the way `BIOCLAW_STORE_ROOT` allows.
**Why it happens:** `BIOCLAW_STORE_ROOT` was added deliberately (per `agent/tools.py`'s own comment: "Deliberately never read from LLM-controlled `args`") for a security reason unrelated to Docker; the memory/log paths were never revisited for external configurability.
**How to avoid:** During planning, decide explicitly between (a) mounting named volumes at the exact literal paths `/app/agent/memory.sqlite` and `/app/tool_calls.jsonl` (zero code change, but a single-file bind mount is slightly more fragile — e.g. SQLite WAL mode's `-wal`/`-shm` sidecar files need to live alongside it, so prefer mounting the containing directory pattern carefully rather than one bare file) or (b) adding small `BIOCLAW_MEMORY_DB`/`BIOCLAW_LOG_PATH` env-var overrides mirroring the existing `BIOCLAW_STORE_ROOT` pattern (a small, in-scope code change, arguably the cleaner fix). Flagged as an Open Question below rather than pre-decided here.
**Warning signs:** Session history / audit log silently resets on every `docker compose down && docker compose up` if no volume is mounted at all; a `docker cp` shows the sqlite file only living inside the ephemeral container layer.

## Code Examples

### Fixed single-worker Uvicorn command (matches existing local-dev invocation exactly)
```bash
# Source: webapp/README.md's documented "Run (every time)" command, adapted for
# container use (0.0.0.0 bind instead of default localhost, explicit --workers 1
# baked into the image CMD instead of relying on Uvicorn's own default-of-1,
# so it cannot be silently overridden via a compose `command:` override):
uvicorn webapp.backend.main:app --host 0.0.0.0 --port 8000 --workers 1
```

### Existing hardcoded worker paths this phase's Docker layout must preserve verbatim
```python
# Source: annotation/fm_client.py (read directly from this repo, 2026-09-17)
def call_scgpt_annotate(
    query_h5ad_path,
    reference_index_path,
    worker_python="bio_fm_worker/.venv/bin/python",
    script_path="bio_fm_worker/run_scgpt_embed.py",
    model_dir="bio_fm_worker/checkpoints/scGPT_human",
    timeout: float = 3600.0,
) -> list["AnnotationCall"]: ...

# Source: perturbation/geneformer_client.py (read directly from this repo, 2026-09-17)
def call_geneformer_perturb(
    query_h5ad_path,
    target_gene,
    target_ensembl_id,
    worker_python="geneformer_worker/.venv/bin/python",
    script_path="geneformer_worker/run_geneformer_perturb.py",
    model_dir="geneformer_worker/src/Geneformer-V1-10M",
    timeout: float = 7200.0,
) -> "GeneformerPerturbationCall": ...
```

### Reproducible venv build commands (already proven in this repo, verified 2026-09-17)
```bash
# scGPT worker venv — bio_fm_worker/README.md, verified working:
python3 -m venv bio_fm_worker/.venv
bio_fm_worker/.venv/bin/pip install --upgrade pip
bio_fm_worker/.venv/bin/pip install scgpt
bio_fm_worker/.venv/bin/pip install "torch==2.3.0"   # repin, MUST run immediately after scgpt install

# Geneformer worker venv — geneformer_worker/README.md, verified working:
python3.10 -m venv geneformer_worker/.venv
geneformer_worker/.venv/bin/pip install --upgrade pip
git lfs install
GIT_LFS_SKIP_SMUDGE=1 git clone https://huggingface.co/ctheodoris/Geneformer geneformer_worker/src
cd geneformer_worker/src \
  && git lfs pull --include="Geneformer-V1-10M/*,geneformer/gene_dictionaries_30m/*,geneformer/*.pkl" \
  && cd -
geneformer_worker/.venv/bin/pip install -e geneformer_worker/src
geneformer_worker/.venv/bin/pip install "transformers==4.46"   # repin, MUST run immediately after
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|-------------------|---------------|--------|
| `docker-compose` standalone v1 binary, `version: "3.x"` key at the top of compose files | `docker compose` v2 plugin (Compose Specification — no `version:` key needed/recommended) | v1 reached EOL (Docker deprecated it in 2023, and current Docker Desktop/Engine installs ship only the v2 plugin) | This environment already has v2 (`v5.1.1`) — write the compose file without a `version:` key; including one is harmless but flagged obsolete by current tooling |
| `docker run --gpus all` only (single-container, no Compose GPU support) | Compose-native `deploy.resources.reservations.devices` with `capabilities: [gpu]`, honored by `docker compose up` outside Swarm specifically for device reservations | Added to Compose Specification some time after the original Swarm-only `deploy:` semantics; now documented as the standard non-Swarm GPU mechanism | Lets this phase express GPU passthrough declaratively in `docker-compose.yml` rather than requiring a separate `docker run` invocation outside Compose |

**Deprecated/outdated:**
- `docker-compose` (hyphenated, v1, Python-based standalone tool): superseded by the `docker compose` v2 Go-based plugin already installed here.
- Top-level `version:` key in compose files: no longer required or meaningfully interpreted by Compose v2; omit it.

## Open Questions

1. **Should `agent/memory.sqlite` and `tool_calls.jsonl` gain env-var path overrides (mirroring `BIOCLAW_STORE_ROOT`) as part of this phase, or should Compose just volume-mount their exact literal container paths?**
   - What we know: `BIOCLAW_STORE_ROOT` already exists as a precedent; the other two paths don't have an equivalent.
   - What's unclear: Whether adding two small env-var overrides is in-scope for a "Docker Compose Deployment" phase (arguably yes, since it directly serves persistence-across-restarts) or should be deferred as unnecessary code churn given literal-path volume mounts work fine.
   - Recommendation: Default to literal-path volume mounts (zero code change) unless the plan-writer judges the env-var addition trivial and clearly better; either is workable.

2. **Does the automated scGPT checkpoint `gdown` fetch actually succeed unattended inside a Docker build in this environment, or does it need a documented manual pre-step / `checkpoint:human-verify` gate?**
   - What we know: This repo's own Phase 4 planning already anticipated and accepted this exact failure mode as a real possibility, not a hypothetical.
   - What's unclear: Whether Google Drive's anti-automation behavior will actually trigger for this specific file/folder at plan-execution time — this can only be determined by attempting it.
   - Recommendation: The plan should attempt the automated `gdown` fetch as the primary path in the Dockerfile, but explicitly define a fallback (pre-populate the build context from a local `bio_fm_worker/checkpoints/scGPT_human/` that already exists on this dev machine, `COPY`d in) and treat success/failure as a `checkpoint:human-verify`-style checkpoint during plan execution, not an assumed-green CI step.

3. **Is a single "backend" Compose service (with the GPU reservation behind a `profiles: [gpu]` flag on that same service) the right shape, or should the plan still expose a visually-distinct `gpu-worker` service name in `docker-compose.yml` for clarity/documentation purposes even though it's architecturally the same container image?**
   - What we know: The subprocess-shim architecture (Pitfall 1) makes a *functionally* separate GPU worker container impossible without a client-code rewrite.
   - What's unclear: Whether DOCK-01's/the success criteria's literal wording ("starts a working backend, frontend, and optional GPU worker") implies the plan-checker or verifier expects to literally see three named services in `docker-compose.yml`, even if two of them point at the same image/Dockerfile.
   - Recommendation: Plan for ONE image/service functionally, but consider whether naming it in a way that satisfies the literal requirement wording (e.g., a `backend` service plus a GPU-profile-gated `backend` override that Compose documentation/README explicitly calls out as "the optional GPU worker mode of the same backend service") avoids a plan-checker mismatch. Surface this explicitly to the user/planner rather than silently picking one interpretation.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 8.x (existing project convention — `pyproject.toml` `[tool.pytest.ini_options]`), extended with a new marker for Docker-gated tests, plus a plain shell smoke-test script for the actual `docker compose up`/`down` cycle (pytest cannot practically drive a real multi-minute Docker build inside the fast/CI tier) |
| Config file | `pyproject.toml` (existing `markers` list — add `docker_smoke: requires a built Docker image / running Docker daemon, excluded from fast/CI runs`, mirroring the existing `bio_fm_smoke`/`geneformer_smoke`/`census_data` pattern) |
| Quick run command | `uv run pytest -q` (existing fast tier — must NOT gain any new dependency on Docker being installed/running) |
| Full suite command | `uv run pytest tests/ -q` plus a separate, explicitly-invoked `scripts/docker_compose_smoke_test.sh` (new) that runs `docker compose build && docker compose up -d && curl` against the health endpoint `&& docker compose down` |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|---------------------|--------------|
| DOCK-01 (criterion 1) | `docker compose up` from a clean checkout starts backend+frontend+optional-GPU-worker with only env vars configured | smoke (shell) | `scripts/docker_compose_smoke_test.sh` (builds image, `docker compose up -d`, polls a new `GET /api/health` endpoint, `docker compose down`) | ❌ Wave 0 — script and health endpoint both need to be created |
| DOCK-01 (criterion 2) | Compose config hard-codes `--workers 1`; verify it cannot be silently overridden | unit/smoke | `docker compose config` output grep-checked for `--workers 1` in the `command`, plus a live check that no `WEB_CONCURRENCY`/`--workers`-style env var in `docker-compose.yml`'s `environment:` block can change it | ❌ Wave 0 — no such check exists yet |
| DOCK-01 (criterion 3) | A researcher can complete upload/census-fetch → analysis → FM inference → CSV export → script export entirely against the compose stack, no local Python deps | manual-only (`checkpoint:human-verify`) — full FM inference (scGPT/Geneformer) real runs take minutes-to-hours per this repo's own documented latencies (`bio_fm_smoke`/`geneformer_smoke` real-checkpoint runs), not automatable inside a fast smoke test | — | Manual verification against the running compose stack, justified by existing precedent (`checkpoint:human-verify` gates already used in Phase 4/13 for the same underlying FM calls) |

### Sampling Rate
- **Per task commit:** `uv run pytest -q` (fast tier — no Docker daemon dependency; keeps existing CI-safe convention)
- **Per wave merge:** `scripts/docker_compose_smoke_test.sh` (build + up + health-check + down) — requires Docker Engine locally, run manually/on-demand, not in the fast tier
- **Phase gate:** Full `docker compose up` from a genuinely clean checkout (fresh `git clone` into a scratch directory, no host-cached `.venv`/checkpoints), followed by the manual end-to-end researcher workflow described in criterion 3, before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `GET /api/health` endpoint in `webapp/backend/main.py` — does not exist today; needed for both Compose `healthcheck:` and the smoke-test script. Should be **unauthenticated** (container orchestration health probes should not need `BIOCLAW_WEB_PASSWORD`) and cheap (no DB/FM calls).
- [ ] `scripts/docker_compose_smoke_test.sh` — new shell script driving `docker compose build && up -d && curl health && down`.
- [ ] `docker/geneformer_cuda_fallback.patch` — new committed artifact capturing the currently-untracked CUDA-fallback edit described in `geneformer_worker/README.md`'s "Real-run fixes" item 2 (must be authored by diffing the current local, patched `geneformer_worker/src/` against a fresh unpatched clone, or by hand-writing the ~15-site edit as a patch file).
- [ ] `docker_smoke` pytest marker registration in `pyproject.toml`'s `[tool.pytest.ini_options] markers` list, mirroring the existing `bio_fm_smoke`/`geneformer_smoke`/`census_data`/`vcc_data` entries.
- [ ] `.dockerignore` — does not exist yet; must exclude all three `.venv/` directories, `geneformer_worker/src/`, `data/`, `agent/logs/`, `agent/memory.sqlite*`, `tool_calls.jsonl`, `.git/`, and any local `bio_fm_worker/checkpoints/`/`bio_fm_worker/reference/` content that the Dockerfile intends to fetch fresh rather than copy from the host (or, if choosing the "COPY from an already-populated local checkout" fallback for Pitfall 2, deliberately NOT excluding those specific paths).

## Sources

### Primary (HIGH confidence)
- Direct repo reads (2026-09-17): `.planning/STATE.md`, `.planning/REQUIREMENTS.md`, `pyproject.toml`, `.gitignore`, `webapp/backend/main.py`, `webapp/backend/streaming.py`, `webapp/backend/deps.py`, `webapp/backend/auth.py`, `webapp/backend/uploads.py`, `webapp/README.md`, `webapp/frontend/index.html`, `webapp/frontend/api.js`, `agent/server.py`, `agent/session.py`, `agent/tools.py`, `agent/memory.py`, `annotation/fm_client.py`, `annotation/pipeline.py`, `annotation/reference.py`, `perturbation/geneformer_client.py`, `bio_fm_worker/README.md`, `geneformer_worker/README.md`, `geneformer_worker/src/requirements.txt`, `geneformer_worker/src/setup.py`, `qa/session.py`, `.planning/phases/04-bio-fm-cell-type-annotation/04-05-PLAN.md`, `.planning/phases/04-bio-fm-cell-type-annotation/04-05-SUMMARY.md`, `.planning/phases/13-real-fm-inference-scgpt-then-geneformer/13-RESEARCH.md`
- `bio_fm_worker/checkpoints/scGPT_human/gdown.log` (local evidence of the actual Google Drive fetch command/URLs used) — confirms Pitfall 2's characterization
- `docker --version` / `docker compose version` run directly in this environment — confirms `29.3.1` / `v5.1.1` are what's actually available here
- [Docker Docs: Compose Deploy Specification](https://docs.docker.com/reference/compose-file/deploy/) — `deploy.resources.reservations.devices` syntax
- [Docker Docs: Run Docker Compose services with GPU access](https://docs.docker.com/compose/how-tos/gpu-support/) — confirms Compose (not just Swarm) honors GPU device reservations
- [astral-sh/uv official Docker integration guide](https://docs.astral.sh/uv/guides/integration/docker/) — multi-stage `uv sync --frozen` pattern

### Secondary (MEDIUM confidence)
- WebSearch results on Compose `profiles:` as the standard optional-service/config mechanism (cross-referenced across multiple 2026-dated guides — khimananda.com, kokil.com.np, dev.to — consistent with each other and with the official Docker "deploy settings ignored outside Swarm except for GPU device reservations" clarification)
- WebSearch results on baking-vs-mounting large model weights in Docker images (theneuralbase.com course content) — general ML-Docker guidance, used here only to justify the "small checkpoints (~280MB) are fine to bake in" recommendation, not treated as authoritative for this repo's specific artifacts

### Tertiary (LOW confidence)
- None — every claim above traces to either a direct repo read or an official Docker/uv documentation source; no unverified single-source WebSearch claims were used for the architecture recommendations.

## Metadata

**Confidence breakdown:**
- Standard stack (Docker/Compose versions, uv Docker pattern, base image choices): HIGH — verified against installed tool versions and official docs
- Architecture (single-container-with-3-venvs, relative-path constraint, GPU profile gating): HIGH — directly derived from reading the actual subprocess-shim code (`fm_client.py`/`geneformer_client.py`) and official Compose GPU docs, not inferred
- Checkpoint/vendored-clone reproducibility risk (Pitfalls 2 and 3): MEDIUM-HIGH — the risk itself is HIGH confidence (documented in this repo's own README files and prior phase planning docs), but whether the automated `gdown` fetch will actually succeed at plan-execution time is inherently unknowable until attempted
- Validation architecture: MEDIUM — the test-type mapping follows this repo's own existing `*_smoke`/`checkpoint:human-verify` conventions closely, but the specific new `GET /api/health` endpoint and smoke-test script are net-new design choices, not verified against an existing pattern in this repo

**Research date:** 2026-09-17
**Valid until:** 30 days (Docker/Compose mechanics are stable; the checkpoint-fetch fragility (Pitfall 2) and the vendored-package patch status (Pitfall 3) should be re-verified if this research is reused after any `geneformer_worker/src/` or `bio_fm_worker/checkpoints/` rebuild on the dev machine)
