---
phase: 05-perturbation-response-tool-vcc-benchmark-harness
plan: "04"
subsystem: benchmarking
tags: [cell-eval, vcc, perturbation, metrics, anndata, polars]

# Dependency graph
requires:
  - phase: 05-03
    provides: perturbation.pipeline.predict() direct-call interface
  - phase: 05-01
    provides: benchmark/ skeleton, cell-eval installed, DatasetStore

provides:
  - benchmark/vcc_eval.py with compute_vcc_metrics() and run_vcc_eval() implemented
  - VCC-02 closed: PDS/DES/MAE computed by cell_eval.MetricsEvaluator exclusively
  - Direct-call harness that bypasses agent/MCP loop for batch benchmark runs

affects:
  - 05-05-PLAN.md (imports compute_vcc_metrics/run_vcc_eval for report generation)

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "compute_vcc_metrics() normalises Polars DataFrame output from cell_eval to stable {mae, pds, des} dict"
    - "tempfile.TemporaryDirectory when outdir=None so metric-only callers manage no files"
    - "run_vcc_eval() pseudobulks adata_real from stored dataset; adds control row to all three AnnData objects for MetricsEvaluator validation"

key-files:
  created:
    - benchmark/vcc_eval.py
    - tests/test_vcc_eval.py
  modified: []

key-decisions:
  - "cell_eval.MetricsEvaluator.compute(profile='vcc') returns (results: pl.DataFrame, agg_results: pl.DataFrame) -- not a dict or dataclass as sketched in 05-RESEARCH.md"
  - "VCC_METRICS confirmed as [mae, discrimination_score_l1, overlap_at_N]; mapped to {mae, pds, des} stable dict keys in compute_vcc_metrics()"
  - "Both adata_pred and adata_real supplied to MetricsEvaluator MUST contain a 'non-targeting' control row in obs[pert_col] -- MetricsEvaluator validates this at construction time"
  - "run_vcc_eval() builds adata_real from pseudobulk means of the stored dataset (same logic as fit_from_adata); adds ctrl_mean as the control row for all three assembled AnnData objects"
  - "allow_discrete=True passed through to MetricsEvaluator to handle raw integer count fixtures without normalize_total+log1p being applied"

patterns-established:
  - "Metric wrapper always normalises library-specific return types (Polars DataFrame) to plain Python dicts for stable downstream API"
  - "outdir=None -> TemporaryDirectory pattern: metric-only callers get no file side-effects"

requirements-completed: ["VCC-02"]

# Metrics
duration: 18min
completed: 2026-09-09
---

# Phase 5 Plan 04: VCC Benchmark Harness Summary

**compute_vcc_metrics() wraps cell_eval.MetricsEvaluator for official PDS/DES/MAE scoring; run_vcc_eval() calls perturbation.pipeline.predict() directly per gene, bypassing agent/MCP, producing both predictor and naive baseline metric sets (VCC-02 closed)**

## Performance

- **Duration:** 18 min
- **Started:** 2026-09-09T22:19:44Z
- **Completed:** 2026-09-09T22:37:00Z
- **Tasks:** 2 (TDD: RED + GREEN)
- **Files modified:** 2

## Accomplishments

- Introspected real cell_eval.MetricsEvaluator API before writing any code -- confirmed constructor args, compute() return shape (Polars DataFrames), and exact VCC metric column names
- compute_vcc_metrics() wraps MetricsEvaluator.compute(profile="vcc") with stable {mae, pds, des} output, tempdir management, and allow_discrete pass-through
- run_vcc_eval() calls perturbation.pipeline.predict() directly in a plain synchronous loop; assembles adata_real from pseudobulk means + control row to satisfy MetricsEvaluator's validation; returns both predictor and baseline metric dicts
- 10 tests across both functions (TDD), full suite 121 tests green

## Task Commits

1. **TDD RED -- failing tests** - `63787b3` (test)
2. **Task 1+2 GREEN -- compute_vcc_metrics + run_vcc_eval** - `275783a` (feat)

**Plan metadata:** (this commit)

_Note: TDD produced RED commit then GREEN commit; Tasks 1 and 2 implemented together in the GREEN phase since Task 2 depends directly on Task 1's function_

## Files Created/Modified

- `benchmark/vcc_eval.py` - compute_vcc_metrics() wrapping MetricsEvaluator; run_vcc_eval() direct-call harness producing predictor + baseline metric sets
- `tests/test_vcc_eval.py` - 10 tests: identical-data MAE~0/PDS=1.0, corrupted MAE meaningfully higher, run_vcc_eval fixture round-trip

## Decisions Made

- cell_eval.MetricsEvaluator.compute(profile='vcc') returns (results, agg_results) as Polars DataFrames (not a dict as sketched in 05-RESEARCH.md). compute_vcc_metrics() reads per-perturbation results DataFrame and takes column means to produce one scalar per metric.
- Both adata_pred and adata_real must include a control row in obs[pert_col]; run_vcc_eval() builds this by computing ctrl_mean from the stored dataset and prepending it to all three assembled AnnData objects.
- MetricsEvaluator constructor's pert_col default is "target" (not "target_gene"); our wrapper always passes pert_col explicitly to avoid the mismatch.
- allow_discrete=True required for raw integer count AnnDatas; passed as an explicit parameter with False default to match real VCC data behaviour.

## Deviations from Plan

None - plan executed exactly as written. The research note "VERIFY against the actually-installed cell-eval package" was followed (introspected before coding), confirming the Polars DataFrame return type that 05-RESEARCH.md described as a sketch rather than a guarantee.

## Issues Encountered

- First test run of the manual introspection revealed that MetricsEvaluator raises ValueError if control label is absent from adata_real -- the plan's interface section did not explicitly call this out. Handled by design (both adata_pred and adata_real include a control row), documented in module docstring and test file header.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- benchmark/vcc_eval.compute_vcc_metrics and run_vcc_eval are ready for Plan 05-05 to import
- Plan 05-05 (build_benchmark_report/run_full_benchmark) can call run_vcc_eval() with a real dataset name and a list of target genes, then pass both metric dicts to the report builder
- No blockers

---
*Phase: 05-perturbation-response-tool-vcc-benchmark-harness*
*Completed: 2026-09-09*
