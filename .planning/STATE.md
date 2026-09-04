---
gsd_state_version: 1.0
milestone: v1.0
milestone_name: milestone
status: planning
stopped_at: "Completed 02-01-PLAN.md (Wave 0: igraph dependency, structured_adata fixture, bounded-summary dataclass contracts)"
last_updated: "2026-09-04T20:18:55.517Z"
last_activity: "2026-09-04 — Executed 02-01-PLAN.md (Wave 0: igraph dependency, structured_adata fixture, bounded-summary dataclass contracts)"
progress:
  total_phases: 6
  completed_phases: 1
  total_plans: 10
  completed_plans: 6
  percent: 60
---

# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-09-03)

**Core value:** A Biopunk Labs researcher can ask a plain-language question about a single-cell dataset and get back a QC'd, annotated, interpreted answer without writing a scanpy script by hand.
**Current focus:** Phase 2 — Analysis Tool Layer (Wave 0 complete, Wave 1 next)

## Current Position

Phase: 2 of 6 (Analysis Tool Layer) — IN PROGRESS
Plan: 1 of 5 in current phase — Wave 0 (02-01) complete; Wave 1 (02-02, 02-03, 02-04) next
Status: 02-01-PLAN.md complete: igraph dependency installed, structured_adata fixture added, analysis/summary.py bounded dataclasses (PreprocessSummary, ClusterSummary, DEGeneResult, DESummary) defined for Wave 1 to build against. Full test suite green (31 tests).
Last activity: 2026-09-04 — Executed 02-01-PLAN.md (Wave 0: igraph dependency, structured_adata fixture, bounded-summary dataclass contracts)

Progress: [██████░░░░] 60% (6/10 plans complete)

## Performance Metrics

**Velocity:**
- Total plans completed: 6
- Average duration: ~10 min
- Total execution time: ~63 min

**By Phase:**

| Phase | Plans | Total | Avg/Plan |
|-------|-------|-------|----------|
| 01-ingest-qc-pipeline | 5 | ~55min | ~11min |
| 02-analysis-tool-layer | 1 | ~8min | ~8min |

**Recent Trend:**
- Last 5 plans: 25min, 4min, 2min, 9min, 8min
- Trend: stable/fast (Phase 2 Wave 0 plan came in under Phase 1 average)

*Updated after each plan completion*
| Phase 01-ingest-qc-pipeline P01 | 13min | 2 tasks | 4 files |
| Phase 01 P02 | 25min | 2 tasks | 6 files |
| Phase 01-ingest-qc-pipeline P03 | 4min | 2 tasks | 2 files |
| Phase 01-ingest-qc-pipeline P04 | 2min | 2 tasks | 2 files |
| Phase 01-ingest-qc-pipeline P05 | 9min | 2 tasks | 2 files |
| Phase 02-analysis-tool-layer P01 | 8min | 2 tasks | 6 files |

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

### Pending Todos

None yet. Phase 2 Wave 0 (02-01) complete; next step is Wave 1 (02-02 preprocess.py, 02-03 cluster.py, 02-04 diffexp.py), which can run in parallel since all three depend only on 02-01's igraph dependency, structured_adata fixture, and analysis/summary.py contracts.

### Blockers/Concerns

- Phase 4 (Bio-FM annotation): scGPT/Geneformer VRAM requirements are LOW confidence per research — verify against current model cards before implementation. Self-hosted-by-default decision (confirmed 2026-09-03) makes this sizing question load-bearing for Phase 4 planning, not just a nice-to-know.
- Phase 5 (Perturbation + VCC): GEARS/cell-gears environment isolation is MEDIUM confidence and version-sensitive (pinned older PyTorch Geometric stack). VCC scope question is now resolved (task format/metrics only, confirmed 2026-09-03) — no longer a blocker.
- Phase 6 (NL Q&A): no established reference pattern for hallucination-mitigation (claim traceability, confidence surfacing) at this agent+scientific-tool combination — flagged as highest-risk phase in research.
- Project-wide validation with Elliot Roth: resolved 2026-09-03 (see Decisions above). Remaining open item (non-blocking): check overlap with Cardiac Base Editor / FDT-BioTech on cardiomyocyte single-cell data as an early test dataset (CONCEPT.md).

## Session Continuity

Last session: 2026-09-04T20:18:55.517Z
Stopped at: Completed 02-01-PLAN.md (Wave 0: igraph dependency, structured_adata fixture, bounded-summary dataclass contracts)
Resume file: None
