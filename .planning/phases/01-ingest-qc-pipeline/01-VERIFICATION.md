---
phase: 01-ingest-qc-pipeline
verified: 2026-09-04T15:17:04Z
status: passed
score: 8/8 must-haves verified
---

# Phase 1: Ingest + QC Pipeline Verification Report

**Phase Goal:** Raw 10x Genomics single-cell output becomes canonical, versioned `.h5ad` data with an immutable raw-counts contract and logged, explicit QC — the trustworthy foundation every later phase depends on.
**Verified:** 2026-09-04T15:17:04Z
**Status:** passed
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths

(Aggregated `must_haves.truths` across all 5 plan frontmatters, deduplicated against ROADMAP.md Success Criteria)

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | Test infra: `uv run pytest tests/ -q` runs cleanly, synthetic 10x fixtures are valid, network-free | ✓ VERIFIED | `uv run pytest tests/ -q` → `30 passed, 4 warnings in 5.98s`, zero collection errors. No `sc.datasets.*` calls anywhere in `ingest/` or `tests/`. |
| 2 | Researcher can point loader at a `.mtx` dir or `.h5` file and get back a valid AnnData with correct n_obs/n_vars and deduplicated var_names | ✓ VERIFIED | `ingest/loaders.py::load()` format-detects dir vs `.h5`, calls `var_names_make_unique()` explicitly on the h5 path (Pitfall 5). `tests/test_loaders.py` (5 tests) and `tests/test_pipeline.py::test_ingest_10x_h5_end_to_end` all pass. |
| 3 | `adata.layers['counts']` set at load time, before normalization, stays bit-for-bit unchanged through later normalization | ✓ VERIFIED | `ingest/contract.py::set_counts_layer()` copies `.X`, freezes buffer (`writeable=False`), stores sha256 checksum. `test_counts_immutable_after_normalize` runs `sc.pp.normalize_total` + `log1p` then asserts array equality + `verify_counts_integrity() is True`. Direct-write test confirms `ValueError` on mutation attempt; hostile full-array reassignment test confirms checksum catches what write-lock alone cannot. |
| 4 | Standard QC metrics (mito %, doublet score, low-count/gene filtering) computed for any ingested dataset | ✓ VERIFIED | `ingest/qc.py::run()` adds `pct_counts_mt`, `n_genes_by_counts`, `total_counts`, `doublet_score`, `predicted_doublet` to `.obs`, all non-null (test asserts `.notna().all()`). Scrublet doublet detection wired with small-dataset PCA-component fallback. |
| 5 | QC thresholds explicit (typed config, not hard-coded) and logged so a researcher can see what was filtered and why | ✓ VERIFIED | `QCConfig` dataclass (no inline hard-coded thresholds in function body). `adata.uns['qc']` written every run with `config`, `n_cells_before`, `n_cells_after`, `removed_by_reason` (per-reason breakdown). `test_threshold_changes_filtering` proves changing `min_genes_per_cell`/`max_pct_mt` between two `run()` calls changes `n_cells_after` and the specific `removed_by_reason` entry — thresholds are live, not hard-coded. |
| 6 | A named, versioned dataset persists in a store later phases can reference by name | ✓ VERIFIED | `ingest/store.py::DatasetStore` — filesystem `.h5ad` + SQLite registry. `test_versioning` proves repeat `save()` increments version (1→2) without overwriting; `test_save_load_roundtrip` proves values round-trip exactly; `list()` proves metadata (source_path, qc_config, created_at) is queryable and JSON round-trips. |
| 7 | Researcher can point ingest pipeline at a `.mtx`/`.h5` directory and get back a valid canonical `.h5ad` in one call | ✓ VERIFIED | `ingest/pipeline.py::ingest_10x(path, name, qc_config=None, store_root="data")` wires `loaders.load → contract.set_counts_layer → qc.run → store.save` in sequence, returns `"{name}@{version}"`. `test_ingest_10x_mtx_end_to_end` and `test_ingest_10x_h5_end_to_end` both pass for both input formats. |
| 8 | Re-ingesting the same source path under the same name produces a new version, not a silent overwrite | ✓ VERIFIED | `test_reingest_same_name_versions` calls `ingest_10x()` twice on the same `tiny_mtx_dir`/name, asserts `"demo@1"` then `"demo@2"`. |

**Score:** 8/8 truths verified

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `pyproject.toml` | Python 3.12+, scanpy/anndata/pytest deps, pytest config | ✓ VERIFIED | `requires-python = ">=3.12"`, `scanpy[scrublet]>=1.12`, `anndata>=0.13`, dev group `pytest>=8`, `[tool.pytest.ini_options] testpaths = ["tests"]`. `.venv/` confirmed in `.gitignore`. |
| `tests/conftest.py` | `tiny_mtx_dir`, `tiny_h5_file`, `synthetic_adata` fixtures | ✓ VERIFIED (156 lines) | All three fixtures present, used across every downstream test file. |
| `ingest/loaders.py` | `load(path) -> AnnData`, format-detecting loader | ✓ VERIFIED (107 lines) | Handles `.mtx` dir and `.h5`, raises `ValueError` on bad input, logs feature-type drops via `logging` module (Pitfall 4). |
| `ingest/contract.py` | `set_counts_layer`, `verify_counts_integrity` | ✓ VERIFIED (59 lines) | Copy + write-freeze + sha256 checksum, both sparse and dense code paths handled. |
| `ingest/qc.py` | `QCConfig` dataclass + `run(adata, cfg) -> AnnData` | ✓ VERIFIED (132 lines) | Metrics, filtering, `adata.uns['qc']` audit log, empty-result edge case guarded (no crash on 0-obs). |
| `ingest/store.py` | `DatasetStore`: save/load/list, filesystem + SQLite | ✓ VERIFIED (150 lines) | `CREATE TABLE IF NOT EXISTS datasets`, versioning via `MAX(version)+1`, JSON round-trip for `qc_config`. |
| `ingest/pipeline.py` | `ingest_10x(path, name, qc_config=None) -> dataset_id` | ✓ VERIFIED (56 lines) | Single coarse-grained entrypoint, wires all four modules in documented order, re-freezes counts contract post-QC-subsetting with an explicit rationale comment. |

### Key Link Verification

| From | To | Via | Status | Details |
|------|-----|-----|--------|---------|
| `tests/test_fixtures.py` | `tests/conftest.py` | pytest fixture injection | ✓ WIRED | Fixture-parametrized tests exist and pass for all three fixtures. |
| `ingest/contract.py:set_counts_layer` | `adata.layers['counts']` | `.X.copy()` + `writeable=False` + sha256 in `uns['counts_checksum']` | ✓ WIRED | `adata.layers["counts"] = adata.X.copy()` at contract.py:40; writeable-flag freeze + checksum both present. |
| `ingest/qc.py:run` | `adata.uns['qc']` | resolved config + before/after + removed_by_reason | ✓ WIRED | `adata.uns["qc"] = {...}` at qc.py:126, written unconditionally every call including the 0-obs edge case. |
| `ingest/store.py:DatasetStore.save` | `data/registry.sqlite` | SQLite INSERT | ✓ WIRED | `INSERT INTO datasets (...)` at store.py:83, executed inside `save()`. |
| `ingest/pipeline.py:ingest_10x` | `ingest/loaders.py:load` | `adata = loaders.load(path)` | ✓ WIRED | pipeline.py:34. |
| `ingest/pipeline.py:ingest_10x` | `ingest/contract.py:set_counts_layer` | called immediately after load(), before qc.run() | ✓ WIRED | pipeline.py:35 (immediately post-load) and pipeline.py:49 (re-frozen post-QC-subsetting, documented rationale — QC filtering changes shape, not values). |
| `ingest/pipeline.py:ingest_10x` | `ingest/qc.py:run` | `adata = qc.run(adata, qc_config)` | ✓ WIRED | pipeline.py:38. |
| `ingest/pipeline.py:ingest_10x` | `ingest/store.py:DatasetStore.save` | `store.save(name, adata, source_path=path, qc_config=qc_config)` | ✓ WIRED | pipeline.py:52. |

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|-------------|-------------|--------|----------|
| INGEST-01 | 01-02, 01-05 | Ingest standard 10x `.mtx`/`.h5` output, normalize to canonical AnnData | ✓ SATISFIED | `ingest/loaders.py::load()` + integration tests in `test_pipeline.py`. |
| INGEST-02 | 01-02, 01-05 | Raw counts persisted to immutable `adata.layers['counts']` at load time, before normalization | ✓ SATISFIED | `ingest/contract.py`; write-lock + checksum both tested directly and through a `normalize_total`/`log1p` mutation scenario. |
| INGEST-03 | 01-04, 01-05 | Canonical datasets stored in a versioned dataset store, referenceable by name | ✓ SATISFIED | `ingest/store.py::DatasetStore`; versioning and metadata query both tested. |
| QC-01 | 01-03, 01-05 | Standard QC metrics computed (mito %, doublet score, low-count/gene filtering) | ✓ SATISFIED | `ingest/qc.py::run()`; all 5 QC columns proven non-null. |
| QC-02 | 01-03, 01-05 | QC thresholds explicit and logged per run, not hard-coded | ✓ SATISFIED | `QCConfig` dataclass + `adata.uns['qc']` audit dict; live-parameter behavior proven by test. |

No orphaned requirements — REQUIREMENTS.md maps exactly these 5 IDs to Phase 1, and every ID appears in at least one plan's `requirements` frontmatter field (01-02: INGEST-01/02; 01-03: QC-01/02; 01-04: INGEST-03; 01-05: all five, at integration level).

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| — | — | None found | — | Scanned all of `ingest/*.py` and `tests/*.py` for TODO/FIXME/XXX/HACK/PLACEHOLDER, empty implementations (`return null`/`{}`/`[]`, `=> {}`), and console.log-only bodies. Zero hits. All modules are substantive, non-stub implementations with genuine behavior tests. |

### Human Verification Required

None. All Phase 1 must-haves are mechanically verifiable (pure Python/data pipeline, no UI, no external service, no real-time behavior) and are covered by passing automated tests that assert on actual data values, not mocks.

### Gaps Summary

No gaps. All 8 derived observable truths verified, all 7 required artifacts exist and are substantive (not stubs), all 8 key links are wired (imported and actually invoked in the documented sequence), all 5 requirement IDs (INGEST-01/02/03, QC-01/02) have direct implementation and test evidence, and the full Phase 1 test suite (`uv run pytest tests/ -q`) passes with 30/30 tests green and zero collection errors. The one notable design nuance — `contract.set_counts_layer()` is called twice in `ingest/pipeline.py` (once immediately after load, once again after `qc.run()` subsets the AnnData) — is intentional and documented in-line: QC filtering changes cell/gene *count* via slicing (which resets the writeable flag), not the underlying *values*, so re-freezing against the final persisted shape is correct behavior, not a contract violation. This was checked directly against the INGEST-02 requirement text ("stays unchanged through later pipeline steps") and confirmed consistent, since no normalization or value mutation occurs between the two freeze points.

---

_Verified: 2026-09-04T15:17:04Z_
_Verifier: Claude (gsd-verifier)_
