---
gsd_state_version: 1.0
milestone: v1.0
milestone_name: milestone
status: planning
stopped_at: "Completed 02-04-PLAN.md (Wave 1: analysis/diffexp.py, ANLYS-03) -- Wave 1 fully complete"
last_updated: "2026-09-04T21:10:00.000Z"
last_activity: "2026-09-04 — Executed 02-04-PLAN.md (Wave 1: analysis/diffexp.py, ANLYS-03)"
progress:
  total_phases: 6
  completed_phases: 1
  total_plans: 10
  completed_plans: 9
  percent: 90
---

# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-09-03)

**Core value:** A Biopunk Labs researcher can ask a plain-language question about a single-cell dataset and get back a QC'd, annotated, interpreted answer without writing a scanpy script by hand.
**Current focus:** Phase 2 — Analysis Tool Layer (Wave 0 and Wave 1 complete; Wave 2 — 02-05 pipeline.py — next)

## Current Position

Phase: 2 of 6 (Analysis Tool Layer) — IN PROGRESS
Plan: 4 of 5 in current phase — Wave 1 (02-02, 02-03, 02-04) all complete; Wave 2 (02-05 pipeline.py) next, final plan of the phase
Status: 02-04-PLAN.md complete: analysis/diffexp.py implements differential_expression() -- generic Wilcoxon rank-sum DE (method="wilcoxon", tie_correct=True, pts=True, corr_method="benjamini-hochberg") over any categorical .obs column, recovers structured_adata's known marker genes, returns bounded DESummary (top_genes capped at n_genes). Task 2 was interrupted mid-execution by a subagent session-limit cutoff and completed directly in the orchestrating session. Full test suite green (51 tests).
Last activity: 2026-09-04 — Executed 02-04-PLAN.md (Wave 1: analysis/diffexp.py, ANLYS-03)

Progress: [█████████░] 90% (9/10 plans complete)

## Performance Metrics

**Velocity:**
- Total plans completed: 8
- Average duration: ~9.5 min
- Total execution time: ~76 min

**By Phase:**

| Phase | Plans | Total | Avg/Plan |
|-------|-------|-------|----------|
| 01-ingest-qc-pipeline | 5 | ~55min | ~11min |
| 02-analysis-tool-layer | 3 | ~21min | ~7min |

**Recent Trend:**
- Last 5 plans: 2min, 9min, 8min, 8min, 5min
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

### Pending Todos

All three Wave 1 plans (02-02 preprocess.py, 02-03 cluster.py, 02-04 diffexp.py) complete. Wave 2 (02-05 pipeline.py) is next and final for the phase — composes preprocess/cluster/diffexp into the coarse-grained `analyze()` orchestration entrypoint mirroring `ingest/pipeline.py::ingest_10x()`, including `verify_counts_integrity()` pre+post to close the counts-layer round-trip vulnerability (Pitfall 6). After 02-05, run gsd-verifier for phase goal-backward verification, then mark Phase 2 complete.

### Blockers/Concerns

- Phase 4 (Bio-FM annotation): scGPT/Geneformer VRAM requirements are LOW confidence per research — verify against current model cards before implementation. Self-hosted-by-default decision (confirmed 2026-09-03) makes this sizing question load-bearing for Phase 4 planning, not just a nice-to-know.
- Phase 5 (Perturbation + VCC): GEARS/cell-gears environment isolation is MEDIUM confidence and version-sensitive (pinned older PyTorch Geometric stack). VCC scope question is now resolved (task format/metrics only, confirmed 2026-09-03) — no longer a blocker.
- Phase 6 (NL Q&A): no established reference pattern for hallucination-mitigation (claim traceability, confidence surfacing) at this agent+scientific-tool combination — flagged as highest-risk phase in research.
- Project-wide validation with Elliot Roth: resolved 2026-09-03 (see Decisions above). Remaining open item (non-blocking): check overlap with Cardiac Base Editor / FDT-BioTech on cardiomyocyte single-cell data as an early test dataset (CONCEPT.md).

## Session Continuity

Last session: 2026-09-04T20:32:04.781Z
Stopped at: Completed 02-03-PLAN.md (Wave 1: analysis/cluster.py, ANLYS-02)
Resume file: None
