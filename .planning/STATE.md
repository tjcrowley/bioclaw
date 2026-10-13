---
gsd_state_version: 1.0
milestone: v1.2
milestone_name: Real Data + Bio FM Integration
status: in_progress
stopped_at: Phase 14 executed in full; 14-VERIFICATION.md is PARTIAL (7/8) — one blocking gap: FM inference never invoked against the Compose stack
last_updated: "2026-10-13T00:00:00.000Z"
last_activity: 2026-10-13 — Phase 14 close-out. Wrote the missing 14-05-SUMMARY.md and 14-VERIFICATION.md retroactively, pushed the three unpushed docker fixes (9d9f92e..6ec5ff6), verified both export endpoints live against the running container (which surfaced an EXPORT-02 defect), and re-confirmed all three interpreters inside the long-running container.
progress:
  total_phases: 14
  completed_phases: 13
  total_plans: 54
  completed_plans: 54
---

# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-09-15)

**Core value:** A Biopunk Labs researcher can ask a plain-language question about a single-cell dataset and get back a QC'd, annotated, interpreted answer without writing a scanpy script by hand.
**Current focus:** v1.2 — Real Data + Bio FM Integration (phases 11-14); Phases 11-13 complete, Phase 14 all 5 plans executed but verification is PARTIAL with one blocking gap.

## Current Position

Milestone: v1.2 Real Data + Bio FM Integration — Phase 14 executed, verification partial
Phase: Phase 14 Docker Compose deployment — **5 of 5 plans complete**, `14-VERIFICATION.md` status `partial` (7/8 truths)
Plan: No plan pending. **Next action is the one open gap:** invoke `annotate_cell_type` (scGPT) and/or `predict_perturbation` (Geneformer) through the agent against the running Compose container and record latency + output. That is all DOCK-01 criterion 3 still needs.
Status: 14-01 complete (unauthenticated GET /api/health, BIOCLAW_MEMORY_DB / BIOCLAW_LOG_PATH env overrides, committed Geneformer CUDA-fallback patch artifact). 14-02 complete (multi-stage Dockerfile → python:3.13-slim at WORKDIR /app, .dockerignore, .env.example, docker/entrypoint.sh). 14-03 complete (all three interpreters verified in fresh containers; best_model.pt 205MB of real weights; CUDA-fallback patch applied). 14-04 complete (docker-compose.yml + GPU overlay + smoke script). **14-05 complete 2026-09-19** — docs committed (63d0bf7), then the first real end-to-end run exposed three startup defects fixed in a78bd1d / 461d1c5 / 6ec5ff6 (non-root user, .env baked into image, /app unreadable). The resulting image has been **up and healthy for 3 weeks** (149,791 clean healthchecks).
Last activity: 2026-10-13 — Phase 14 close-out, performed retroactively because 14-05 left no summary and STATE was frozen at "next action is 14-05". Pushed the three orphaned docker fixes. Wrote 14-05-SUMMARY.md and 14-VERIFICATION.md from live container evidence. Closed the CSV-export and script-export legs of the 14-05 human checkpoint by exercising both endpoints against the running container — which surfaced a genuine EXPORT-02 defect (`sc.read_h5ad("")`). Re-confirmed all three interpreters importable inside the long-running container. FM inference against the stack remains the single unverified leg.

```
v1.2 Progress [#########-] 94% (3.75/4 phases)
Overall     [#########-] 98% (13.75/14 phases)
```

## Phase 14 open gap (blocks marking v1.2 complete)

`14-VERIFICATION.md` is `status: partial`, 7/8 truths. DOCK-01 criteria 1 and 2 are
fully satisfied with live evidence. Criterion 3 is 5 of 6 legs verified — upload,
analysis (incl. real DE), session history, CSV export, and script export all
confirmed against the container. **FM inference was never invoked against the
Compose stack.** `tool_calls.jsonl` shows `ToolSearch` loaded `annotate_cell_type`
and `predict_perturbation` on 2026-09-19 but neither was called.

The capability is proven baked in (scGPT py3.9.25/torch 2.3.0+cu121 and Geneformer
py3.10.21/torch 2.14.0+cu130 both import cleanly in the running container;
checkpoint and reference index present at the hardcoded paths) — but importable is
not the same as an inference completing through the agent path. Expect it to be
slow: the image is amd64 under emulation on this arm64 host, against native
baselines of 11.2s (scGPT) and 15.0s (Geneformer).

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
- ~~Execute 14-05-PLAN.md~~ DONE 2026-09-19 (see 14-05-SUMMARY.md, written retroactively 2026-10-13). Docs landed 2026-09-18; the real run on 2026-09-19 exposed and fixed three startup defects. The blocking human checkpoint was started but never signed off — FM inference leg still open.
- **OPEN (closes Phase 14): run FM inference against the Compose container.** Invoke `annotate_cell_type` and/or `predict_perturbation` through the agent at `http://localhost:8000`, record latency + output, then flip `14-VERIFICATION.md` to `passed` 8/8 and tick Phase 14 in ROADMAP.md.
- **OPEN (EXPORT-02 defect, found 2026-10-13):** exported scanpy script emits `adata = sc.read_h5ad("")` for uploaded datasets at every version — `export_script.py:91-92` degrades a `None` `source_path` to `""`, and the registry only records `source_path` on v1 (as a since-deleted temp path). Census datasets unaffected, which is why tests missed it. Three candidate fixes in phase 14 `deferred-items.md`; needs a regression test for the uploaded-dataset path.
- **OPEN (docs):** `docker/README.md` predates the non-root fixes and omits runtime file ownership — the most likely thing to break a rebuild. See phase 14 `deferred-items.md`.
- Do NOT run GSD plan execution as a headless automation — plan execution has interactive gates and the 14-01 kickoff stalled on one mid-run, leaving a half-finished tree. Run plans interactively.
- 14-03 will need real network + disk: it fetches the scGPT whole-human checkpoint, clones Geneformer, and builds a census-derived reference index inside the image build. Base image is already 1.61GB before any of that.
- Full-suite test-isolation bug: 14 failures in `tests/test_vcc_eval.py` / `tests/test_vcc_report.py`, all 25 pass in isolation. Root cause isolated during 13-03 — leaked global thread-count state makes `pdex` size numba's threadpool at 0, so `cell_eval.MetricsEvaluator.__init__` raises `ValueError: The number of threads must be between 1 and 10`. See phase 13 `deferred-items.md`; needs a cleanup plan.
- VCC real dataset download (Phase 5 Task 3) still pending — non-blocking for v1.2
- **Jetson Orin Nano 8GB edge appliance: ROADMAP ITEM ONLY** (added 2026-09-18, decisions locked 2026-09-18). Researched and written up as milestone v1.3, Phases 15 (arm64 + GPU port) and 16 (appliance hardening) — see `.planning/research/JETSON-ORIN-NANO.md` and the v1.3 section of ROADMAP.md. Deliberately NOT decomposed into plans and NOT built. **Decisions locked by Darren:** JetPack 6.2 (its system Python 3.10 matches `geneformer_worker/.venv`); scGPT strategy is the torchtext shim gated on a blocking spike with baseline-only annotation as the pre-declared fallback; the deliverable is a true appliance (headless, network-discoverable, self-provisioning), which is why Phase 16 exists. Headline finding: `torchtext==0.18.0` has no linux-aarch64 wheel and no sdist and is archived upstream, so the scGPT worker's Python 3.9 floor cannot coexist with GPU acceleration (NVIDIA ships cp310/cp312 CUDA wheels only) — but torchtext's entire footprint in scGPT is one `Vocab` subclass, and removing it also removes the reason for the `torch==2.3.0` pin. Two unverified items to check first when this phase is planned: aarch64 wheel availability for `tiledbsoma` and `cell-eval`.

### Blockers/Concerns

- VCC real dataset download (Phase 5 Task 3) was deferred due to no GCP billing — still pending, non-blocking for v1.2.

## Session Continuity

Last session: 2026-10-13
Stopped at: Phase 14 close-out complete — all 5 plans executed, 14-05-SUMMARY.md and 14-VERIFICATION.md written, three orphaned docker fixes pushed (origin/main at 6ec5ff6). Verification is `partial` 7/8; the only open leg is FM inference against the Compose stack.
Resume file: .planning/phases/14-docker-compose-deployment/14-VERIFICATION.md (see "To close")

Note on the 3-week gap: no work occurred between 2026-09-19 and 2026-10-13. The
container kept running throughout, so the live evidence this close-out relies on
is continuous with the 14-05 execution session rather than reconstructed from a
rebuild.
