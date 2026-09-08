---
gsd_state_version: 1.0
milestone: v1.0
milestone_name: milestone
status: executing
stopped_at: "Completed 04-05-PLAN.md (real scGPT checkpoint + cellxgene-census reference index + bio_fm_smoke gate, ANNOT-01/02/03); Phase 4 COMPLETE. Next: Phase 5 (Perturbation + VCC)."
last_updated: "2026-09-08T00:00:00.000Z"
last_activity: 2026-09-08 — Executed Phase 4 Plan 05 (bio_fm_smoke checkpoint). Fixed 7 bugs discovered during real end-to-end verification (StringDtype/uns cross-venv compat, os.sched_getaffinity macOS shim, feature_name reference gene-col fix, reference embed cache, stdout JSON extraction). Smoke test passed: 31.2s latency, 1/1 green.
progress:
  total_phases: 6
  completed_phases: 4
  total_plans: 20
  completed_plans: 20
  percent: 100
---

# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-09-03)

**Core value:** A Biopunk Labs researcher can ask a plain-language question about a single-cell dataset and get back a QC'd, annotated, interpreted answer without writing a scanpy script by hand.
**Current focus:** Phase 4 (Bio-FM Tool Layer — Cell-Type Annotation) is executing. Waves 0-2 (04-01 through 04-04) are complete. Only Wave 3 (04-05, blocking human-verify checkpoint for the real scGPT checkpoint + cellxgene-census reference index) remains before Phase 4 is done.

## Current Position

Phase: 4 of 6 (Bio-FM Tool Layer — Cell-Type Annotation) — COMPLETE
Plan: All 5 plans complete — 04-01 (annotation/ skeleton) ✓; 04-02 (decoupler baseline, ANNOT-02) ✓; 04-03 (bio_fm_worker venv, ANNOT-01) ✓; 04-04 (annotate() pipeline + annotate_cell_type_tool wiring, ANNOT-03) ✓; 04-05 (real scGPT checkpoint + cellxgene-census reference + bio_fm_smoke gate) ✓.
Next: Phase 5 (Perturbation + VCC benchmark).
Status: Phase 4 COMPLETE. Smoke test passed 2026-09-08 at 31.2s end-to-end latency (cache-hit path). Phase 4 executed and committed: `annotation/pipeline.py::annotate()` implemented against a pre-existing untracked test file (`tests/test_annotation_pipeline.py`, found already written from a prior interrupted session, matching this plan's spec exactly) — loads via `DatasetStore.load()`, calls `baseline_annotate()` unconditionally, wraps `call_scgpt_annotate()` in try/except (falls back to `fm_calls=[]` on any failure, never crashes), never persists a new store version. `annotate_cell_type_tool` added to `agent/tools.py` mirroring `analyze_dataset_tool`'s exact shape, registered in `agent/server.py`. One wrinkle found during Task 2's round-trip test: `baseline_annotate()`'s default `markers=None` path calls decoupler's `dc.op.resource()` (a real PanglaoDB network fetch) which failed in this sandbox — mocked both `call_scgpt_annotate` and `baseline_annotate` in the new agent-tool test to stay network-free, matching Task 1's own pipeline-test pattern. Full fast test suite green (98 passed, 1 deselected). Next up: Wave 3 (04-05) — this is the phase's blocking human-verify checkpoint (real multi-GB scGPT checkpoint download + torchtext ABI repair + cellxgene-census reference index build), so it will stop and require your manual confirmation partway through.
Last activity: 2026-09-05 — Executed Phase 4 Plan 03 (isolated scGPT venv + fm_client subprocess shim) and committed outstanding Phase 3 live-test fixes.

Progress: [█████████░] 90% (18/20 plans complete; Phase 4 Plans 01-03 of 5 executed)

## Performance Metrics

**Velocity:**
- Total plans completed: 13
- Average duration: ~7 min
- Total execution time: ~90 min

**By Phase:**

| Phase | Plans | Total | Avg/Plan |
|-------|-------|-------|----------|
| 01-ingest-qc-pipeline | 5 | ~55min | ~11min |
| 02-analysis-tool-layer | 5 | ~26min | ~5min |

**Recent Trend:**
- Last 5 plans: 8min, 8min, 5min, ~10min, 5min
- Trend: stable/fast (Phase 2 plans coming in under Phase 1 average)

*Updated after each plan completion*
| Phase 01-ingest-qc-pipeline P01 | 13min | 2 tasks | 4 files |
| Phase 01 P02 | 25min | 2 tasks | 6 files |
| Phase 01-ingest-qc-pipeline P03 | 4min | 2 tasks | 2 files |
| Phase 01-ingest-qc-pipeline P04 | 2min | 2 tasks | 2 files |
| Phase 01-ingest-qc-pipeline P05 | 9min | 2 tasks | 2 files |
| Phase 02-analysis-tool-layer P01 | 8min | 2 tasks | 6 files |
| Phase 02 P02 | 8 | 2 tasks | 2 files |
| Phase 02-analysis-tool-layer P03 | 5min | 2 tasks | 2 files |
| Phase 02-analysis-tool-layer P04 | ~10min (interrupted/resumed) | 2 tasks | 2 files |
| Phase 02 P05 | 5min | 2 tasks | 2 files |
| Phase 03-agent-orchestration-wiring P01 | 2min | 2 tasks | 4 files |
| Phase 03 P04 | 2min | 1 tasks | 2 files |
| Phase 03-agent-orchestration-wiring P03 | 5min | 1 tasks | 2 files |
| Phase 03 P02 | 12min | 2 tasks | 3 files |
| Phase 03-agent-orchestration-wiring P05 | 5min | 2 tasks | 3 files |
| Phase 04-bio-fm-cell-type-annotation P01 | 6min | 2 tasks | 8 files |
| Phase 04-bio-fm-cell-type-annotation P02 | ~15min | 1 tasks | 2 files |

## Accumulated Context

### Decisions

Decisions are logged in PROJECT.md Key Decisions table.
Recent decisions affecting current work:

- Roadmap: 6 phases, dependency-driven bottom-up order (ingest/QC → analysis → agent wiring → bio-FM annotation → perturbation+VCC → NL Q&A capstone), following research/SUMMARY.md's suggested structure directly.
- 2026-09-03: Elliot Roth confirmed — single-cell wedge matches Biopunk Labs' real pain point; bio-FM hosting is self-hosted by default with a hosted-inference option kept in the architecture; first dataset is public (`cellxgene-census`/VCC); VCC benchmark scope is the public task format/metrics, not the live leaderboard. All four now reflected in PROJECT.md Validated requirements and Key Decisions.
- [Phase 01-ingest-qc-pipeline]: 01-02: Added pythonpath=["."] to pytest config so ingest.* modules are importable by tests (blocking issue found while writing loader tests)
- [Phase 01-ingest-qc-pipeline]: 01-03: Filled NaN QC values (mito%, doublet score/flag) for all-zero cells with 0/0.0/False rather than propagating nulls, since QC-01 requires all five columns non-null for every cell
- [Phase 01-ingest-qc-pipeline]: 01-03: Scrublet n_prin_comps default (30) crashes on small AnnData inputs (PCA bound depends on Scrublet's internal HVG selection, not adata.n_vars) — added a shrink-and-retry loop instead of a fixed smaller constant
- [Phase 01-ingest-qc-pipeline]: 01-04: Hand-rolled filesystem+SQLite dataset registry (no LaminDB); version = MAX(version)+1 per name, never overwritten
- [Phase 01-ingest-qc-pipeline]: 01-05: Re-freeze/re-checksum `layers['counts']` (contract.set_counts_layer) a second time immediately after qc.run(), since QC filtering allocates a new writeable sparse buffer that invalidates the pre-filter checksum — caught only at the full-pipeline integration level, not in any Wave 1 module's own unit tests
- [Phase 02-analysis-tool-layer]: 02-01: structured_adata fixture uses RNG seed 3 (next unused seed after Phase 1's 0/1/2), 15 marker genes per population at Poisson lam=15 vs. lam=2 background, matching the plan spec exactly
- [Phase 02-analysis-tool-layer]: 02-01: analysis/summary.py's four dataclasses transcribed verbatim from the plan's `<interfaces>` contract, no additions — three Wave 1 plans (02-02/03/04) depend on this exact shape being stable
- [Phase 02]: 02-02: Clamped PCA n_comps against the actual post-HVG-selection gene count (n_hvg), not adata.n_vars -- sklearn's arpack solver requires n_components strictly less than min(n_samples, n_features), and HVG selection can silently return fewer genes than requested on small fixtures
- [Phase 02-analysis-tool-layer]: 02-03: flavor='igraph' always paired with explicit directed=False and n_iterations=2; Leiden determinism asserted, UMAP coordinate exactness deliberately not asserted (Pitfall 5)
- [Phase 02-analysis-tool-layer]: 02-04: DESummary.top_genes sorted/capped by pvals_adj ascending via .head(n_genes); n_significant/n_genes_tested computed over the full unsliced rank_genes_groups_df result before truncation, mirroring PreprocessSummary/ClusterSummary's O(1)/O(top_n) bounding invariant
- [Phase 02]: 02-05: Task-split analyze() implementation -- Task 1 hardcodes de_summary=None (core load-verify-preprocess-cluster-verify-save flow), Task 2 adds config.run_de branch as a pure additive diff, matching the plan's explicit task boundary
- [Phase 02]: 02-05: verify_counts_integrity() enforced both immediately after store.load() and immediately before store.save() in analyze() -- closes Pitfall 6 (write-lock does not survive an h5ad round-trip) at the pipeline entrypoint, raising RuntimeError naming the dataset on failure
- [Phase 03-agent-orchestration-wiring]: 03-01: No deviations - claude-agent-sdk installed and live_llm marker registered exactly per plan; agent/ package skeleton mirrors analysis/__init__.py precedent
- [Phase 03-agent-orchestration-wiring]: 03-03: log_tool_call implemented exactly per plan's provided code (sha256(json.dumps(..., sort_keys=True, default=str)) hashing, async signature for future PostToolUse hook shape) -- no deviation needed
- [Phase 03-agent-orchestration-wiring]: 03-04: SessionMemory implemented exactly per plan's provided code, mirroring ingest/store.py::DatasetStore's connection/table pattern; ORDER BY created_at DESC, rowid DESC tiebreaker used for deterministic most-recent-first ordering when ISO timestamps collide -- no deviation needed
- [Phase 03-agent-orchestration-wiring]: 03-02: `@tool`-decorated functions are `SdkMcpTool` instances, not directly callable -- tests invoke `<tool>.handler(args)`, not `<tool>(args)` (verified via `vars()` against the installed `claude_agent_sdk` package)
- [Phase 03-agent-orchestration-wiring]: 03-02: `tiny_mtx_dir`'s 18 genes can never pass `QCConfig`'s default `min_genes_per_cell=200` threshold (no cell can have >=200 detected genes when only 18 exist) -- added a local, larger `analyzable_mtx_dir` fixture (300 genes x 60 cells, two marker populations) in `tests/test_agent_tools.py` for the `analyze_dataset_tool` round-trip test; `tiny_mtx_dir` still used for the plain ingest-only test, matching Phase 1's own `tests/test_pipeline.py` precedent of overriding `qc_config` for this exact fixture/threshold interaction
- [Phase 03-agent-orchestration-wiring]: 03-05: PostToolUse hook callback signature/registration verified against the installed claude_agent_sdk package (single input_data dict + tool_use_id + context; hooks[event] is list[HookMatcher]) rather than the plan sketch's positional kwargs shape
- [Phase 03-agent-orchestration-wiring]: 03-05 (post-hoc, found during live_llm debugging 2026-09-05): uncaught tool handler exceptions dispatch as a distinct `PostToolUseFailure` SDK event (not `PostToolUse`), invisible to hooks that only subscribe to `PostToolUse` -- `agent/tools.py` now catches all exceptions and returns a controlled `is_error: True` result instead. Also: in-process MCP `tool_response` seen by a `PostToolUse` hook is the handler's bare `content` array, not the `{"content":[...], "is_error":...}` dict the handler returns -- the CLI strips the wrapper and `is_error` is not passed through separately.
- [Phase 04-bio-fm-cell-type-annotation]: Planning (2026-09-05): scGPT chosen over Geneformer for ANNOT-01 (PyPI-installable, CPU-capable, zero-shot reference-mapping) — see 04-RESEARCH.md. scGPT/torch isolated into a plain-venv `bio_fm_worker/` environment reached via subprocess shim (`annotation/fm_client.py`), never added to the root `pyproject.toml`. `decoupler` (lightweight, no torch) installed directly into the main venv for ANNOT-02's baseline. ANNOT-03's ontology metadata sourced from `cellxgene-census`'s schema-required `cell_type_ontology_term_id` field on the reference index, not a separate ontology-mapping pipeline. The decoupler baseline call is unconditional in `annotate()`'s code order (executes before/independent of the FM call's try/except), so ANNOT-02 holds even when the FM call fails.
- [Phase 04-bio-fm-cell-type-annotation]: 04-01: decoupler installed torch-free with zero resolver conflicts, confirming 04-RESEARCH.md's Isolation Boundary; AnnotationCall/AnnotationSummary dataclasses fixed verbatim from the plan spec for all downstream Wave 1/2 plans to implement against.
- [Phase 04-bio-fm-cell-type-annotation]: 04-02: decoupler==2.2.0's real API introspected directly (dc.op.resource / dc.mt.ora), superseding 04-RESEARCH.md's LOW-MEDIUM-confidence v1.x sketch. baseline_annotate() pseudobulks per-group counts before calling dc.mt.ora (which operates per-observation, not per-group) and overrides n_up to 10% of gene count (vs decoupler's own 5% default) since 5% produced tied/non-discriminating scores on small marker panels -- verified empirically, documented in annotation/baseline.py's module docstring.
- [Phase 04-bio-fm-cell-type-annotation]: 04-03: `pip install scgpt` succeeded in isolated `bio_fm_worker/.venv` (Python 3.9.6) but `import scgpt` fails on a torch/torchtext ABI mismatch (dlopen symbol-not-found inside torchtext's compiled extension) -- per plan's own documented contingency, captured in bio_fm_worker/README.md with three repair candidates and left for 04-05, since fast tests mock the subprocess boundary entirely. run_scgpt_embed.py's embed_data() calls are therefore unverified against the real scgpt API -- 04-05 must re-verify once the import is repaired.

### Pending Todos

Phase 4 (Bio-FM Tool Layer — Cell-Type Annotation) is planned (5 plans, 04-01..04-05) and ready to execute via `/gsd:execute-phase 04-bio-fm-cell-type-annotation`. Wave 3's 04-05 ends in a blocking `checkpoint:human-verify` task (real scGPT checkpoint download + measured latency) that requires Darren's manual involvement — cannot be fully automated.

### Blockers/Concerns

- Phase 4 (Bio-FM annotation): RESOLVED at planning time (2026-09-05) — scGPT chosen over Geneformer (PyPI-installable, confirmed CPU-capable via `load_pretrained`, zero-shot reference-mapping needs no fine-tuning; Geneformer's own model card requires GPU and isn't on PyPI). Remaining open item is not VRAM sizing but dependency isolation: scGPT's live PyPI pins (`scvi-tools<1.0`, unpinned `torchtext`, `orbax<0.1.8`) must stay out of the main venv — plans isolate it into `bio_fm_worker/.venv`. Real CPU-inference latency is still unmeasured (one unverified third-party benchmark only) — closed by 04-05's `bio_fm_smoke` checkpoint, not before.
- Phase 5 (Perturbation + VCC): GEARS/cell-gears environment isolation is MEDIUM confidence and version-sensitive (pinned older PyTorch Geometric stack). VCC scope question is now resolved (task format/metrics only, confirmed 2026-09-03) — no longer a blocker.
- Phase 6 (NL Q&A): no established reference pattern for hallucination-mitigation (claim traceability, confidence surfacing) at this agent+scientific-tool combination — flagged as highest-risk phase in research.
- Project-wide validation with Elliot Roth: resolved 2026-09-03 (see Decisions above). Remaining open item (non-blocking): check overlap with Cardiac Base Editor / FDT-BioTech on cardiomyocyte single-cell data as an early test dataset (CONCEPT.md).

## Session Continuity

Last session: 2026-09-05T23:20:00.000Z
Stopped at: Completed 04-03-PLAN.md (isolated scGPT venv + fm_client subprocess shim, ANNOT-01); Wave 1 done, next is Wave 2 (04-04)
Resume file: None
