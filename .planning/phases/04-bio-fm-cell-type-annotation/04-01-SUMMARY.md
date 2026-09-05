---
phase: 04-bio-fm-cell-type-annotation
plan: 01
subsystem: infra
tags: [decoupler, pytest, dataclasses, annotation]

# Dependency graph
requires:
  - phase: 02-analysis-tool-layer
    provides: analysis/summary.py's dataclass-per-result-type convention (ClusterSummary precedent)
provides:
  - decoupler installed in the main venv (no torch/scgpt), verified conflict-free against scanpy>=1.12/anndata>=0.13
  - bio_fm_smoke pytest marker registered alongside live_llm
  - annotation/ package skeleton with AnnotationCall/AnnotationSummary dataclass contracts fixed for all downstream plans
affects: [04-02-decoupler-baseline, 04-03-scgpt-fm-client, 04-04-pipeline-composition, 04-05-reference-index-checkpoint-gate]

# Tech tracking
tech-stack:
  added: [decoupler==2.2.0]
  patterns:
    - "Bio-FM isolation boundary: lightweight bio deps (decoupler) go in root pyproject.toml; heavy/torch-dependent deps (scgpt) stay isolated in bio_fm_worker/ venv, never touching root"
    - "annotation/*.py stub convention: module docstring names the exact downstream plan and function that fills it in, so `import annotation.X` succeeds before any real logic lands"

key-files:
  created:
    - annotation/__init__.py
    - annotation/summary.py
    - annotation/baseline.py
    - annotation/fm_client.py
    - annotation/reference.py
    - annotation/pipeline.py
  modified:
    - pyproject.toml
    - uv.lock

key-decisions:
  - "decoupler 2.2.0 installed cleanly via uv add with zero resolver conflicts against the existing scanpy/anndata stack -- confirms 04-RESEARCH.md's HIGH-confidence dependency-footprint finding (anndata, scipy, numba, requests, tqdm, docrep, marsilea, adjusttext, session-info2 -- no torch)."
  - "AnnotationCall/AnnotationSummary transcribed verbatim from the plan's <interfaces> contract (mirroring analysis/summary.py's ClusterSummary precedent), fixing the shared return shape before Plans 02/03/04 write any real logic against it."

patterns-established:
  - "Pattern: annotation/*.py stub files carry only a module docstring naming the plan+function that implements them -- lets downstream plans reference the module path immediately without guessing shape."

requirements-completed: []

# Metrics
duration: ~6min
completed: 2026-09-05
---

# Phase 4 Plan 01: Bio-FM Infrastructure Skeleton Summary

**decoupler 2.2.0 installed torch-free in the main venv, bio_fm_smoke pytest marker registered, and annotation/ package stood up with AnnotationCall/AnnotationSummary dataclass contracts fixed for all Wave 1/2 plans.**

## Performance

- **Duration:** ~6 min
- **Tasks:** 2 completed
- **Files modified:** 8 (pyproject.toml, uv.lock, 6 new annotation/*.py files)

## Accomplishments
- `decoupler` installed via `uv add decoupler` with zero resolver conflicts and no `torch`/`scgpt` introduced into the root `pyproject.toml` -- confirms 04-RESEARCH.md's Isolation Boundary is achievable exactly as researched.
- `bio_fm_smoke` pytest marker registered in `[tool.pytest.ini_options]` alongside the existing `live_llm` marker, giving Phase 4's real-scGPT-inference tests (Plan 04-05) an exclusion path from the fast/default suite before any such test exists.
- `annotation/` package created with `AnnotationCall`/`AnnotationSummary` dataclasses in `summary.py` implemented exactly per 04-RESEARCH.md Pattern 3, and the four remaining modules (`baseline.py`, `fm_client.py`, `reference.py`, `pipeline.py`) present as documented stubs naming their implementing plan.

## Task Commits

Each task was committed atomically:

1. **Task 1: Install decoupler + register bio_fm_smoke pytest marker** - `b314989` (chore)
2. **Task 2: annotation/ package skeleton + AnnotationCall/AnnotationSummary contracts** - `b57ee85` (feat)

**Plan metadata:** (this commit, following SUMMARY.md creation)

## Files Created/Modified
- `pyproject.toml` - Added `decoupler>=2.2.0` dependency; registered `bio_fm_smoke` marker
- `uv.lock` - Updated lockfile for decoupler and its 9 new transitive deps (adjusttext, docrep, marsilea, legendkit, pyarrow, etc.)
- `annotation/__init__.py` - Empty, mirrors `analysis/__init__.py` precedent
- `annotation/summary.py` - `AnnotationCall`/`AnnotationSummary` dataclasses (the shared FM/baseline return-shape contract)
- `annotation/baseline.py` - Stub; Plan 04-02 implements `baseline_annotate()` (decoupler ORA)
- `annotation/fm_client.py` - Stub; Plan 04-03 implements `call_scgpt_annotate()` (subprocess shim to isolated scGPT env)
- `annotation/reference.py` - Stub; Plan 04-05 implements `build_reference_index()` (cellxgene-census reference)
- `annotation/pipeline.py` - Stub; Plan 04-04 implements `annotate()` (composes baseline + fm_client)

## Decisions Made
- `decoupler` installs cleanly alongside the existing Phase 1-3 stack with no version conflicts -- no workaround needed, matching the plan's HIGH-confidence expectation exactly.
- `AnnotationCall`/`AnnotationSummary` fixed verbatim from the plan spec, with `ontology_term_id: str | None` deliberately always `None` on the baseline side and populated only on FM-side calls (per 04-RESEARCH.md's Don't Hand-Roll guidance) -- this asymmetry is documented in `summary.py`'s module docstring so Plans 04-02/03 don't have to re-derive it.

## Deviations from Plan

None - plan executed exactly as written. No resolver conflicts encountered (the plan's contingency instruction to capture and flag a resolver conflict was not triggered).

## Issues Encountered
None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness
- `annotation/` package and its dataclass contracts are stable and importable; Plan 04-02 (decoupler ORA baseline) and Plan 04-03 (scGPT fm_client) can now implement against `AnnotationCall`/`AnnotationSummary` without guessing shape.
- `bio_fm_smoke` marker is live and ready for Plan 04-05's real-checkpoint smoke test to use.
- Full fast test suite (`pytest tests/ -q -m "not live_llm and not bio_fm_smoke"`) verified green: 82 passed, 1 deselected -- no regression from this plan's changes.
- No blockers for Wave 1 (Plans 04-02/04-03, parallel).

---
*Phase: 04-bio-fm-cell-type-annotation*
*Completed: 2026-09-05*

## Self-Check: PASSED

All 6 annotation/*.py files, the SUMMARY.md, and both task commit hashes (b314989, b57ee85) verified present on disk / in git history.
