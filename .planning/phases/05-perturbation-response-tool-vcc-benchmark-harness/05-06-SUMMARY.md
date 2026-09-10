---
phase: 05-perturbation-response-tool-vcc-benchmark-harness
plan: 06
subsystem: testing
tags: [vcc, gcs, benchmark, smoke-test, download]

# Dependency graph
requires:
  - phase: 05-perturbation-response-tool-vcc-benchmark-harness
    provides: run_full_benchmark, compute_vcc_metrics, predict_perturbation_tool, ingest pipeline with .h5ad branch
provides:
  - benchmark/download_vcc.py with download_vcc_split() scripted GCS download attempt
  - tests/test_vcc_smoke.py vcc_data-marked end-to-end smoke test (ready to run once data available)
  - Documented path to run real VCC benchmark verification when GCS billing is available
affects: [06-natural-language-qa-capstone]

# Tech tracking
tech-stack:
  added: [gcsfs (pyproject.toml dev dep for VCC download)]
  patterns: [vcc_data pytest marker gates real-data tests out of CI, mirrors bio_fm_smoke precedent from Phase 4]

key-files:
  created:
    - benchmark/download_vcc.py
    - tests/test_vcc_smoke.py
  modified:
    - pyproject.toml

key-decisions:
  - "Task 3 (real VCC data download + smoke test run) DEFERRED: no GCP billing account available (all projects checked returned billingEnabled=false); smoke test written and gated behind vcc_data marker, ready to run when billing is enabled"
  - "vcc_data marker follows exact precedent of bio_fm_smoke from Phase 4 — excluded from default CI run, requires manual invocation with real infrastructure"

patterns-established:
  - "Phase-gate smoke tests that require authenticated external data sources are marked and deferred, not blocking — document the exact run command so re-enabling is trivial"

requirements-completed: ["VCC-01", "VCC-02", "VCC-03"]

# Metrics
duration: ~5min (summary-only run; tasks 1+2 committed in prior session)
completed: 2026-09-10
---

# Phase 5 Plan 06: VCC Dataset Download + Smoke Test Summary

**Scripted VCC GCS download (benchmark/download_vcc.py) and vcc_data-marked end-to-end smoke test (tests/test_vcc_smoke.py) written and committed; Task 3 real-data run deferred — no GCP billing account available**

## Performance

- **Duration:** ~5 min (summary/state update only; tasks 1+2 executed in prior session 2026-09-09)
- **Started:** 2026-09-09T22:00:00Z (tasks 1-2); 2026-09-10T16:56:09Z (summary)
- **Completed:** 2026-09-10T16:56:09Z
- **Tasks:** 2 of 3 completed (Task 3 deferred)
- **Files modified:** 3

## Accomplishments

- `benchmark/download_vcc.py` implemented: `download_vcc_split(split, out_dir, billing_project)` attempts authenticated GCS download from `gs://arc-institute-virtual-cell-atlas/virtual-cell-challenge/`, catches auth/billing failures cleanly, documents manual recovery steps in module docstring
- `tests/test_vcc_smoke.py` written: `@pytest.mark.vcc_data` end-to-end test wires real downloaded .h5ad through `ingest.loaders.load()` -> DatasetStore -> `benchmark.report.run_full_benchmark()`, asserting real MAE/PDS/DES values returned for both predictor and baseline
- Smoke test excluded from default CI run (verified: `uv run pytest tests/ -q -m "not live_llm and not bio_fm_smoke and not vcc_data"` stays green unchanged from Wave 4)
- Task 3 (human-verify: run real data download + smoke test) formally deferred — GCP billing not available; all GCP projects checked returned `billingEnabled=false`

## Task Commits

1. **Task 1: Scripted VCC dataset download attempt** - `2050f52` (feat)
2. **Task 2: vcc_data-marked end-to-end smoke test** - `5b70118` (feat)
3. **Task 3: Verify real VCC data + smoke test** — DEFERRED (no GCS billing account)

**Plan metadata:** (this summary commit)

## Files Created/Modified

- `benchmark/download_vcc.py` — `download_vcc_split()`: GCS download attempt via gcsfs; documents auth steps and manual re-run command
- `tests/test_vcc_smoke.py` — `@pytest.mark.vcc_data` smoke test: real VCC ingest -> DatasetStore -> `run_full_benchmark()` end-to-end
- `pyproject.toml` — gcsfs added as dev dependency for VCC download

## Decisions Made

- Task 3 deferred due to GCP billing unavailability. All GCP projects in the environment returned `billingEnabled=false`; GCS Requester Pays bucket (`gs://arc-institute-virtual-cell-atlas/virtual-cell-challenge/`) requires an active billing project.
- The smoke test is intentionally kept behind the `vcc_data` marker (not deleted) so re-enabling is a one-command operation once billing is available.
- Requirements VCC-01/02/03 are marked complete: the code path is fully implemented and tested with synthetic fixtures in Plans 05-01 through 05-05; Task 3 represents real-data verification of already-proven logic, not a missing implementation.

## Deviations from Plan

### Deferred Task

**Task 3: human-verify checkpoint — real VCC dataset download + smoke test run**

- **Reason:** No active GCP billing account available. GCS bucket `gs://arc-institute-virtual-cell-atlas/virtual-cell-challenge/` is Requester Pays; all GCP projects checked returned `billingEnabled=false`.
- **User decision:** "defer" — complete the phase without real-data verification.
- **Impact:** VCC-01/02/03 requirements confirmed against synthetic fixtures (Plans 05-01 through 05-05); real-data confirmation pending.
- **To run later:**
  1. Enable GCS billing on a GCP project
  2. Run `gcloud auth login && gcloud config set project <your-billing-project>`
  3. Run `uv run python -c "from benchmark.download_vcc import download_vcc_split; download_vcc_split('test', billing_project='<your-billing-project>')"`
  4. Run `uv run pytest tests/test_vcc_smoke.py -m vcc_data -x -v -s`

---

**Total deviations:** 1 deferred (user-authorized, infrastructure blocker — no auto-fix applicable)
**Impact on plan:** Core implementation complete; real-data verification deferred pending infrastructure availability. No scope creep.

## Issues Encountered

- GCP billing not available in execution environment — all projects returned `billingEnabled=false`. Confirmed via `gcloud billing projects describe` for all available projects. No workaround possible without enabling billing.

## User Setup Required

To run the real-data smoke test when ready:

1. Enable GCS billing on a GCP project
2. Authenticate: `gcloud auth login && gcloud config set project <your-billing-project>`
3. Download data: `uv run python -c "from benchmark.download_vcc import download_vcc_split; download_vcc_split('test', billing_project='<your-billing-project>')"`
4. Run smoke test: `uv run pytest tests/test_vcc_smoke.py -m vcc_data -x -v -s`
5. Report predictor vs. baseline MAE/PDS/DES numbers; check for train/test leakage (suspiciously perfect scores per 05-RESEARCH.md Pitfall 6)

## Next Phase Readiness

- Phase 5 is functionally complete: all perturbation/VCC code paths implemented, unit-tested with synthetic fixtures (Plans 05-01 through 05-05), and gated smoke test written.
- Phase 6 (Natural-Language Q&A Capstone) can proceed — it depends on the perturbation tool's API contract, not on real VCC data verification.
- Real VCC data verification remains as a deferred item; does not block Phase 6 execution.

---
*Phase: 05-perturbation-response-tool-vcc-benchmark-harness*
*Completed: 2026-09-10*
