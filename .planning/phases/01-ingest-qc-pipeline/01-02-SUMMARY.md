---
phase: 01-ingest-qc-pipeline
plan: 02
subsystem: ingest
tags: [scanpy, anndata, scipy-sparse, hashlib, pytest]

# Dependency graph
requires:
  - phase: 01-ingest-qc-pipeline plan 01
    provides: "tests/conftest.py fixtures (tiny_mtx_dir, tiny_h5_file, synthetic_adata)"
provides:
  - "ingest/loaders.py::load(path) -> AnnData: format-detecting 10x .mtx directory / .h5 file loader with var_names deduplication and feature-type-drop logging"
  - "ingest/contract.py::set_counts_layer(adata) / verify_counts_integrity(adata): raw-counts immutability contract (write-lock + sha256 checksum)"
affects: [01-05-pipeline-integration]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "10x ingest: sc.read_10x_mtx(make_unique=True) for directories, sc.read_10x_h5() + explicit adata.var_names_make_unique() for .h5 files (read_10x_h5 does not dedupe automatically)"
    - "Raw-counts immutability: adata.layers['counts'] = adata.X.copy() + freeze buffer (.data.flags.writeable = False for sparse, .flags.writeable = False for dense) + sha256 checksum in adata.uns['counts_checksum'] as a second line of defense against full-array reassignment"
    - "pytest pythonpath = ['.'] in pyproject.toml so first-party packages (ingest/*) are importable by test modules without an editable install"

key-files:
  created:
    - ingest/__init__.py
    - ingest/loaders.py
    - ingest/contract.py
    - tests/test_loaders.py
    - tests/test_ingest_contract.py
  modified:
    - pyproject.toml

key-decisions:
  - "Kept gex_only=True (matches project's scRNA-seq-only v1 scope) but added explicit logging of feature types present and count of non-Gene-Expression features dropped, per Pitfall 4"
  - "For the .mtx-directory path, read feature_types directly from features.tsv.gz to report on dropped non-GEX features, since gex_only=True strips both the rows and the feature_types column before the loader ever sees the resulting AnnData"
  - "verify_counts_integrity() compares full sha256 of the frozen buffer bytes, not a lighter checksum, since this dataset is small and correctness matters more than speed at this contract boundary"

patterns-established:
  - "Pattern: any AnnData transformation step in later phases must call ingest.contract.verify_counts_integrity(adata) at trust boundaries (tool entrypoints) to assert layers['counts'] wasn't silently replaced"

requirements-completed: ["INGEST-01", "INGEST-02"]

# Metrics
duration: 25min
completed: 2026-09-04
---

# Phase 1 Plan 02: 10x Loader & Raw-Counts Immutability Contract Summary

**Format-detecting scanpy loader (`ingest/loaders.py`) for 10x `.mtx`/`.h5` input plus a write-locked + checksummed `adata.layers['counts']` contract (`ingest/contract.py`) that makes raw-count corruption either impossible or provably detectable.**

## Performance

- **Duration:** 25 min
- **Started:** 2026-09-04T14:13:00Z
- **Completed:** 2026-09-04T14:38:40Z
- **Tasks:** 2 completed
- **Files modified:** 6 (ingest/__init__.py, ingest/loaders.py, ingest/contract.py, tests/test_loaders.py, tests/test_ingest_contract.py, pyproject.toml)

## Accomplishments
- `ingest/loaders.py::load()` correctly format-detects a 10x MEX directory vs `.h5` file, dedupes `var_names` on both paths (explicit `var_names_make_unique()` after `read_10x_h5`, since that reader doesn't dedupe automatically), and raises `ValueError` with a descriptive message on nonexistent/unrecognized paths
- Loader logs (via `logging`, not `print`) which feature types were present in the source data and how many non-Gene-Expression features were dropped by the `gex_only=True` default
- `ingest/contract.py::set_counts_layer()` copies `adata.X` into `layers['counts']`, freezes the buffer (raises `ValueError` on direct in-place write attempts), and stores a sha256 checksum
- `verify_counts_integrity()` proves by test that raw counts survive a simulated `normalize_total()` + `log1p()` pipeline step unchanged, and that a hostile full-array reassignment (which bypasses the write-lock) is caught by the checksum
- Full test suite (12 tests across Plan 01-01 + 01-02) green with zero collection errors

## Task Commits

Each task was committed atomically, following TDD (RED → GREEN):

1. **Task 1: Format-detecting 10x loader (INGEST-01)** - `218faf4` (test, RED) → `d75b58f` (feat, GREEN)
2. **Task 2: Raw-counts immutability contract (INGEST-02)** - `63925df` (test, RED) → `7760d50` (feat, GREEN)

**Plan metadata:** (this commit)

_No refactor commits needed — both implementations passed cleanly on first GREEN attempt._

## Files Created/Modified
- `ingest/__init__.py` - Empty, makes `ingest` a package
- `ingest/loaders.py` - `load(path) -> AnnData`, format-detecting 10x loader with feature-type-drop logging
- `ingest/contract.py` - `set_counts_layer(adata)` / `verify_counts_integrity(adata)`, the raw-counts immutability contract
- `tests/test_loaders.py` - Tests for mtx dir load, h5 load, dedup behavior, error paths, feature-type-drop logging
- `tests/test_ingest_contract.py` - Tests for copy semantics, post-normalize immutability, write-lock `ValueError`, checksum-detected hostile reassignment
- `pyproject.toml` - Added `pythonpath = ["."]` to `[tool.pytest.ini_options]`

## Decisions Made
- Kept `gex_only=True` per project scope (scRNA-seq only, no CITE-seq in v1) but made the drop visible via structured logging rather than silent, per Pitfall 4.
- For the `.mtx` directory path, since `gex_only=True` strips the `feature_types` column from the loaded AnnData along with the dropped rows, read `features.tsv.gz` directly to compute what was present/dropped for the log message — avoids re-reading with `gex_only=False` (would double the I/O and defeat the purpose of the default).
- `verify_counts_integrity()` recomputes the full sha256 of the buffer on every call rather than a cheaper hash — correctness over speed at this contract boundary given dataset sizes here are small.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Added `pythonpath = ["."]` to pytest config**
- **Found during:** Task 1 (writing/running `tests/test_loaders.py`)
- **Issue:** `from ingest.loaders import load` failed with `ModuleNotFoundError: No module named 'ingest'`. The project has no `[build-system]`/editable install, and pytest's default "prepend" import mode only adds the test file's own directory (`tests/`) to `sys.path`, not the project root — so the newly created `ingest` package was never importable by any test module, in this plan or the parallel 01-03/01-04 plans.
- **Fix:** Added `pythonpath = ["."]` under `[tool.pytest.ini_options]` in `pyproject.toml`, which makes pytest prepend the project root to `sys.path` before test collection.
- **Files modified:** `pyproject.toml`
- **Verification:** `uv run pytest tests/test_loaders.py::test_load_mtx_dir -x -q` passed after the change; full suite (`uv run pytest tests/ -q`) green (12 passed).
- **Committed in:** `d75b58f` (Task 1 GREEN commit)

---

**Total deviations:** 1 auto-fixed (1 blocking)
**Impact on plan:** Necessary for any `ingest.*` import to work at all, including the parallel 01-03 (`ingest/qc.py`) and 01-04 (`ingest/store.py`) plans' own test suites. Minimal, additive config change — no scope creep, no behavior change to existing passing tests.

## Issues Encountered

None beyond the blocking pytest-import issue documented above (resolved via Rule 3, see Deviations).

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- `ingest/loaders.py::load()` and `ingest/contract.py::set_counts_layer()`/`verify_counts_integrity()` are ready for Plan 01-05 (`ingest/pipeline.py`) to wire together directly per the `<interfaces>` contract: `adata = loaders.load(path)` → `contract.set_counts_layer(adata)` → QC (Plan 01-03) → store (Plan 01-04).
- The `pythonpath = ["."]` pytest config fix benefits the parallel 01-03/01-04 plans as well — their `ingest.qc`/`ingest.store` test imports will resolve the same way.
- No blockers for Wave 1/2 plans.

---
*Phase: 01-ingest-qc-pipeline*
*Completed: 2026-09-04*

## Self-Check: PASSED

All created files verified present on disk (ingest/__init__.py, ingest/loaders.py, ingest/contract.py, tests/test_loaders.py, tests/test_ingest_contract.py, this SUMMARY.md). All task commit hashes (218faf4, d75b58f, 63925df, 7760d50) verified present in git log.
