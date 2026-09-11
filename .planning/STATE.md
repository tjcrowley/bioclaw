---
gsd_state_version: 1.0
milestone: v1.0
milestone_name: milestone
current_plan: 3 of 3
status: completed
stopped_at: "Completed 06-03-PLAN.md (Phase 6 Wave 3: live_llm QA-01/02/03 integration test passed; checkpoint approved by Darren; Phase 6 and v1.0 milestone complete)"
last_updated: "2026-09-11T15:33:45.319Z"
last_activity: 2026-09-11 — Executed 06-03-PLAN.md (Wave 3, final plan of Phase 6 and the v1.0 milestone).
progress:
  total_phases: 6
  completed_phases: 6
  total_plans: 29
  completed_plans: 29
  percent: 100
---

# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-09-03)

**Core value:** A Biopunk Labs researcher can ask a plain-language question about a single-cell dataset and get back a QC'd, annotated, interpreted answer without writing a scanpy script by hand.
**Current focus:** All 6 phases complete. v1.0 milestone done — the full ingest → analysis → agent → bio-FM annotation → perturbation/VCC → natural-language Q&A stack is built and live-verified end to end.

## Current Position

Phase: 6 of 6 (Natural-Language Q&A Capstone) — COMPLETE
Plan: 3 plans planned — 06-01 (Wave 0: qa/ skeleton + system_prompt kwarg on run_session/build_options + citation module + test scaffolds) COMPLETE; 06-02 (Wave 2: ask_question + QA_SYSTEM_PROMPT wired) COMPLETE; 06-03 (Wave 3: live multi-tool integration test asserting citation resolution + uncertainty surfacing) COMPLETE.
Current Plan: 3 of 3 (final)
Next: /gsd:complete-milestone (all phases and plans done)
Status: Phase 5 COMPLETE (2026-09-10; 05-06 Task 3 deferred pending GCS billing). Phase 6 Wave 0 (06-01) COMPLETE 2026-09-10. Phase 6 Wave 2 (06-02) COMPLETE 2026-09-10. Phase 6 Wave 3 (06-03) COMPLETE 2026-09-11 — live_llm integration test passed for real (54.43s, 2 distinct tools, 10/10 citations resolved, decimal DE values paired with citations); two production bugs found and fixed during checkpoint verification (headless permission_mode hang in agent/session.py; result_sha256 citation-hash timing). Phase 6 and the v1.0 milestone are now fully complete: QA-01, QA-02, QA-03 all closed.
Last activity: 2026-09-11 — Executed 06-03-PLAN.md (Wave 3 for Phase 6, final plan of the milestone).

Progress: [██████████] 100% (29/29 plans complete; all 6 phases done)

## Performance Metrics

**Velocity:**
- Total plans completed: 14
- Average duration: ~7 min (excludes 06-03's cross-session checkpoint debugging time)
- Total execution time: ~95 min

**By Phase:**

| Phase | Plans | Total | Avg/Plan |
|-------|-------|-------|----------|
| 01-ingest-qc-pipeline | 5 | ~55min | ~11min |
| 02-analysis-tool-layer | 5 | ~26min | ~5min |

**Recent Trend:**
- Last 5 plans: 8min, ~10min, 5min, 3min, 4min, ~95min (06-03, includes checkpoint bugfix session)
- Trend: stable/fast; 06-03 was the outlier due to two real production bugs surfaced only by the live_llm checkpoint

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
| Phase 05-perturbation-response-tool-vcc-benchmark-harness P01 | 6min | 3 tasks | 12 files |
| Phase 05-perturbation-response-tool-vcc-benchmark-harness P02 | 2min | 2 tasks | 2 files |
| Phase 05-perturbation-response-tool-vcc-benchmark-harness P03 | 6min | 2 tasks | 6 files |
| Phase 05-perturbation-response-tool-vcc-benchmark-harness P04 | 18min | 2 tasks | 2 files |
| Phase 05-perturbation-response-tool-vcc-benchmark-harness P05 | 3min | 2 tasks | 2 files |
| Phase 05-perturbation-response-tool-vcc-benchmark-harness P06 | 5min | 2 tasks | 3 files |
| Phase 06-natural-language-qa-capstone P01 | 3min | 2 tasks | 6 files |
| Phase 06-natural-language-qa-capstone P02 | 4min | 1 tasks | 2 files |
| Phase 06-natural-language-qa-capstone P03 | ~95min (cross-session; checkpoint bugfixing) | 2 tasks | 4 files |

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
- [Phase 05-perturbation-response-tool-vcc-benchmark-harness]: cell-eval installed torch-free (confirmed via uv.lock); PerturbationSummary uses scalar model_call/baseline_call (not lists) per PERT-01 one-target-gene-per-call design; .h5ad branch in load() omits var_names_make_unique() since well-formed h5ad already has valid var_names
- [Phase 05-perturbation-response-tool-vcc-benchmark-harness]: 05-02: Ridge fallback feature is target gene's own control-expression scalar (single-feature Ridge per 05-RESEARCH.md Pattern 1); predict() routes exact lookup -> fallback -> KeyError by distinct failure modes; fit_from_adata returns (model, control_mean) tuple for Plan 05-03
- [Phase 05-perturbation-response-tool-vcc-benchmark-harness]: 05-03: build_base_mean_adata returns GLOBAL mean of all pert group means (not per-gene); tests assert against actual output; allow_discrete=True required for raw counts; pandas Series must use .values for scipy sparse indexing
- [Phase 05-perturbation-response-tool-vcc-benchmark-harness]: 05-04: cell_eval.MetricsEvaluator.compute(profile='vcc') returns Polars DataFrames (not dict); VCC_METRICS=[mae,discrimination_score_l1,overlap_at_N] mapped to {mae,pds,des}; both adata_pred/real must include control row; allow_discrete=True for raw integer count fixtures
- [Phase 05-perturbation-response-tool-vcc-benchmark-harness]: 05-05: Plain dict (not dataclass) for benchmark report shape -- trivially JSON-serializable for checkpoint display and agent tool output
- [Phase 05-perturbation-response-tool-vcc-benchmark-harness]: 05-05: ValueError raised for BOTH predictor_metrics AND baseline_metrics None/empty/incomplete -- symmetric validation enforces completeness structurally (VCC-03 closed)
- [Phase 05-perturbation-response-tool-vcc-benchmark-harness]: Task 3 (real VCC data download + smoke test) DEFERRED: no GCP billing account available; smoke test gated behind vcc_data marker and ready to run when billing is enabled
- [Phase 06-natural-language-qa-capstone]: 06-01: qa/citations.py fully implemented in Task 1 (not stubbed) since it is pure Python w/ no LLM dependency; Task 2 tests written against real implementation, all 7 passing on first run -- Wave 0 contract stable for Plans 06-02/03
- [Phase 06-natural-language-qa-capstone]: 06-01: system_prompt kwarg is additive on build_options/run_session with existing SYSTEM_PROMPT constant as default -- zero behavioral change for Phase-3 callers (verified by 8 test_agent_session_wiring tests still passing)
- [Phase 06-natural-language-qa-capstone]: 06-01: CITATION_RE requires 12 lowercase hex chars for the sha prefix; test_parse_citation_ids_ignores_malformed asserts uppercase, missing-prefix, and wrong-length forms are all rejected -- prevents future silent regex loosening
- [Phase 06-natural-language-qa-capstone]: 06-02: ask_question is a policy-free wrapper -- verify_answer_citations reports (list of tuples with record|None) but ask_question does not raise on unresolved citations; policy lives in the caller/test (Plan 06-03 asserts on citation_results shape/count)
- [Phase 06-natural-language-qa-capstone]: 06-02: QA_SYSTEM_PROMPT extends 06-RESEARCH.md Pattern 1 with two additional protocol sections beyond citation+uncertainty -- explicit anti-hallucination ('MUST invoke the corresponding tool in this session') and mandatory-citation ('MUST include at least one [ref:...]') clauses; fast-suite unit tests assert on each keyword so prompt drift breaks loudly in CI
- [Phase 06-natural-language-qa-capstone]: 06-02: TDD test file uses asyncio.run() inside sync tests + unittest.mock.AsyncMock (matching tests/test_agent_session_wiring.py's pattern) rather than adding pytest-asyncio -- keeps dev-dependency footprint stable, async surface fully exercised
- [Phase 06-natural-language-qa-capstone]: 06-03: `permission_mode="bypassPermissions"` added to `build_options()` in `agent/session.py` -- without it, any headless (pytest/script) `run_session()` caller hangs forever on interactive tool approval with no TTY to approve from; safe since `allowed_tools` is scoped to the in-process bioclaw MCP server only. This was a latent Phase 3 bug, never exercised live until 06-03's checkpoint.
- [Phase 06-natural-language-qa-capstone]: 06-03: `analyze_dataset_tool` widened to pass through `run_de`/`de_groupby`/`de_group1`/`de_group2`/`de_n_genes` to `AnalysisConfig` -- `analyze()` already supported these from Phase 2, the tool wrapper simply never forwarded them; only surfaced once a real live question required DE.
- [Phase 06-natural-language-qa-capstone]: 06-03: `log_tool_call()` now returns the `result_sha256` it computes, forwarded to the model via the `PostToolUse` hook's `hookSpecificOutput.additionalContext` -- the citation protocol in `QA_SYSTEM_PROMPT` asks the model to quote this hash, but it was previously computed only after the tool response had already reached the model, making correct citation structurally impossible.
- [Phase 06-natural-language-qa-capstone]: 06-03 checkpoint verified live (real ANTHROPIC_API_KEY, run by Darren per the checkpoint's how-to-verify steps): test passed in 54.43s — 2 distinct tools logged (QA-01), 10/10 citation tags resolved with zero hallucinated citations (QA-02), 32 significant DE genes with a decimal value paired with a resolved citation (QA-03). Phase 6 and the v1.0 milestone are complete.

### Pending Todos

None — all 6 phases and 29 plans of the v1.0 milestone are complete. Ready for `/gsd:complete-milestone`.

### Blockers/Concerns

- Phase 4 (Bio-FM annotation): RESOLVED at planning time (2026-09-05) — scGPT chosen over Geneformer (PyPI-installable, confirmed CPU-capable via `load_pretrained`, zero-shot reference-mapping needs no fine-tuning; Geneformer's own model card requires GPU and isn't on PyPI). Dependency isolation (scGPT's live PyPI pins) confirmed working, isolated into `bio_fm_worker/.venv`, closed by 04-05.
- Phase 5 (Perturbation + VCC): GEARS/cell-gears environment isolation was MEDIUM confidence and version-sensitive but resolved by execution. VCC scope question resolved (task format/metrics only, confirmed 2026-09-03). Task 3 (real VCC data download smoke test) remains DEFERRED — no GCP billing account available; gated behind `vcc_data` marker, ready to run when billing is enabled. Non-blocking for milestone completion (public task format/metrics scope was already validated).
- Phase 6 (NL Q&A): RESOLVED — hallucination-mitigation (claim traceability, confidence surfacing) pattern validated live end to end via 06-03's checkpoint; no longer a research risk, it's a working, tested implementation.
- Project-wide validation with Elliot Roth: resolved 2026-09-03 (see Decisions above). Remaining open item (non-blocking): check overlap with Cardiac Base Editor / FDT-BioTech on cardiomyocyte single-cell data as an early test dataset (CONCEPT.md).

## Session Continuity

Last session: 2026-09-11T15:33:45.319Z
Stopped at: Completed 06-03-PLAN.md (Phase 6 Wave 3: live_llm QA-01/02/03 integration test passed live; checkpoint approved; Phase 6 and v1.0 milestone complete). Next recommended step: /gsd:complete-milestone.
Resume file: None
