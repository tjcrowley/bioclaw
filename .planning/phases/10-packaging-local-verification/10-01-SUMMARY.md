---
phase: 10-packaging-local-verification
plan: 01
subsystem: testing
tags: [pytest, packaging, docs, fastapi, uv, 10x-genomics]

# Dependency graph
requires:
  - phase: 09-frontend-chat-ui
    provides: "Complete, live-verified webapp (backend + frontend) at webapp/, with the manual 'no OpenClaw import' grep recorded in 09-VERIFICATION.md"
provides:
  - "Automated, always-run regression test enforcing PKG-01's self-containment claim (tests/test_webapp_packaging.py::test_webapp_has_no_openclaw_dependency)"
  - "Standalone demo 10x MEX dataset generator script (scripts/make_sample_dataset.py) for Plan 10-02's manual upload-flow verification"
  - "Documented single command to run the webapp locally, in both README.md and new webapp/README.md"
affects: [10-02, packaging, docs]

# Tech tracking
tech-stack:
  added: []
  patterns: ["Standalone CLI script exposing an importable generate_*(out_dir) function so both a real filesystem run and a pytest smoke test share one code path"]

key-files:
  created:
    - tests/test_webapp_packaging.py
    - scripts/make_sample_dataset.py
    - webapp/README.md
  modified:
    - README.md

key-decisions:
  - "Task 2's test (test_make_sample_dataset_writes_valid_10x_dir) was written into tests/test_webapp_packaging.py in the same commit as Task 1's test, since the file was authored in one pass; the script itself (scripts/make_sample_dataset.py) landed in its own commit"
  - "No __init__.py needed under scripts/ -- pythonpath=[\".\"] plus Python 3 implicit namespace packages already resolve `from scripts.make_sample_dataset import generate_sample_dataset` in pytest, confirmed empirically before adding one unnecessarily"

patterns-established:
  - "Demo/fixture-generation logic that needs to outlive a single pytest session should be extracted from tests/conftest.py's fixture into a plain, importable generate_*(out_dir) function usable both as a CLI script and from a test smoke-check"

requirements-completed: [PKG-01, PKG-02]

# Metrics
duration: 4min
completed: 2026-09-13
---

# Phase 10 Plan 01: Automated Self-Containment Test, Demo Dataset Script, Run Docs Summary

**Added a permanent pytest guard against OpenClaw references in webapp/, a standalone 10x MEX demo-dataset generator script, and documented the exact single command to run the bioclaw webapp locally in both README.md and a new webapp/README.md.**

## Performance

- **Duration:** ~4 min
- **Started:** 2026-09-13T18:10:00-07:00 (approx)
- **Completed:** 2026-09-13T18:14:18-07:00
- **Tasks:** 3 completed
- **Files modified:** 4 (3 created, 1 modified)

## Accomplishments
- Promoted the one-time manual "no OpenClaw import" grep (from 09-VERIFICATION.md) into a durable, always-run pytest test (`tests/test_webapp_packaging.py::test_webapp_has_no_openclaw_dependency`) that walks every `.py`/`.js`/`.html`/`.css` file under `webapp/` and fails on any future regression.
- Built `scripts/make_sample_dataset.py`, a standalone CLI generating a synthetic 300-gene x 60-cell 10x MEX dataset (two marker-gene pseudo populations) to `data/demo_10x/` by default, with `--out`/`--force` flags and a reusable `generate_sample_dataset(out_dir)` function -- unblocks Plan 10-02's manual upload verification without requiring a private test file.
- Documented the single command to run the webapp: a new "Web UI" section in root `README.md` linking to a new `webapp/README.md`, which covers prerequisites, one-time setup, the exact run command, the `/app` URL (explicitly not `/`), the single-worker constraint, and the demo-dataset generator.

## Task Commits

Each task was committed atomically:

1. **Task 1: Automated no-OpenClaw-dependency regression test** - `5846a9b` (test)
2. **Task 2: Demo dataset generator script** - `ed305f9` (feat)
3. **Task 3: Document the single run command in README.md and webapp/README.md** - `6719163` (docs)

**Plan metadata:** pending (docs: complete plan)

## Files Created/Modified
- `tests/test_webapp_packaging.py` - New module: `test_webapp_has_no_openclaw_dependency` (PKG-01 durability) + `test_make_sample_dataset_writes_valid_10x_dir` (Task 2 smoke test)
- `scripts/make_sample_dataset.py` - Standalone CLI + importable `generate_sample_dataset(out_dir)`, writes a synthetic 10x MEX dataset to `data/demo_10x/` by default
- `README.md` - New "Web UI (v1.1)" section (after "Status") with quick-start command and link to `webapp/README.md`
- `webapp/README.md` - New file: what-this-is, prerequisites, setup, exact run command, `/app` URL, single-worker constraint, demo-dataset generation, local-only scope note

## Decisions Made
- Wrote both tests in `tests/test_webapp_packaging.py` in a single pass (Task 1's commit), since the module was authored as one file; Task 2's actual deliverable commit is the script itself. No functional deviation from the plan -- both tests specified in the plan exist and pass.
- Confirmed empirically (per the plan's own instruction) that `scripts/` does not need an `__init__.py` for `from scripts.make_sample_dataset import generate_sample_dataset` to resolve under this project's `pythonpath = ["."]` pytest config -- Python's implicit namespace packages already cover it.

## Deviations from Plan

None - plan executed exactly as written. (Minor commit-grouping note above: Task 2's new test landed in Task 1's commit since both were part of the same file write; the script deliverable itself has its own dedicated commit.)

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- `tests/test_webapp_packaging.py` and `scripts/make_sample_dataset.py` are both in place and passing, closing the two open items (PKG-01 durability gap, demo dataset generation) that Plan 10-02's clean-checkout dry run and combined manual checkpoint depend on.
- Full fast-tier suite confirmed green: `uv run --extra web pytest tests/ -x -q -m "not live_llm and not bio_fm_smoke and not vcc_data"` -> 210 passed, 6 deselected, 0 failed (208 baseline + 2 new tests, zero regressions).
- Root `README.md` and `webapp/README.md` now give a fresh reader the single command to run the webapp without consulting `.planning/`.
- No blockers for Plan 10-02.

---
*Phase: 10-packaging-local-verification*
*Completed: 2026-09-13*

## Self-Check: PASSED

All created files and referenced commit hashes verified present.
