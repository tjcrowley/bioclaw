---
phase: 05-perturbation-response-tool-vcc-benchmark-harness
plan: "01"
subsystem: perturbation-infrastructure
tags: [cell-eval, perturbation, benchmark, vcc, ingest, tdd]
dependency_graph:
  requires: []
  provides: [cell-eval-install, vcc_data-marker, perturbation-package, benchmark-package, PerturbationCall, PerturbationSummary, perturbation_adata-fixture, h5ad-ingest]
  affects: [pyproject.toml, ingest/loaders.py, tests/conftest.py]
tech_stack:
  added: [cell-eval==0.8.2, numba-mwu==0.2.0, pdex==0.3.0, polars==1.44.2]
  patterns: [dataclass-per-result-type, tdd-red-green, documented-stub-skeleton]
key_files:
  created:
    - perturbation/__init__.py
    - perturbation/summary.py
    - perturbation/model.py
    - perturbation/baseline.py
    - perturbation/pipeline.py
    - benchmark/__init__.py
    - benchmark/vcc_eval.py
    - benchmark/report.py
  modified:
    - pyproject.toml
    - ingest/loaders.py
    - tests/conftest.py
    - tests/test_loaders.py
decisions:
  - "cell-eval installed with no torch dependency (confirmed via uv.lock grep); isolates cleanly alongside existing Phase 1-4 stack"
  - "PerturbationSummary uses single model_call/baseline_call (not lists) because PERT-01 predicts one target gene per call -- mirrors annotation/summary.py's dataclass convention but with different bounding semantics"
  - ".h5ad branch in load() has no var_names_make_unique() call: a well-formed .h5ad already has valid var_names, unlike raw 10x .h5/.mtx formats"
  - "perturbation_adata fixture uses +10 shift only on the target gene's own index so Plans 02/03 tests can assert per-gene discrimination (mean ~12 in perturbed cells vs ~2 in controls)"
metrics:
  duration: "~6 min (339 seconds)"
  completed: "2026-09-09"
  tasks_completed: 3
  files_modified: 4
  files_created: 8
---

# Phase 5 Plan 01: Infrastructure Setup (cell-eval, perturbation/benchmark packages, VCC-01) Summary

**One-liner:** cell-eval installed torch-free, PerturbationCall/PerturbationSummary contracts fixed, perturbation/ and benchmark/ package skeletons created, perturbation_adata fixture added, and .h5ad ingest branch added to close VCC-01.

## What Was Built

**Task 1 (cell-eval + vcc_data marker):** `cell-eval>=0.8.2` added to project dependencies via `uv add` with zero torch resolution (confirmed via uv.lock). Three markers now registered: `live_llm`, `bio_fm_smoke`, `vcc_data` -- all three fast-tier excludable via `-m "not live_llm and not bio_fm_smoke and not vcc_data"`.

**Task 2 (package skeletons + contracts + fixture):** `perturbation/` and `benchmark/` created as real Python packages. `perturbation/summary.py` implements the `PerturbationCall`/`PerturbationSummary` dataclass contract verbatim (one target gene per call, `model_call`/`baseline_call` scalars). Five stub modules (`model.py`, `baseline.py`, `pipeline.py`, `vcc_eval.py`, `report.py`) created with docstrings pointing each downstream plan to the right module path and implementation note. `perturbation_adata` fixture added to `tests/conftest.py` (seed 4, 30 genes x 350 cells: 100 non-targeting controls + 5 perturbations x 50 cells, each with +10 shift on its own gene index).

**Task 3 (VCC-01, TDD):** `.h5ad` branch added to `ingest/loaders.py::load()` before the `ValueError` fallback. Dispatches to `sc.read_h5ad()` directly. No bespoke ingest path -- `ingest_10x` pipeline already operates on `.X` regardless of format. Test `test_load_h5ad` added via TDD (RED commit `5ecb624`, GREEN commit `ac11536`).

## Verification Results

```
uv run pytest tests/ -q -m "not live_llm and not bio_fm_smoke and not vcc_data"
99 passed, 2 deselected, 7 warnings in 19.23s
```

```
uv run python -c "import cell_eval, perturbation, benchmark"
# OK -- no errors
```

## Commits

| Task | Commit | Message |
|------|--------|---------|
| Task 1 | 646daba | chore(05-01): install cell-eval and register vcc_data pytest marker |
| Task 2 | bd89a0c | feat(05-01): perturbation/ and benchmark/ package skeletons plus contracts |
| Task 3 RED | 5ecb624 | test(05-01): add failing test_load_h5ad for VCC-01 .h5ad ingest branch |
| Task 3 GREEN | ac11536 | feat(05-01): VCC-01 -- add .h5ad branch to ingest/loaders.py::load() |

## Deviations from Plan

None - plan executed exactly as written.

## Requirements Closed

- **VCC-01:** `.h5ad` file ingests through the existing `ingest_10x` pipeline with no bespoke ingest path.
