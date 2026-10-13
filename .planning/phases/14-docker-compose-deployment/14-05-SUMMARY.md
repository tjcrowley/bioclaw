---
phase: 14-docker-compose-deployment
plan: 05
subsystem: docker
tags: [docker-compose, docs, non-root, human-verify, export-02]

# Dependency graph
requires:
  - phase: 14
    plan: 03
    provides: full multi-venv image (main 3.13 / scGPT 3.9 / Geneformer 3.10) with baked checkpoints + census reference index
  - phase: 14
    plan: 04
    provides: docker-compose.yml, docker-compose.gpu.yml, scripts/docker_compose_smoke_test.sh
provides:
  - docker/README.md — build design, three-interpreter rationale, Dockerfile traps, manual fallbacks, known gaps
  - README.md "Docker" section — CPU-only and GPU-enabled invocations
  - three non-root runtime fixes without which the image could not start the agent
affects: [14-VERIFICATION]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Container runs as a non-root `bioclaw` user; /app must be world-readable because the relocated interpreters under /opt are root-owned"
    - ".env is never baked into the image — it arrives only via Compose `env_file:` at run time"

key-files:
  created:
    - docker/README.md
  modified:
    - README.md
    - Dockerfile

key-decisions:
  - "Docs were written (commit 63d0bf7) BEFORE the real end-to-end run, so they did not yet describe the three non-root defects the run then exposed."
  - "Ran the container as non-root rather than relaxing the agent's expectations — the agent spawns subprocess interpreters, so the fix belonged in image ownership, not in application code."
  - "Stopped baking .env into the image once the stack was confirmed startable; the credential had been entering the image layer via the broad COPY."

requirements-completed: []

# Metrics
duration: ~3h across two days (docs 2026-09-18, real run + fixes 2026-09-19)
completed: 2026-09-19 (execution) / closed out 2026-10-13 (this summary)
---

# Phase 14 Plan 05: Real Compose run, deployment docs, and the non-root fixes it forced

**The documentation landed first, the real run landed second, and the real run broke the image three times before it served a request. The blocking human checkpoint was started but never finished or signed off — this summary records what was actually verified and what was not.**

> **Written retroactively on 2026-10-13.** Plan 14-05 executed on 2026-09-18/19 but no summary was ever written and `STATE.md` was never advanced past "next action is 14-05". Everything below is reconstructed from git history, the live container, and its persisted state volume — each claim is cited to the artifact that proves it. Where evidence is absent, this summary says so rather than inferring success.

## Task 1 — real smoke test against the full image

The first genuine `docker build` of the complete multi-stage Dockerfile produced an image that **built green and then failed to serve**. Three defects, each fixed in its own commit:

| Commit | Defect | Why it only appeared now |
|---|---|---|
| `a78bd1d` | Container ran as root; the agent would not start | Plans 14-02/14-03 only verified `--target` stages and interpreter imports, never a full agent boot |
| `461d1c5` | `.env` was being baked into the image | Only observable once a real `.env` existed on the host at build time |
| `6ec5ff6` | `/app` unreadable by the new non-root user | Direct consequence of `a78bd1d`; the relocated `/opt/py39`/`/opt/py310` interpreters are root-owned |

The resulting image is the one still running today:

```
bioclaw:latest   183d83c3ae63   15.8GB   created 2026-09-19T17:10 PDT
bioclaw-backend-1   Up (healthy)   started 2026-09-19T17:11 PDT   user=bioclaw
```

`GET /api/health` → `{"status":"ok"}`. The container's own healthcheck has since run **149,791** times without a failure or restart, which is a stronger uptime result than the plan asked for.

**Ordering note worth preserving:** `docker/README.md` was committed 2026-09-18 16:59, *before* the 2026-09-19 run that found these three defects. The docs therefore describe the build as designed, not as it behaved. Their "Known gaps" section does not mention the non-root class of failure.

## Task 2 — docker/README.md and README.md

Both artifacts exist and satisfy the plan's automated verify (`test -f docker/README.md && grep -q "## Docker" README.md`). `docker/README.md` (227 lines) covers the build automation, the three-interpreter rationale, the two Dockerfile traps (interpreter relocation, runtime-vs-builder assertions), the amd64 platform pin, per-artifact manual fallbacks, and known gaps. `README.md` gained a 21-line Docker section with both CPU-only and GPU invocations.

## Task 3 — blocking human-verify checkpoint: STARTED, NOT COMPLETED

The plan's resume signal was `"approved"`. **No sign-off was ever recorded.** The persisted state volume shows the checkpoint was genuinely attempted on **2026-09-19 17:30–17:33 PDT** and then abandoned partway.

What the evidence shows was exercised, from `docker logs` and `/app/state/tool_calls.jsonl`:

| Checkpoint step | Status | Evidence |
|---|---|---|
| Frontend served from the container | DONE | `GET /app/` + `main.js`/`chat.js`/`api.js`/`sessions.js`/`style.css` all 200 |
| Upload a dataset | DONE | `POST /api/upload` → `demo_query_blood` v1 (13MB `v1.h5ad`) in the named volume |
| Run an analysis | DONE | `POST /api/ask` ×2 drove `analyze_dataset` ×3 — including a real DE run (`run_de=true, de_groupby=leiden, de_group1=2`), producing versions v2→v4 (21MB) |
| Session history | DONE | `GET /api/sessions` ×4 and session detail ×2 |
| **Call FM inference** | **NOT DONE** | `ToolSearch` *loaded* `annotate_cell_type` and `predict_perturbation`, but `tool_calls.jsonl` contains **no invocation** of either |
| **Download CSV export** | **NOT DONE on 09-19** | No `/api/export/csv` request in 3 weeks of logs — verified separately on 2026-10-13, see below |
| **Export scanpy script** | **NOT DONE on 09-19** | No `/api/export/script` request — verified separately on 2026-10-13, see below |
| `down` && `up` persistence re-check | **NOT DONE** | Container has never restarted since 2026-09-19 17:11 |

### Gap-closing done during this close-out (2026-10-13)

**Exports — now verified live against the running container.** Both endpoints return 200 with real content:

- `GET /api/export/csv?dataset_id=demo_query_blood@4` → 342,099 B `application/zip` containing `clusters.csv` (2,911 B, real per-barcode leiden assignments), `de_genes.csv` (1,392,986 B, real DE table), `annotations.csv` (70 B — the known placeholder row, per the Phase 11 decision already recorded in STATE.md).
- `GET /api/export/script?dataset_id=demo_query_blood@4` → 1,550 B `text/x-python`, rendering the full QC + analysis chain with seeds.

**This surfaced a real EXPORT-02 defect** — see `deferred-items.md` § "14-05: exported script emits an unrunnable source path". The generated script's load line is `adata = sc.read_h5ad("")`. Root cause confirmed in the live registry: `source_path` is recorded only on v1, and for an *uploaded* dataset that value is a since-deleted temp path (`/tmp/tmpnn9pzv6j/...`); derived versions v2–v4 record `None`. `webapp/backend/export_script.py:91-92` degrades `None` to `""` silently. So EXPORT-02's "self-contained, reproducible" promise is broken for uploaded datasets at every version — not just the one tested. Census-sourced datasets take the other branch and are unaffected.

**FM inference — still not verified through the container.** What *is* confirmed, live in the running container today, is that the capability is correctly baked in:

```
/app/bio_fm_worker/.venv       python 3.9.25   torch 2.3.0+cu121   import scgpt OK
/app/geneformer_worker/.venv   python 3.10.21  torch 2.14.0+cu130  import geneformer OK
/app/bio_fm_worker/checkpoints/scGPT_human/best_model.pt   205,385,258 B
/app/bio_fm_worker/reference/reference.h5ad                 29,893,945 B
```

That is 14-03's assertion re-confirmed in a long-running container rather than a fresh one. It is **not** a substitute for an actual inference call through the agent path, which remains the one genuinely open item of Phase 14. (It also re-confirms the 14-03 deferred finding first-hand: the shipped Geneformer venv carries `torch 2.14.0+cu130`, the unconstrained CUDA-13 resolution, inside an image whose Geneformer worker was patched to avoid the GPU.)

`down`/`up` persistence is treated as satisfied by 14-04's direct evidence (marker file + `memory.sqlite` mtime survived a full cycle) rather than re-run here, since restarting a 3-week-healthy container destroys more evidence than it creates.

## Verification

| Must-have truth | Result |
|---|---|
| `docker compose up` from clean checkout + env vars only, no manual setup | **PASS** — after `a78bd1d`/`461d1c5`/`6ec5ff6`; image built and healthy since 2026-09-19, 149,791 clean healthchecks |
| Full researcher workflow with zero local Python deps | **PARTIAL** — upload, analysis (incl. DE), history, CSV export, script export all confirmed against the container; **FM inference never invoked** |
| Manual fallback documented for any failed Wave 3 fetch | **PASS** — `docker/README.md`; no fetch actually failed (checkpoint is 205MB of real weights) |

Host test suite today, unchanged baseline: **fast tier 261 passed / 6 skipped**; full suite **14 failed / 272 passed**, all 14 the pre-existing VCC numba-threadpool isolation bug. This plan touches no Python.

## Notes for phase closure

1. Phase 14 should **not** be recorded as fully verified. DOCK-01 criteria 1 and 2 pass; criterion 3 is partial on FM inference alone.
2. `docker/README.md` predates the non-root fixes and should gain a short "runtime ownership" note.
3. The EXPORT-02 empty-source-path defect is a Phase 12 regression that only a real containerized export could have surfaced — it is the concrete argument for why this checkpoint was marked blocking.
