---
phase: 1
slug: ingest-qc-pipeline
status: approved
nyquist_compliant: true
wave_0_complete: false
created: 2026-09-03
---

# Phase 1 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest (current) — no test framework exists yet in this greenfield repo |
| **Config file** | none — Wave 0 installs |
| **Quick run command** | `pytest tests/ -x -q` |
| **Full suite command** | `pytest tests/ -q` |
| **Estimated runtime** | ~30 seconds |

---

## Sampling Rate

- **After every task commit:** Run `pytest tests/ -x -q`
- **After every plan wave:** Run `pytest tests/ -q`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 30 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 01-02-INGEST-01 | 01-02 | 1 | INGEST-01 | unit | `uv run pytest tests/test_loaders.py::test_load_mtx_dir -x` / `::test_load_h5 -x` | ❌ W0 | ⬜ pending |
| 01-02-INGEST-02 | 01-02 | 1 | INGEST-02 | unit | `uv run pytest tests/test_ingest_contract.py::test_counts_immutable_after_normalize -x` | ❌ W0 | ⬜ pending |
| 01-04-INGEST-03 | 01-04 | 1 | INGEST-03 | unit | `uv run pytest tests/test_store.py::test_save_load_roundtrip -x` / `::test_versioning -x` | ❌ W0 | ⬜ pending |
| 01-03-QC-01 | 01-03 | 1 | QC-01 | unit | `uv run pytest tests/test_qc.py::test_qc_metrics_present -x` | ❌ W0 | ⬜ pending |
| 01-03-QC-02 | 01-03 | 1 | QC-02 | unit | `uv run pytest tests/test_qc.py::test_qc_config_logged -x` / `::test_threshold_changes_filtering -x` | ❌ W0 | ⬜ pending |
| 01-05-ALL | 01-05 | 2 | INGEST-01/02/03, QC-01/02 (integration) | unit | `uv run pytest tests/test_pipeline.py -x` | ❌ W0 | ⬜ pending |

Wave 0 (`01-01`): test infra + synthetic 10x fixtures — no requirement IDs of its own, gates all rows above.

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/conftest.py` — synthetic 10x fixture generators: (a) a tiny `.mtx` directory (`matrix.mtx.gz`/`barcodes.tsv.gz`/`features.tsv.gz`, ~10-20 genes × ~30-50 cells, scipy `mmwrite` + gzip) with a few `MT-`-prefixed genes and one deliberately duplicated gene symbol; (b) an equivalent tiny `.h5` file in Cell Ranger's HDF5 feature-barcode-matrix layout. Both must be small, in-repo, and require no network access (do not rely on `sc.datasets.pbmc3k()`, which downloads from the internet on first use).
- [ ] `tests/test_loaders.py`, `tests/test_ingest_contract.py`, `tests/test_qc.py`, `tests/test_store.py` — new files, covering INGEST-01/02/03, QC-01/02.
- [ ] `pyproject.toml` or `pytest.ini` — minimal pytest config (test discovery paths); none exists yet in this greenfield repo.
- [ ] Framework install: `uv pip install -D pytest`.

---

## Manual-Only Verifications

*None — all Phase 1 behaviors have automated verification (deterministic, CPU-only, no agent/LLM involvement).*

---

## Edge Cases to Explicitly Test

- **Empty result after filtering:** a `QCConfig` with an implausibly strict `min_genes_per_cell` (e.g., 100000) that filters out every cell — pipeline should not crash; should return a 0-`n_obs` AnnData with the filtering report showing 100% removed, not silently succeed with misleading downstream state. Verify the pipeline either raises a clear, typed error or returns an explicitly empty-but-valid dataset (planner should decide which; either is acceptable, but it must be intentional, not an unhandled exception from a downstream `.obs["pct_counts_mt"]` access on an empty frame).
- **All-cells-already-filtered input:** a 10x directory representing a `filtered_feature_bc_matrix` (already cell-called by Cell Ranger) vs. a `raw_feature_bc_matrix` (all barcodes, mostly empty droplets) — both are valid 10x inputs per 10x's own documented output structure; confirm the loader doesn't assume one or the other.
- **Duplicate gene symbols:** confirm `var_names_make_unique()` behavior is tested explicitly (both loader paths), not just implicitly relied upon.
- **Zero-count cell/gene rows:** a synthetic dataset including at least one all-zero cell and one all-zero gene, to confirm `filter_cells`/`filter_genes` behave as expected at the boundary (`min_genes=1` should remove an all-zero cell).
- **Re-ingesting the same source path under the same name:** confirms INGEST-03's versioning increments rather than silently overwriting.

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 30s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
