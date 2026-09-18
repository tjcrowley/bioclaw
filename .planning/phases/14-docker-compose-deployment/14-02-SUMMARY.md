---
phase: 14-docker-compose-deployment
plan: 02
subsystem: docker
tags: [docker, dockerfile, entrypoint, single-worker, health-check, docker-prep]

# Dependency graph
requires:
  - phase: 14
    plan: 01
    provides: unauthenticated GET /api/health probe; BIOCLAW_MEMORY_DB / BIOCLAW_LOG_PATH env overrides
  - phase: 07
    provides: FastAPI app (webapp/backend/main.py) + /app StaticFiles frontend mount
provides:
  - Buildable single-service image `bioclaw:test-main` (multi-stage, python:3.13-slim, WORKDIR /app)
  - docker/entrypoint.sh — fixed `uvicorn ... --workers 1`, no "$@" forwarding, non-overridable
  - .dockerignore — excludes all three venvs, gitignored FM artifacts, dev clutter
  - .env.example — documents ANTHROPIC_API_KEY / BIOCLAW_WEB_PASSWORD
  - Runtime ENV defaults relocating all three state paths under /app/state
affects: [14-03-fm-worker-stages, 14-04-compose, 14-05-docs]

# Tech tracking
tech-stack:
  added:
    - "docker (build target python:3.13-slim; verified against Docker Engine 29.3.1)"
  patterns:
    - "Single-worker constraint enforced by the image's own ENTRYPOINT script with no argument forwarding, so neither `docker run` trailing args nor a compose `command:` can reintroduce multi-worker"
    - "uv two-pass install: `uv sync --no-install-project` on lockfile only (cacheable layer), then `COPY . .` + full `uv sync`"
    - "State paths relocated via ENV to a single /app/state subtree, so 14-04 needs exactly one volume mount"

key-files:
  created:
    - Dockerfile
    - .dockerignore
    - docker/entrypoint.sh
    - .env.example
  modified: []

key-decisions:
  - "Verified the single-worker guarantee by actually running `docker run ... --workers 8` and reading /proc/1/cmdline, rather than the plan's weaker `docker inspect` entrypoint-shape check — PID 1 was `uvicorn ... --workers 1`, and logs showed `Started server process [1]` with no parent-process line"
  - "No mkdir needed for the ENV state paths: SessionMemory.__init__ already does path.parent.mkdir(parents=True, exist_ok=True) (agent/memory.py:64), confirmed live — /app/state/agent/memory.sqlite was created on first boot"
  - "Plan's Task 2 verify command `docker run --rm bioclaw:test-main ls /app/.venv/bin/uvicorn` is unrunnable as written — the ENTRYPOINT ignores args by design, so it starts uvicorn instead of running ls. Used `--entrypoint ls` instead. The plan bug is itself evidence the constraint works."

requirements-completed: []

# Metrics
duration: ~25min
completed: 2026-09-17
---

# Phase 14 Plan 02: Base Docker image + non-overridable single-worker entrypoint

**A multi-stage Dockerfile builds the root uv venv into a python:3.13-slim runtime at WORKDIR /app, serving both `/api/*` and the `/app` frontend on port 8000, with `--workers 1` baked into the image's own ENTRYPOINT where no compose override can reach it.**

Deliberately excludes the scGPT/Geneformer builder stages — Plan 14-03 inserts those between `main-builder` and `runtime`. FM-backed tool calls will fail inside the container until then; that is expected and out of scope here.

## Verification

All run live against Docker Engine 29.3.1 (Docker Desktop had to be started first — the daemon was not running):

- `docker build -t bioclaw:test-main .` → succeeded from cold cache in ~5.5min (the `uv sync` layer dominates at 313s). Image 1.61GB before any FM checkpoints.
- Container boot → `GET /api/health` returned `HTTP 200 {"status":"ok"}` ~12s after start; `GET /app/` returned `HTTP 200`, confirming the WORKDIR/relative-path contract holds for the StaticFiles mount.
- **Single-worker guarantee, hard-proven:** `docker run ... bioclaw:test-main --workers 8` → `/proc/1/cmdline` was `/app/.venv/bin/python /app/.venv/bin/uvicorn webapp.backend.main:app --host 0.0.0.0 --port 8000 --workers 1`. Health still 200. `docker inspect` entrypoint is exactly `[/app/docker/entrypoint.sh]`.
- State relocation: `/app/state/agent/memory.sqlite` (20KB) auto-created on first boot from `BIOCLAW_MEMORY_DB`.
- Fast pytest tier → 255 passed, 14 failed — identical to the pre-14-02 baseline; all 14 are the pre-existing `test_vcc_eval.py`/`test_vcc_report.py` numba threadpool-leak isolation bug from Phase 13 deferred-items. This plan touches no Python.

## Notes for 14-03 / 14-04

- `.dockerignore` excludes `bio_fm_worker/checkpoints/`, `bio_fm_worker/reference/`, and `geneformer_worker/src/` — 14-03's builder stages must fetch these fresh in-build; they cannot rely on this dev checkout's pre-fetched copies.
- 1.61GB base means the FM checkpoint layers in 14-03 will dominate final image size; worth watching.
- All mutable state is under `/app/state`, so 14-04 needs one volume mount, not three.
