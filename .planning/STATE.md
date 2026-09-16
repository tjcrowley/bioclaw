---
gsd_state_version: 1.0
milestone: v1.2
milestone_name: Real Data + Bio FM Integration
current_plan: —
status: Defining requirements
stopped_at: —
last_updated: "2026-09-15T00:00:00.000Z"
last_activity: 2026-09-15 — Milestone v1.2 started. v1.1 (phases 7-10, 14 plans) complete and verified.
progress:
  total_phases: 10
  completed_phases: 10
  total_plans: 42
  completed_plans: 42
  percent: 100
---

# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-09-15)

**Core value:** A Biopunk Labs researcher can ask a plain-language question about a single-cell dataset and get back a QC'd, annotated, interpreted answer without writing a scanpy script by hand.
**Current focus:** v1.2 — Real Data + Bio FM Integration (phases 11+); defining requirements.

## Current Position

Milestone: v1.2 Real Data + Bio FM Integration — not started (defining requirements)
Phase: Not started
Plan: —
Status: Defining requirements
Last activity: 2026-09-15 — Milestone v1.2 started

## Performance Metrics

**v1.0 + v1.1 velocity (carried forward):**
- Total plans completed: 42
- Phases completed: 10

## Accumulated Context

### Decisions

See PROJECT.md Key Decisions for all architectural decisions from v1.0 and v1.1.

Key v1.1 decisions relevant to v1.2:
- Webapp is vanilla JS + no build step (preserves single-command run); v1.2 Docker should not require a build step either
- Single-process constraint in streaming.py (in-memory queue registry) — Docker must run one backend replica only, not `--workers`
- scGPT isolated in `bio_fm_worker/.venv` (Python 3.9.6, subprocess shim via `annotation/fm_client.py`) — v1.2 real FM inference uses the same subprocess boundary; no merging into the main venv
- Session history currently not persisted as message transcripts — only dataset associations stored in `SessionMemory`; v1.2 history replay requires adding message storage to `SessionMemory`

### Pending Todos

- Define v1.2 requirements (in progress)
- Create v1.2 roadmap (phases 11+)
- Research: cellxgene-census API, Geneformer inference, session storage patterns, Docker multi-service patterns for FastAPI + GPU worker

### Blockers/Concerns

- Real scGPT inference: torch/torchtext ABI mismatch was present in Phase 4 `bio_fm_worker/`. v1.2 FM research should resolve the correct repair path before planning.
- VCC real dataset download (Phase 5 Task 3) was deferred due to no GCP billing — still pending, non-blocking for v1.2 but worth noting.

## Session Continuity

Last session: 2026-09-15
Stopped at: v1.2 milestone start (updating PROJECT.md / STATE.md)
Resume file: None
