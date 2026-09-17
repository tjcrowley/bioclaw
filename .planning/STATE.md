---
gsd_state_version: 1.0
milestone: v1.2
milestone_name: Real Data + Bio FM Integration
status: completed
stopped_at: Completed 12-03-PLAN.md (Script export endpoint + frontend wiring)
last_updated: "2026-09-17T14:06:00.562Z"
last_activity: 2026-09-17 — Completed 12-03-PLAN.md (Script export endpoint + frontend wiring)
progress:
  total_phases: 14
  completed_phases: 12
  total_plans: 49
  completed_plans: 49
---

# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-09-15)

**Core value:** A Biopunk Labs researcher can ask a plain-language question about a single-cell dataset and get back a QC'd, annotated, interpreted answer without writing a scanpy script by hand.
**Current focus:** v1.2 — Real Data + Bio FM Integration (phases 11-14); roadmap defined, ready to plan Phase 11.

## Current Position

Milestone: v1.2 Real Data + Bio FM Integration — Phase 12 complete
Phase: Phase 13 (next)
Plan: —
Status: Phase 12 complete (DATA-01 + EXPORT-02 satisfied) — ready to plan Phase 13
Last activity: 2026-09-17 — Completed 12-03-PLAN.md (Script export endpoint + frontend wiring)

```
v1.2 Progress [#####-----] 50% (2/4 phases)
Overall     [###########] 86% (12/14 phases)
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
- [Phase 11-02]: Use ingest.loaders.load() (not scanpy directly) to build tiny_h5ad_file fixture — guarantees AnnData structure matches production ingest pipeline output
- [Phase 11-quick-wins-history-replay-h5ad-upload-csv-export]: WAL mode set in _connect() — idempotent PRAGMA applies to every SessionMemory connection automatically
- [Phase 11-quick-wins-history-replay-h5ad-upload-csv-export]: Content cap at 64 KB character count (not bytes); touch() called before add_message() in ask() for ask-only sessions; citations omitted from history replay
- [Phase 11]: annotation/pipeline.py annotate() does not persist results back to store; annotations.csv uses placeholder row for current datasets
- [Phase 11]: Used anchor-click pattern for CSV download so session cookie is sent automatically on browser navigation
- [Phase 11-quick-wins-history-replay-h5ad-upload-csv-export]: annotation/pipeline.py annotate() does not persist results back to store; annotations.csv uses placeholder row for current datasets
- [Phase 11-quick-wins-history-replay-h5ad-upload-csv-export]: Used anchor-click pattern for CSV download so session cookie is sent automatically on browser navigation
- [Phase 12-01]: ingest_from_anndata() keeps census AnnData in memory (no write+read round-trip), mirrors ingest_10x() exactly minus loaders.load()
- [Phase 12-01]: format_census_source() is census-source-agnostic (no cellxgene_census import) — pure string function for provenance round-trip in EXPORT-02
- [Phase 12-01]: census_data marker + CENSUS_DATA env-var double gate on smoke test prevents accidental CI network calls
- [Phase 12-03]: webapp/backend/export_script.py verified against spec rather than rewritten (found pre-existing from interrupted run, matched exactly)
- [Phase 12-03]: Export Script button reuses _showDownloadBtn/_hideDownloadBtn helpers so CSV and Script export buttons always show/hide together

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

Last session: 2026-09-17T14:05:40.086Z
Stopped at: Completed 12-03-PLAN.md (Script export endpoint + frontend wiring)
Resume file: None
