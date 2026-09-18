---
phase: 14
slug: docker-compose-deployment
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-09-18
---

# Phase 14 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 8.x (existing project convention — `pyproject.toml` `[tool.pytest.ini_options]`), extended with a new `docker_smoke` marker, plus a plain shell smoke-test script for the actual `docker compose up`/`down` cycle (pytest cannot practically drive a real multi-minute Docker build inside the fast/CI tier) |
| **Config file** | `pyproject.toml` (existing `markers` list — add `docker_smoke: requires a built Docker image / running Docker daemon, excluded from fast/CI runs`, mirroring the existing `bio_fm_smoke`/`geneformer_smoke`/`census_data` pattern) |
| **Quick run command** | `uv run pytest -q` (existing fast tier — must NOT gain any new dependency on Docker being installed/running) |
| **Full suite command** | `uv run pytest tests/ -q` plus a separate, explicitly-invoked `scripts/docker_compose_smoke_test.sh` (new) that runs `docker compose build && docker compose up -d && curl` against the health endpoint `&& docker compose down` |
| **Estimated runtime** | Fast tier ~unchanged (seconds); `docker_compose_smoke_test.sh` ~5-15 min (image build + container start) |

---

## Sampling Rate

- **After every task commit:** Run `uv run pytest -q` (fast tier — no Docker daemon dependency)
- **After every plan wave:** Run `scripts/docker_compose_smoke_test.sh` (build + up + health-check + down) — requires Docker Engine locally, run manually/on-demand, not in the fast tier
- **Before `/gsd:verify-work`:** Full `docker compose up` from a genuinely clean checkout (fresh `git clone` into a scratch directory, no host-cached `.venv`/checkpoints), followed by the manual end-to-end researcher workflow (criterion 3) below
- **Max feedback latency:** ~15 minutes (Docker image build is the dominant cost; not sub-second like the existing fast tier, but this is the correct tier for infra work — pytest fast tier stays sub-second for all code-level tasks)

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 14-01-01 | 01 | 0 | DOCK-01 (criterion 1) | unit | `uv run pytest tests/test_health.py -q` | ❌ W0 | ⬜ pending |
| 14-0X-0X | TBD | TBD | DOCK-01 (criterion 1) | smoke (shell) | `scripts/docker_compose_smoke_test.sh` | ❌ W0 | ⬜ pending |
| 14-0X-0X | TBD | TBD | DOCK-01 (criterion 2) | smoke (shell) | `docker compose config \| grep -- '--workers 1'` | ❌ W0 | ⬜ pending |
| 14-0X-0X | TBD | TBD | DOCK-01 (criterion 3) | manual (`checkpoint:human-verify`) | — (real FM inference against compose stack, minutes-to-hours per existing `bio_fm_smoke`/`geneformer_smoke` precedent) | n/a | ⬜ pending |

*Exact task IDs finalized by the planner; this map records the requirement → test-type contract the plans must satisfy.*

---

## Wave 0 Requirements

- [ ] `GET /api/health` endpoint in `webapp/backend/main.py` — does not exist today; needed for both Compose `healthcheck:` and the smoke-test script. Must be **unauthenticated** (container orchestration health probes should not need `BIOCLAW_WEB_PASSWORD`) and cheap (no DB/FM calls).
- [ ] `tests/test_health.py` — stub covering the new health endpoint (fast tier, no Docker dependency)
- [ ] `scripts/docker_compose_smoke_test.sh` — new shell script driving `docker compose build && up -d && curl health && down`
- [ ] `docker/geneformer_cuda_fallback.patch` — new committed artifact capturing the currently-untracked CUDA-fallback edit described in `geneformer_worker/README.md`'s "Real-run fixes" item 2 (author by diffing the current local, patched `geneformer_worker/src/` against a fresh unpatched clone, or by hand-writing the ~15-site edit as a patch file)
- [ ] `docker_smoke` pytest marker registration in `pyproject.toml`'s `[tool.pytest.ini_options] markers` list, mirroring the existing `bio_fm_smoke`/`geneformer_smoke`/`census_data`/`vcc_data` entries
- [ ] `.dockerignore` — does not exist yet; must exclude all three `.venv/` directories, `geneformer_worker/src/`, `data/`, `agent/logs/`, `agent/memory.sqlite*`, `tool_calls.jsonl`, `.git/`, and any local `bio_fm_worker/checkpoints/`/`bio_fm_worker/reference/` content the Dockerfile intends to fetch fresh rather than copy from the host

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Full researcher workflow (upload or census-fetch → analysis → FM inference → CSV export → script export) against the running compose stack, no local Python deps | DOCK-01 (criterion 3) | Real scGPT/Geneformer FM inference takes minutes-to-hours per this repo's own documented `bio_fm_smoke`/`geneformer_smoke` real-checkpoint latencies — not automatable inside a fast smoke test. Matches existing precedent (`checkpoint:human-verify` gates already used in Phase 4/13 for the same underlying FM calls). | `docker compose up`, open the frontend, run the full workflow end to end, confirm each step (upload/census-fetch, analysis, FM inference, CSV export, script export) succeeds with no local Python installed. |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 15 min (Docker-tier), < 1s (fast pytest tier)
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
