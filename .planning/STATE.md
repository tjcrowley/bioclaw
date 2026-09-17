---
gsd_state_version: 1.0
milestone: v1.2
milestone_name: Real Data + Bio FM Integration
status: executing
stopped_at: Completed 13-02-PLAN.md (Geneformer output dataclasses, Ensembl-ID validator, isolated geneformer_worker/ env) — Phase 13 in progress (13-01 also in progress in parallel)
last_updated: "2026-09-17T19:10:00.000Z"
last_activity: 2026-09-17 — Completed 13-02-PLAN.md (Geneformer foundation: dataclasses, validate_ensembl_ids, geneformer_smoke marker, geneformer_worker/ env)
progress:
  total_phases: 14
  completed_phases: 12
  total_plans: 53
  completed_plans: 50
---

# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-09-15)

**Core value:** A Biopunk Labs researcher can ask a plain-language question about a single-cell dataset and get back a QC'd, annotated, interpreted answer without writing a scanpy script by hand.
**Current focus:** v1.2 — Real Data + Bio FM Integration (phases 11-14); Phases 11-12 complete, ready to plan Phase 13.

## Current Position

Milestone: v1.2 Real Data + Bio FM Integration — Phase 13 in progress
Phase: Phase 13 (in progress)
Plan: 13-02 complete (2 of 4 plans; 13-01 in progress/checkpoint in parallel, 13-03/13-04 pending)
Status: 13-02 complete — FM-02 foundation laid (Geneformer dataclasses, Ensembl validator, geneformer_smoke marker, geneformer_worker/ env verified working); 13-03/13-04 build the actual inference pipeline on top of this
Last activity: 2026-09-17 — Completed 13-02-PLAN.md (Geneformer foundation: dataclasses, validate_ensembl_ids, geneformer_smoke marker, geneformer_worker/ env)

```
v1.2 Progress [######----] 62% (2.5/4 phases)
Overall     [###########] 87% (12.5/14 phases)
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
- [Phase 12-02]: _census_fetch_blocking() keeps the entire open_soma with-block + get_anndata call inside one closure passed wholesale to asyncio.to_thread(), per RESEARCH Pattern 2/Pitfall 1 (both must run in the same worker thread)
- [Phase 12-02]: Fixed pre-existing 12-01 test scaffold bugs (SdkMcpTool.handler(...) invocation, asyncio.run() instead of deprecated get_event_loop().run_until_complete()) rather than reverting to the buggy pattern
- [Phase 13-02]: validate_ensembl_ids() resolution order is gene_ids -> feature_id -> Ensembl-shaped var_names -> ValueError; presence/shape check only, real vocabulary match rate deferred to geneformer_worker/run_geneformer_perturb.py (Plan 13-03), which alone can import the geneformer package
- [Phase 13-02]: New Geneformer dataclasses (GeneShift, GeneformerPerturbationCall, GeneformerPerturbationSummary) are additive/parallel to PerturbationCall/PerturbationSummary, not a replacement — Geneformer's ranked-gene-list output is structurally distinct from an expression vector
- [Phase 13-02]: geneformer_worker/.venv requires repinning transformers==4.46 (Geneformer's own requirements.txt pin) immediately after pip install -e, since the unconstrained setup.py resolves an incompatible latest transformers that breaks import geneformer (SpecialTokensMixin removed)

### Critical Pitfalls to Encode in Plans

- **HIST-01**: SQLite WAL mode must be set on the messages table; stored content must be capped at 64 KB per entry to prevent database blowup
- **DATA-01**: Census fetch must run in `asyncio.to_thread()` — TileDB-SOMA is synchronous and blocks the event loop otherwise
- **FM-01**: Verify `scgpt.tasks.embed_data()` API shape in bio_fm_worker before writing the worker script; torch/torchtext ABI mismatch was present in Phase 4 and must be confirmed fixed (ABI confirmed fixed per research guidance)
- **FM-02**: Geneformer requires Ensembl IDs in `adata.var` — gene symbols produce silent zero-length tokens and must be validated before inference runs; Geneformer needs a separate Python 3.10 venv
- **DOCK-01**: docker compose must hard-code `--workers 1`; the in-memory queue registry breaks under multi-worker

### Pending Todos

- Execute 13-03-PLAN.md (geneformer_worker/run_geneformer_perturb.py four-step pipeline CLI + perturbation/geneformer_client.py subprocess shim)
- Execute 13-04-PLAN.md (predict_geneformer() composition + predict_perturbation_geneformer_tool + real end-to-end smoke test checkpoint)
- VCC real dataset download (Phase 5 Task 3) still pending — non-blocking for v1.2

### Blockers/Concerns

- Real scGPT inference: torch/torchtext ABI mismatch was present in Phase 4 `bio_fm_worker/`. Research guidance indicates this is confirmed fixed; Phase 13 plan must verify `scgpt.tasks.embed_data()` API shape before writing worker script.
- VCC real dataset download (Phase 5 Task 3) was deferred due to no GCP billing — still pending, non-blocking for v1.2.

## Session Continuity

Last session: 2026-09-17T19:10:00.000Z
Stopped at: Completed 13-02-PLAN.md (Geneformer output dataclasses, Ensembl-ID validator, isolated geneformer_worker/ env) — Phase 13 in progress (13-01 also in progress in parallel)
Resume file: None
