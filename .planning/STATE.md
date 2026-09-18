---
gsd_state_version: 1.0
milestone: v1.2
milestone_name: Real Data + Bio FM Integration
status: completed
stopped_at: Completed Phase 13; Phase 14 researched and planned, not executed
last_updated: "2026-09-18T03:50:00.000Z"
last_activity: 2026-09-17 — Completed Phase 13 (13-04-PLAN.md wired predict_perturbation_geneformer_tool into the agent server with a real end-to-end smoke test); 13-VERIFICATION.md passed 8/8; Phase 14 research + validation strategy + plans 14-01..14-05 drafted
progress:
  total_phases: 14
  completed_phases: 13
  total_plans: 53
  completed_plans: 53
---

# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-09-15)

**Core value:** A Biopunk Labs researcher can ask a plain-language question about a single-cell dataset and get back a QC'd, annotated, interpreted answer without writing a scanpy script by hand.
**Current focus:** v1.2 — Real Data + Bio FM Integration (phases 11-14); Phases 11-13 complete, Phase 14 planned and ready to execute.

## Current Position

Milestone: v1.2 Real Data + Bio FM Integration — Phase 14 in progress (waves 1-2 done)
Phase: Phase 14 Docker Compose deployment — 3 of 5 plans complete
Plan: Next action is 14-03-PLAN.md (the expensive one: bakes scGPT + Geneformer venvs/checkpoints and the census reference index into the image), then 14-05 docs
Status: 14-01 complete (unauthenticated GET /api/health, BIOCLAW_MEMORY_DB / BIOCLAW_LOG_PATH env overrides, committed Geneformer CUDA-fallback patch artifact). 14-02 complete (multi-stage Dockerfile → python:3.13-slim at WORKDIR /app, .dockerignore, .env.example, docker/entrypoint.sh). Base image builds and serves: GET /api/health → 200 and GET /app/ → 200 inside the container. Single-worker constraint hard-proven — `docker run ... --workers 8` still yields /proc/1/cmdline ending in `--workers 1`. Remaining: 14-03 bakes the scGPT + Geneformer venvs/checkpoints and the census reference index into the image, 14-04 adds docker-compose.yml + GPU overlay + smoke script, 14-05 docs (autonomous: false, needs human review).
Last activity: 2026-09-17 — Completed 14-02 interactively (base Docker image + non-overridable single-worker ENTRYPOINT verified live against Docker Engine 29.3.1).

```
v1.2 Progress [########--] 85% (3.4/4 phases)
Overall     [#########-] 96% (13.4/14 phases)
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
- [Phase 13-01]: _match_and_aggregate()'s confidence changed from top-1 cosine similarity to a k-NN (k=15) vote fraction — count of majority-label neighbors among each query cell's k nearest reference neighbors, divided by k; k is clamped to min(k, reference embedding count); no change to AnnotationCall schema or main()'s call site since k has a default
- [Phase 13-03]: run_geneformer_perturb.py's TranscriptomeTokenizer call uses model_input_size=2048 (not Pattern 3's 4096) — live inspect.getsource() on the installed geneformer package confirmed model_version="V1" unconditionally overrides model_input_size to 2048 and special_token to False inside __init__, making 4096/True the V2-only defaults
- [Phase 13-03]: ranked_genes built from InSilicoPerturberStats.get_stats()'s Affected_gene_name/Affected_Ensembl_ID columns (not Gene_name/Ensembl_ID, which describe the single perturbed gene and are constant across every row) — real column names verified via inspect.getsource() on isp_aggregate_gene_shifts, a drift from 13-RESEARCH.md Pattern 3's documented column list
- [Phase 13-03]: call_geneformer_perturb() timeout defaults to 7200s (2h), double call_scgpt_annotate()'s 3600s, per Pitfall 3's four-step-pipeline wall-clock warning; query h5ad is symlinked into a dedicated work_dir/data_input/ directory before tokenize_data() since TranscriptomeTokenizer.tokenize_files() globs an entire directory rather than accepting a single file path

### Critical Pitfalls to Encode in Plans

- **HIST-01**: SQLite WAL mode must be set on the messages table; stored content must be capped at 64 KB per entry to prevent database blowup
- **DATA-01**: Census fetch must run in `asyncio.to_thread()` — TileDB-SOMA is synchronous and blocks the event loop otherwise
- **FM-01**: RESOLVED (Phase 13-01) — `scgpt.tasks.embed_data()` API shape verified with no drift, torch/torchtext ABI confirmed fixed, k-NN vote-fraction confidence verified end-to-end against the real checkpoint
- **FM-02**: Geneformer requires Ensembl IDs in `adata.var` — gene symbols produce silent zero-length tokens and must be validated before inference runs; Geneformer needs a separate Python 3.10 venv. Pipeline worker built (Phase 13-03): `geneformer_worker/run_geneformer_perturb.py` computes the real vocabulary match_rate independently (hard-fails below 50%) and ranks genes by `Affected_gene_name`/`Affected_Ensembl_ID`/`Cosine_sim_mean` from `InSilicoPerturberStats`, not the `Gene_name`/`Ensembl_ID` columns Pattern 3 originally documented. RESOLVED (Phase 13-04) — run end-to-end against the real V1-10M checkpoint, 15.0s latency, non-empty `ranked_genes` with non-zero cosine shifts.
- **DOCK-01**: docker compose must hard-code `--workers 1`; the in-memory queue registry breaks under multi-worker. The image's own ENTRYPOINT must own this flag (Plan 14-02) so a compose `command:`/`entrypoint:` override cannot silently reintroduce multi-worker.

### Pending Todos

- ~~Execute 14-01-PLAN.md~~ DONE 2026-09-17 (commits 849a7e7/aff4a33/4490085/b843a01; see 14-01-SUMMARY.md). Kickoff automation timed out headless; finished interactively.
- ~~Execute 14-02-PLAN.md~~ DONE 2026-09-17 (see 14-02-SUMMARY.md). Base image builds and serves; `--workers 1` proven non-overridable.
- ~~Execute 14-04-PLAN.md~~ DONE 2026-09-18 (see 14-04-SUMMARY.md). Compose stack up/health/down verified, GPU overlay merges onto the same service, state persists across down/up.
- ~~**SECURITY follow-up (from 14-04):** blank `BIOCLAW_WEB_PASSWORD` authenticated anyone sending an empty `session` cookie~~ FIXED 2026-09-18. `_valid()` now guards `if not expected or not password:`; `tests/test_auth_blank_password.py` (15 tests) covers both HTTP and WebSocket entry points. Note the vector first reported in 14-04-SUMMARY/commit 9920b5a (`?password=`) was wrong — that path collapses to `None` and was already rejected; the real one was `Cookie: session=`. See phase 14 `deferred-items.md`.
- Do NOT run GSD plan execution as a headless automation — plan execution has interactive gates and the 14-01 kickoff stalled on one mid-run, leaving a half-finished tree. Run plans interactively.
- 14-03 will need real network + disk: it fetches the scGPT whole-human checkpoint, clones Geneformer, and builds a census-derived reference index inside the image build. Base image is already 1.61GB before any of that.
- Full-suite test-isolation bug: 14 failures in `tests/test_vcc_eval.py` / `tests/test_vcc_report.py`, all 25 pass in isolation. Root cause isolated during 13-03 — leaked global thread-count state makes `pdex` size numba's threadpool at 0, so `cell_eval.MetricsEvaluator.__init__` raises `ValueError: The number of threads must be between 1 and 10`. See phase 13 `deferred-items.md`; needs a cleanup plan.
- VCC real dataset download (Phase 5 Task 3) still pending — non-blocking for v1.2

### Blockers/Concerns

- VCC real dataset download (Phase 5 Task 3) was deferred due to no GCP billing — still pending, non-blocking for v1.2.

## Session Continuity

Last session: 2026-09-18T03:50:00.000Z
Stopped at: Phase 14 Plan 01 executed & committed (health probe + persistence env vars + Geneformer CUDA-fallback patch); fast tier green except the pre-existing 14 VCC isolation failures
Resume file: .planning/phases/14-docker-compose-deployment/14-02-PLAN.md
