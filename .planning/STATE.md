---
gsd_state_version: 1.0
milestone: v1.2
milestone_name: Real Data + Bio FM Integration
current_plan: —
status: Roadmap defined — ready for Phase 11 planning
stopped_at: —
last_updated: "2026-09-16T00:00:00.000Z"
last_activity: 2026-09-16 — v1.2 roadmap created (Phases 11-14, 8 requirements, 100% coverage)
progress:
  total_phases: 14
  completed_phases: 10
  total_plans: 42
  completed_plans: 42
  percent: 71
---

# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-09-15)

**Core value:** A Biopunk Labs researcher can ask a plain-language question about a single-cell dataset and get back a QC'd, annotated, interpreted answer without writing a scanpy script by hand.
**Current focus:** v1.2 — Real Data + Bio FM Integration (phases 11-14); roadmap defined, ready to plan Phase 11.

## Current Position

Milestone: v1.2 Real Data + Bio FM Integration — roadmap defined, not started
Phase: Phase 11 (next)
Plan: —
Status: Roadmap defined — ready for Phase 11 planning
Last activity: 2026-09-16 — v1.2 roadmap created (4 phases, 8 requirements, 100% coverage)

```
v1.2 Progress [----------] 0% (0/4 phases)
Overall     [##########] 71% (10/14 phases)
```

## Performance Metrics

**v1.0 + v1.1 velocity (carried forward):**
- Total plans completed: 42
- Phases completed: 10

**v1.2 targets:**
- Phases: 4 (11-14)
- Requirements: 8

## Accumulated Context

### Decisions

See PROJECT.md Key Decisions for all architectural decisions from v1.0 and v1.1.

Key v1.1 decisions relevant to v1.2:
- Webapp is vanilla JS + no build step (preserves single-command run); v1.2 Docker should not require a build step either
- Single-process constraint in streaming.py (in-memory queue registry) — Docker must run one backend replica only; `--workers 1` must be hard-coded in docker compose
- scGPT isolated in `bio_fm_worker/.venv` (Python 3.9.6, subprocess shim via `annotation/fm_client.py`) — v1.2 real FM inference uses the same subprocess boundary; no merging into the main venv
- Session history currently not persisted as message transcripts — only dataset associations stored in `SessionMemory`; Phase 11 history replay requires adding a messages table to `SessionMemory` with SQLite WAL mode and 64 KB per-entry content cap

Key v1.2 roadmap decisions:
- Phase 11 (HIST-01, DATA-02, EXPORT-01) comes first as all three are independent of FM and network — immediate value at low risk
- Phase 12 (DATA-01, EXPORT-02) requires network (census) and DATA-01's messages table exists after HIST-01
- Phase 13 sequences FM-01 (scGPT) before FM-02 (Geneformer) so the validated subprocess pattern is reused for Geneformer's more complex four-step pipeline
- Phase 14 (DOCK-01) is last — Docker depends on all features being stable

### Critical Pitfalls to Encode in Plans

- **HIST-01**: SQLite WAL mode must be set on the messages table; stored content must be capped at 64 KB per entry to prevent database blowup
- **DATA-01**: Census fetch must run in `asyncio.to_thread()` — TileDB-SOMA is synchronous and blocks the event loop otherwise
- **FM-01**: Verify `scgpt.tasks.embed_data()` API shape in bio_fm_worker before writing the worker script; torch/torchtext ABI mismatch was present in Phase 4 and must be confirmed fixed (ABI confirmed fixed per research guidance)
- **FM-02**: Geneformer requires Ensembl IDs in `adata.var` — gene symbols produce silent zero-length tokens and must be validated before inference runs; Geneformer needs a separate Python 3.10 venv
- **DOCK-01**: docker compose must hard-code `--workers 1`; the in-memory queue registry breaks under multi-worker

### Pending Todos

- Plan Phase 11 (`/gsd:plan-phase 11`)
- VCC real dataset download (Phase 5 Task 3) still pending — non-blocking for v1.2

### Blockers/Concerns

- Real scGPT inference: torch/torchtext ABI mismatch was present in Phase 4 `bio_fm_worker/`. Research guidance indicates this is confirmed fixed; Phase 13 plan must verify `scgpt.tasks.embed_data()` API shape before writing worker script.
- VCC real dataset download (Phase 5 Task 3) was deferred due to no GCP billing — still pending, non-blocking for v1.2.

## Session Continuity

Last session: 2026-09-16
Stopped at: v1.2 roadmap creation complete
Resume file: None
