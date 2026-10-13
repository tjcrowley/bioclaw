---
phase: 14-docker-compose-deployment
verified: 2026-10-13T00:00:00Z
status: partial
score: 7/8 must-haves verified
blocking_gap: DOCK-01 criterion 3 — FM inference never invoked against the Compose stack
---

# Phase 14: Docker Compose Deployment Verification Report

**Phase Goal:** The full stack — backend, frontend, and optional GPU worker for bio FM inference — starts from a clean checkout with a single `docker compose up` command, requiring only environment variable configuration, with the single-worker constraint hard-coded to preserve the in-memory queue registry.
**Verified:** 2026-10-13
**Status:** **partial** — 2 of 3 DOCK-01 criteria fully satisfied; criterion 3 partially satisfied
**Re-verification:** No — initial verification, performed retroactively

> **Why this is retroactive.** Plans 14-01 through 14-05 all executed (2026-09-17 → 2026-09-19) but Phase 14 was never closed out: no 14-05 summary, no verification report, and `STATE.md` frozen at "next action is 14-05". This report verifies the phase against the artifacts and the still-running container rather than against execution notes that were never written. Claims are cited to live evidence; gaps are recorded as gaps.

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | `docker compose up` starts a working backend with only env vars configured | VERIFIED | `bioclaw-backend-1` built 2026-09-19T17:10 PDT from `bioclaw:latest` (15.8GB), started 17:11, **up 3 weeks, healthy**; `GET /api/health` → `{"status":"ok"}` today |
| 2 | The backend's own healthcheck is reliable, not just green once | VERIFIED | **149,791** `GET /api/health` requests in the container log, zero failures, zero restarts since 2026-09-19 |
| 3 | Frontend is served by the same container as the API | VERIFIED | `GET /app/` plus `main.js`, `chat.js`, `api.js`, `sessions.js`, `style.css` all 200 from port 8000 — no separate frontend service |
| 4 | `--workers 1` is structural and cannot be overridden via Compose | VERIFIED | Image `Config.Entrypoint` is `["/app/docker/entrypoint.sh"]`; `docker/entrypoint.sh:8` is `exec /app/.venv/bin/uvicorn ... --workers 1`; resolved `docker compose config` contains **no** `command:`/`entrypoint:` key |
| 5 | GPU support is an override on the same service, not a second service | VERIFIED | `docker compose config --services` → `backend`; merged with `docker-compose.gpu.yml` → still exactly `backend` |
| 6 | All three isolated interpreters and their artifacts are live in the running container | VERIFIED | `/app/bio_fm_worker/.venv` → py 3.9.25 / torch 2.3.0+cu121 / `import scgpt` OK; `/app/geneformer_worker/.venv` → py 3.10.21 / torch 2.14.0+cu130 / `import geneformer` OK; `best_model.pt` 205,385,258 B; `reference.h5ad` 29,893,945 B |
| 7 | State persists across `down`/`up` in a named volume | VERIFIED (via 14-04) | `bioclaw_bioclaw-state` mounted at `/app/state` holds `agent/memory.sqlite` (+WAL), `data/registry.sqlite`, 4 dataset versions, `tool_calls.jsonl`. Cycle itself proven in 14-04 (marker file + mtime survived); not re-run here — restarting a 3-week-healthy container destroys more evidence than it creates |
| 8 | **A researcher can perform the complete workflow against the stack with no local Python** | **PARTIAL** | Upload, analysis (incl. real DE), history, CSV export, script export all confirmed against the container. **FM inference was never invoked.** See below |

**Score:** 7/8 truths verified, 1 partial

### Truth 8 in detail

Reconstructed from `docker logs` and `/app/state/tool_calls.jsonl`. The human checkpoint was genuinely attempted **2026-09-19 17:30–17:33 PDT** and abandoned partway; the export legs were closed separately on 2026-10-13 during this verification.

| Workflow leg | Status | Evidence |
|---|---|---|
| Upload a dataset | VERIFIED | `POST /api/upload` → `demo_query_blood` v1, 12,979,488 B `v1.h5ad` in the volume |
| Run an analysis | VERIFIED | `POST /api/ask` ×2 drove `mcp__bioclaw__analyze_dataset` ×3, one with `run_de=true, de_groupby=leiden, de_group1=2`; produced v2→v4 (20,980,258 B) |
| Session history | VERIFIED | `GET /api/sessions` ×4, `GET /api/sessions/58098d29-…` ×2 |
| Download CSV export | VERIFIED 2026-10-13 | `GET /api/export/csv?dataset_id=demo_query_blood@4` → 200, 342,099 B `application/zip`: `clusters.csv` 2,911 B (real per-barcode leiden), `de_genes.csv` 1,392,986 B (real DE table), `annotations.csv` 70 B (known placeholder, Phase 11 decision) |
| Export scanpy script | VERIFIED-WITH-DEFECT 2026-10-13 | `GET /api/export/script?...` → 200, 1,550 B `text/x-python`; QC/HVG/PCA/neighbors/leiden/umap params and seeds all correct, **but load line is `sc.read_h5ad("")`** — see Open Defects |
| **Call FM inference** | **NOT VERIFIED** | `ToolSearch` loaded `annotate_cell_type` and `predict_perturbation`, but `tool_calls.jsonl` records **no invocation of either**. Truth 6 proves the capability is baked in and importable; it does not prove an inference completes through the agent path inside the container |

### Required Artifacts

| Artifact | Expected | Status | Details |
|---|---|---|---|
| `Dockerfile` | multi-stage, 4 builders + runtime, interpreter relocation | VERIFIED | Builds green in one pass; runtime-stage assertions present (`Dockerfile:209-214`) and load-bearing |
| `.dockerignore` | excludes all three `.venv/`, `data/`, `.git/`, host checkpoints | VERIFIED | Present (618 B) |
| `docker/entrypoint.sh` | owns `--workers 1` | VERIFIED | Line 8; image ENTRYPOINT points at it |
| `docker/geneformer_cuda_fallback.patch` | committed CUDA-fallback artifact | VERIFIED | Present and applied in the image |
| `docker-compose.yml` | single `backend` service, named volume, healthcheck, `${VAR:?}` guards | VERIFIED | Guards confirmed: unset/blank `BIOCLAW_WEB_PASSWORD` refuses to start |
| `docker-compose.gpu.yml` | pure additive override | VERIFIED | Merges nvidia reservation into `backend`; no new service |
| `scripts/docker_compose_smoke_test.sh` | config assertions + build/up/health/down | VERIFIED | Present; passed in 14-04 and at the 14-05 real run |
| `docker/README.md` | build design, fallbacks, known gaps | VERIFIED-WITH-GAP | 227 lines, committed 2026-09-18 — **predates** the 2026-09-19 non-root fixes and omits runtime file ownership. Logged in `deferred-items.md` |
| `README.md` Docker section | CPU-only + GPU invocations | VERIFIED | 21-line section, both commands documented |
| `tests/test_health.py` | fast-tier health coverage, no Docker dep | VERIFIED | Fast tier runs with no Docker daemon dependency |
| `.planning/.../14-05-SUMMARY.md` | plan 05 summary | CREATED 2026-10-13 | Was missing; written retroactively as part of this close-out |

### Requirements Coverage

| Requirement | Criterion | Status | Evidence |
|---|---|---|---|
| DOCK-01 | 1 — clean-checkout `docker compose up`, env vars only, no manual setup | **SATISFIED (with caveat)** | Image built and served from the repo state; three defects (`a78bd1d`, `461d1c5`, `6ec5ff6`) had to be fixed first. **Caveat:** 14-VALIDATION.md's sampling rate called for a build from a *genuinely fresh `git clone` into a scratch directory*; the verified build came from the working repo with `.dockerignore` doing the isolation. Not equivalent, though `.dockerignore` excludes every host artifact the build re-fetches |
| DOCK-01 | 2 — `--workers 1` hard-coded, multi-worker blocked | **SATISFIED** | Truth 4 — flag lives in the image ENTRYPOINT, not in Compose; no Compose override exists to reintroduce it |
| DOCK-01 | 3 — full researcher workflow, zero local Python deps | **PARTIAL** | Truth 8 — 5 of 6 legs verified; FM inference never invoked |

## Open Defects Found During Verification

1. **EXPORT-02: exported script emits an unrunnable source path.** `sc.read_h5ad("")` for uploaded datasets at *every* version. Root cause: `webapp/backend/export_script.py:91-92` degrades `None` to `""`; the live registry shows `source_path` is `None` for derived versions v2–v4 and a since-deleted temp path (`/tmp/tmpnn9pzv6j/…`) for v1. Census-sourced datasets are unaffected, which is why no test caught it. Full writeup and three candidate fixes in `deferred-items.md`.

2. **`docker/README.md` predates the non-root fixes** and does not mention runtime file ownership — the most likely thing to break a rebuild. `deferred-items.md`.

3. **Confirmed first-hand: the 14-03 CUDA-13 waste shipped.** The running container's Geneformer venv carries `torch 2.14.0+cu130` inside an image whose Geneformer worker was deliberately patched to avoid the GPU. Previously measured from build logs; now observed in the deployed artifact. Already logged in `deferred-items.md`.

## Test Baseline

Host suite as of 2026-10-13, unchanged from the Phase 13/14 baseline:

- Fast tier (excluding `test_vcc_eval.py`, `test_vcc_report.py`): **261 passed, 6 skipped** in 67s
- Full suite: **272 passed, 14 failed** — all 14 are the known VCC numba-threadpool isolation bug (all 25 pass in isolation). Root-caused in 13-03, logged in phase 13 `deferred-items.md`, still needs a cleanup plan.

## Verdict

Phase 14 delivers a working, durable single-command deployment. Criteria 1 and 2 are met with strong live evidence; the single-worker constraint is structurally enforced in the right layer.

**Phase 14 is NOT marked complete.** One blocking gap remains: no FM inference has ever been run against the Compose stack. Given that FM inference is the project's core value, and that this phase exists specifically to prove the stack delivers that value, the gap is material rather than cosmetic.

**To close:** invoke `annotate_cell_type` (scGPT) and/or `predict_perturbation` (Geneformer) through the agent against the running container and record the latency and output. Note the realistic cost — the image is amd64 under emulation on this arm64 host, and the host-side `bio_fm_smoke`/`geneformer_smoke` baselines were 11.2s and 15.0s natively, so the containerized run will be substantially slower.
