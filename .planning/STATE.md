---
gsd_state_version: 1.0
milestone: v1.0
milestone_name: milestone
status: executing
stopped_at: Completed 03-02-PLAN.md (agent/tools.py + agent/server.py, AGENT-01 tool-calling surface)
last_updated: "2026-09-05T12:45:06.921Z"
last_activity: 2026-09-05 — Executed 03-02-PLAN.md (agent/tools.py + agent/server.py, AGENT-01 tool-calling surface).
progress:
  total_phases: 6
  completed_phases: 2
  total_plans: 15
  completed_plans: 14
  percent: 93
---

# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-09-03)

**Core value:** A Biopunk Labs researcher can ask a plain-language question about a single-cell dataset and get back a QC'd, annotated, interpreted answer without writing a scanpy script by hand.
**Current focus:** Phase 3 (Agent Orchestration Wiring) EXECUTING — 03-01 (Wave 0 infra), 03-02 (AGENT-01 tool wrappers), 03-03 (AGENT-02 logging), 03-04 (AGENT-03 SessionMemory) all complete (Wave 1 done); 03-05 (Wave 2) next.

## Current Position

Phase: 3 of 6 (Agent Orchestration Wiring) — EXECUTING (4/5 plans complete)
Plan: 5 plans across 3 waves — 03-01 (Wave 0, infra) COMPLETE; Wave 1 (independent, all COMPLETE): 03-02 (AGENT-01 tool wrappers, `agent/tools.py`+`agent/server.py`), 03-03 (AGENT-02 execution logging, `agent/logging.py`), 03-04 (AGENT-03 SessionMemory, `agent/memory.py`); 03-05 (Wave 2: wires Wave 1's three modules into one `ClaudeSDKClient`-driven `run_session()`) NEXT, no longer blocked.
Status: Executing Phase 3. 03-01 and all of Wave 1 (03-02/03-03/03-04) executed cleanly. `agent/tools.py`/`agent/server.py` (AGENT-01 tool-calling surface), `agent/logging.py` (AGENT-02), and `agent/memory.py` (AGENT-03) all implemented and tested in isolation from the SDK/LLM per Pitfall 4's two-tier strategy. Full fast-tier suite green (`uv run pytest tests/ -q -m "not live_llm"` -> 74 passed). Next up: Wave 2 (03-05), then gsd-verifier goal-backward check against AGENT-01/02/03, then mark Phase 3 complete.
Last activity: 2026-09-05 — Executed 03-02-PLAN.md (agent/tools.py + agent/server.py, AGENT-01 tool-calling surface).

Progress: [█████████░] 93% (14/15 plans complete)

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

### Pending Todos

Phase 3 (Agent Orchestration Wiring) execution in progress: 03-01 (Wave 0 infra) and all of Wave 1 (03-02/03-03/03-04) complete. Next: 03-05 (Wave 2), then gsd-verifier goal-backward check against AGENT-01/02/03, then mark Phase 3 complete. Note: 03-05's live_llm integration test requires `ANTHROPIC_API_KEY` to actually run (fast-tier suite does not depend on it and will pass/skip without the key).

### Blockers/Concerns

- Phase 4 (Bio-FM annotation): scGPT/Geneformer VRAM requirements are LOW confidence per research — verify against current model cards before implementation. Self-hosted-by-default decision (confirmed 2026-09-03) makes this sizing question load-bearing for Phase 4 planning, not just a nice-to-know.
- Phase 5 (Perturbation + VCC): GEARS/cell-gears environment isolation is MEDIUM confidence and version-sensitive (pinned older PyTorch Geometric stack). VCC scope question is now resolved (task format/metrics only, confirmed 2026-09-03) — no longer a blocker.
- Phase 6 (NL Q&A): no established reference pattern for hallucination-mitigation (claim traceability, confidence surfacing) at this agent+scientific-tool combination — flagged as highest-risk phase in research.
- Project-wide validation with Elliot Roth: resolved 2026-09-03 (see Decisions above). Remaining open item (non-blocking): check overlap with Cardiac Base Editor / FDT-BioTech on cardiomyocyte single-cell data as an early test dataset (CONCEPT.md).

## Session Continuity

Last session: 2026-09-05T12:45:06.919Z
Stopped at: Completed 03-02-PLAN.md (agent/tools.py + agent/server.py, AGENT-01 tool-calling surface)
Resume file: None
