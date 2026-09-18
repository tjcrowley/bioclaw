---
phase: 14-docker-compose-deployment
plan: 01
subsystem: webapp-backend
tags: [health-check, env-config, persistence, geneformer, patch, docker-prep]

# Dependency graph
requires:
  - phase: 07
    provides: FastAPI app (webapp/backend/main.py), deps.get_ask_question / get_session_memory dependency providers, password auth
  - phase: 13
    provides: geneformer_worker/src nested Geneformer clone with local device="cuda" -> CPU fallback edits
provides:
  - Unauthenticated GET /api/health returning 200 with no DB/FM calls (container health probe)
  - BIOCLAW_MEMORY_DB env var overrides the SessionMemory SQLite path (default agent/memory.sqlite)
  - BIOCLAW_LOG_PATH env var overrides the tool-call audit JSONL path (default tool_calls.jsonl)
  - docker/geneformer_cuda_fallback.patch — re-appliable diff of the ~15 CUDA-fallback edits in geneformer_worker/src/
  - docker_smoke pytest marker registered
affects: [14-02-dockerfile, 14-03-compose, 14-04-smoke-test]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Persistence paths read via os.environ.get(VAR, default) at singleton/call construction so a Docker volume can relocate them without code change"
    - "Machine-local edits to a gitignored vendored clone captured as a committed git diff artifact, re-applied via `git apply` in the Docker builder stage"

key-files:
  created:
    - docker/geneformer_cuda_fallback.patch
  modified:
    - webapp/backend/main.py
    - webapp/backend/deps.py
    - tests/test_webapp_backend.py
    - tests/test_health.py
    - pyproject.toml

key-decisions:
  - "Defaults preserved (agent/memory.sqlite, tool_calls.jsonl) so non-Docker runs are unchanged; env vars are additive overrides"
  - "The reload-based memory-db env test restores deps.get_ask_question / get_session_memory to their original objects in finally, so importlib.reload(deps) no longer breaks app.dependency_overrides identity for later tests (test-isolation fix)"
  - "Patch generated with `git -C geneformer_worker/src diff`; verified 3 diff --git headers and clean reverse+forward apply"

requirements-completed: ["DOCK-01"]

# Metrics
duration: interrupted-then-resumed
completed: 2026-09-17
---

# Phase 14 Plan 01: Docker-prep backend changes

**Added an unauthenticated `GET /api/health` probe, env-var overrides for the two unconfigurable persistence paths (`BIOCLAW_MEMORY_DB`, `BIOCLAW_LOG_PATH`), and captured the machine-local Geneformer CUDA-fallback edits as a committed, re-appliable patch — all Docker-independent and verified by the fast pytest tier.**

## Execution note
The scheduled `bioclaw-14-01-kickoff` automation ran headless and timed out mid-execution (documented GSD interactive-prompt stall). It had committed the health endpoint (aff4a33) and left the env-var work in the tree with one failing test. Resumed interactively 2026-09-17 ~22:40 PT: root-caused the failing `test_ask_uses_env_configured_log_path` to the reload-based sibling test poisoning `app.dependency_overrides` identity, fixed it, generated the CUDA patch, and committed the remainder (4490085, b843a01).

## Verification
- `pytest tests/test_webapp_backend.py tests/test_health.py` → 29 passed
- Full fast tier → 255 passed, 14 failed (all in test_vcc_eval.py / test_vcc_report.py — the pre-existing numba threadpool-leak isolation bug documented in Phase 13 deferred-items, unrelated to this plan)
- Patch: 3 `diff --git` headers; `git apply --check -R` and forward `--check` on a stashed pristine tree both pass
