---
phase: 13-real-fm-inference-scgpt-then-geneformer
plan: 01
subsystem: bio-fm
tags: [scgpt, knn, confidence, cell-type-annotation, numpy]

# Dependency graph
requires:
  - phase: 04
    provides: bio_fm_worker/run_scgpt_embed.py subprocess shim and annotation/fm_client.py boundary (top-1 cosine confidence baseline)
provides:
  - _match_and_aggregate() now computes confidence as a k-NN vote fraction (majority-label neighbor count / k) instead of top-1 cosine similarity
  - Unit tests proving the k-NN vote-fraction result diverges from a top-1-cosine-similarity result on a synthetic disagreement case
  - Confirmed real, unmocked bio_fm_smoke integration test still passes end-to-end against the modified worker script
affects: [14-dockerization]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "k-NN vote-fraction confidence: np.argpartition(-sims, kth=k-1, axis=1)[:, :k] per query cell, majority label among k neighbors, confidence = count(majority)/k, k clamped to min(k, reference size)"

key-files:
  created: []
  modified:
    - bio_fm_worker/run_scgpt_embed.py
    - tests/test_annotation_fm_client.py

key-decisions:
  - "k defaults to 15 with no change to main()'s call site or AnnotationCall schema — confidence stays a float in [0,1], only the underlying computation changed"
  - "k is clamped to min(k, reference embedding count) to avoid crashing on small reference sets, verified by a dedicated unit test"

patterns-established:
  - "k-NN vote-fraction confidence (same technique as scArches WKNN label transfer / popV consensus voting) is the standard replacement for top-1 cosine similarity confidence in FM annotation call aggregation"

requirements-completed: ["FM-01"]

# Metrics
duration: 3min
completed: 2026-09-17
---

# Phase 13 Plan 01: k-NN Vote-Fraction Confidence for scGPT Annotation Summary

**Replaced `_match_and_aggregate()`'s top-1 cosine-similarity confidence with a k-NN (k=15) vote-fraction confidence, verified against the real, unmocked scGPT checkpoint end-to-end.**

## Performance

- **Duration:** 3 min (Task 1 implementation + test), plus a separate real-checkpoint verification run of 19.76s
- **Started:** 2026-09-17T11:38:41-07:00
- **Completed:** 2026-09-17T19:04:48Z
- **Tasks:** 2 completed (1 code task, 1 verification-only checkpoint)
- **Files modified:** 2

## Accomplishments
- `_match_and_aggregate()` now computes confidence as a k-NN vote fraction (count of majority-label neighbors among each query cell's k nearest reference neighbors, divided by k), matching FM-01's explicit requirement and the technique used by scArches' WKNN label-transfer classifier and popV's consensus voting.
- Two new fast-tier unit tests prove the behavior change without requiring the real isolated environment or checkpoint: one demonstrates the k-NN majority vote overriding what a top-1 cosine-similarity implementation would have returned, the other proves `k` is safely clamped to the reference size.
- The real, unmocked `bio_fm_smoke` integration test was re-run against the modified worker script and confirmed passing: `annotate_cell_type_tool` real end-to-end latency 7.7s, all `fm_calls` entries had non-empty label/ontology_term_id and confidence in `[0, 1]`, ORA baseline also populated.

## Task Commits

Each task was committed atomically:

1. **Task 1: k-NN vote-fraction confidence in `_match_and_aggregate()`** - `db1f761` (test, RED), `f1b2026` (feat, GREEN)
2. **Task 2: Verify real scGPT smoke test still passes with the new confidence metric** - checkpoint verification only, no code changes; confirmed via `uv run pytest tests/test_bio_fm_integration.py -m bio_fm_smoke -x -v -s` (1 passed in 19.76s)

**Plan metadata:** (this commit)

_Note: Task 1 followed TDD (test → feat); Task 2 was a human-verify checkpoint requiring no additional commits._

## Files Created/Modified
- `bio_fm_worker/run_scgpt_embed.py` - `_match_and_aggregate()` gained a `k: int = 15` parameter; replaced `sims.argmax(axis=1)` top-1 logic with per-query-cell `np.argpartition`-based k-NN majority vote and vote-fraction confidence; k is clamped to `min(k, reference embedding count)`; per-cluster aggregation logic (majority label, mean confidence among agreeing cells, majority label's ontology id) unchanged
- `tests/test_annotation_fm_client.py` - Added `test_match_and_aggregate_uses_knn_vote_fraction_not_top1` (synthetic case proving majority-of-5-neighbors vote of 0.8 confidence for "T cell" overrides the top-1 nearest neighbor's "Monocyte" match) and `test_match_and_aggregate_clamps_k_to_reference_size` (2-cell reference, default k=15, confirms no crash and confidence 1.0)

## Decisions Made
- `k` defaults to 15 and is a new optional parameter — `main()`'s existing call site (`_match_and_aggregate(query, query_embed, reference, reference_embed, reference_dataset)`) required no changes.
- No schema change to `AnnotationCall` — confidence remains a `float` in `[0.0, 1.0]`, only the computation method changed from top-1 cosine similarity to k-NN vote fraction.

## Deviations from Plan

None - plan executed exactly as written. The live `scgpt.tasks.embed_data()` API re-verification step (per the task's `<behavior>` instructions) confirmed no drift from 13-RESEARCH.md Pattern 2's already-documented signature.

## Issues Encountered
None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness
- FM-01 is now genuinely complete: real scGPT inference with k-NN vote-fraction confidence, verified end-to-end against the real, gitignored checkpoint.
- 13-02 (Geneformer foundation) is already complete in parallel; 13-03 and 13-04 remain to build the actual Geneformer inference pipeline (FM-02) on top of the validated subprocess pattern this plan reused.

---
*Phase: 13-real-fm-inference-scgpt-then-geneformer*
*Completed: 2026-09-17*

## Self-Check: PASSED

- FOUND: bio_fm_worker/run_scgpt_embed.py
- FOUND: tests/test_annotation_fm_client.py
- FOUND: .planning/phases/13-real-fm-inference-scgpt-then-geneformer/13-01-SUMMARY.md
- FOUND: db1f761 (test commit)
- FOUND: f1b2026 (feat commit)
