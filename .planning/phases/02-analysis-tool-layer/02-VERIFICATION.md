---
phase: 02-analysis-tool-layer
verified: 2026-09-05T03:36:13Z
status: passed
score: 4/4 must-haves verified
---

# Phase 2: Analysis Tool Layer Verification Report

**Phase Goal:** Standard scanpy-backed analyses (clustering, differential expression) work as deterministic, typed, agent-callable tools on canonical Phase 1 data — validated standalone, before any agent or GPU dependency exists.
**Verified:** 2026-09-05T03:36:13Z
**Status:** passed
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | Given a QC'd `.h5ad`, normalization, HVG selection, and PCA run as a deterministic prerequisite pipeline step | VERIFIED | `analysis/preprocess.py::preprocess()` runs `sc.pp.normalize_total` -> `sc.pp.log1p` -> `sc.pp.highly_variable_genes` -> `sc.pp.pca` in that exact order (lines 39-55). `tests/test_preprocess.py::test_preprocess_runs_normalize_hvg_pca` and `test_preprocess_deterministic` (fixed `random_state` -> identical `X_pca` via `np.allclose`) both pass. Copy-on-entry (`adata = adata.copy()`, line 37) verified by `test_preprocess_does_not_mutate_input`. |
| 2 | Cells cluster via Leiden (`flavor="igraph"`) and a 2D UMAP embedding is produced for any clustered dataset | VERIFIED | `analysis/cluster.py::cluster()` calls `sc.tl.leiden(..., flavor="igraph", directed=False, n_iterations=2, ...)` (lines 48-55) followed by `sc.tl.umap(...)`. `tests/test_cluster.py::test_cluster_finds_multiple_clusters_and_umap` asserts `>=2` unique Leiden labels and `.obsm["X_umap"].shape == (n_obs, 2)`; `test_cluster_never_passes_directed_true` regression-guards Pitfall 2; `test_cluster_leiden_labels_deterministic` asserts label-list equality across two runs with the same `random_state` (UMAP coordinate exactness deliberately not asserted, per documented upstream nondeterminism). |
| 3 | Differential expression (Wilcoxon rank-sum) between two clusters or conditions returns a ranked gene result | VERIFIED | `analysis/diffexp.py::differential_expression()` calls `sc.tl.rank_genes_groups(..., method="wilcoxon", tie_correct=True, pts=True, corr_method="benjamini-hochberg")`, extracted only via `sc.get.rank_genes_groups_df` (never hand-parsed `uns` arrays). `tests/test_diffexp.py::test_marker_genes_recovered` proves real statistical recovery (>=13/25 top hits are known population-A marker genes, not just "returns something"). `test_generic_over_arbitrary_obs_column` proves genericity over any categorical `.obs` column (not hard-coded to `"leiden"`), satisfying "between two clusters or conditions." |
| 4 | Each analysis tool call returns a bounded, structured summary — not a raw matrix dump — sized for later agent context | VERIFIED | `analysis/summary.py` defines `PreprocessSummary`, `ClusterSummary`, `DEGeneResult`, `DESummary` as the single source of truth for return shapes, each field either a scalar, a `config` dict, or a capped/O(top_n) list (`variance_ratio_top10` <=10, `cluster_sizes` O(n_clusters), `top_genes` capped at `n_genes`). All three low-level modules and `analysis/pipeline.py::analyze()` construct and return these types. Structural-bound tests (`test_preprocess_summary_is_bounded`, `test_cluster_summary_is_bounded`, `test_desummary_is_bounded`) assert no list/dict field scales with `n_cells`/`n_genes_total`. |

**Score:** 4/4 truths verified

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `analysis/summary.py` | 4 bounded dataclasses (`PreprocessSummary`, `ClusterSummary`, `DEGeneResult`, `DESummary`) | VERIFIED | All 4 present, field names match plan `<interfaces>` verbatim; importable (`uv run python -c "from analysis.summary import ..."` confirmed). |
| `tests/conftest.py::structured_adata` | ~200 cells x ~80 genes, two ground-truth populations | VERIFIED | Shape `(200, 80)` confirmed; `true_population` in `{"A","B"}`; marker genes 0-14/15-29 elevated per population; smoke test `test_structured_adata_structure` passes, asserting `mean_a > 2 * mean_b`. |
| `analysis/preprocess.py` | `preprocess(adata, **config) -> (AnnData, PreprocessSummary)` | VERIFIED | Signature matches; 6 tests pass covering order, no-mutation, determinism, small-input guard, summary shape, boundedness. |
| `analysis/cluster.py` | `cluster(adata, **config) -> (AnnData, ClusterSummary)` | VERIFIED | Signature matches; 6 tests pass covering multi-cluster/UMAP, `directed=False` regression, determinism, small-input guard, summary shape, boundedness. |
| `analysis/diffexp.py` | `differential_expression(adata, groupby, group1, group2=None, **config) -> (AnnData, DESummary)` | VERIFIED | Signature matches; 8 tests pass covering marker recovery, `group2=None` equivalence, genericity, param recording, no-mutation, summary shape/capping/boundedness. |
| `analysis/pipeline.py` | `AnalysisConfig` + `analyze(name, version=None, config=None, store_root='data') -> (new_dataset_id, summary_dict)` | VERIFIED | Signature matches; composes `preprocess`/`cluster`/`differential_expression` over `DatasetStore.load/save` with `verify_counts_integrity` checked both post-load and pre-save; 7 integration tests pass. |

### Key Link Verification

| From | To | Via | Status | Details |
|------|-----|-----|--------|---------|
| `analysis/preprocess.py` | `analysis/summary.py:PreprocessSummary` | `from analysis.summary import PreprocessSummary` + constructs it | WIRED | Import present (line 17); constructed and returned (lines 59-72). |
| `analysis/cluster.py` | `analysis/summary.py:ClusterSummary` | `from analysis.summary import ClusterSummary` + constructs it | WIRED | Import present (line 20); constructed and returned (lines 62-73). |
| `analysis/diffexp.py` | `analysis/summary.py:DESummary, DEGeneResult` | `from analysis.summary import ...` + constructs `DESummary` with capped `top_genes` | WIRED | Import present (line 17); `top_df.head(n_genes)` truncation before building `DESummary` (lines 57-80). |
| `analysis/pipeline.py` | `ingest/store.py:DatasetStore.load/save` | `store.load(name, version)` at start, `store.save(name, adata)` at end | WIRED | `store.load` line 78; `store.save` line 135; integration test confirms new version (`demo@2`) created, not overwritten. |
| `analysis/pipeline.py` | `ingest/contract.py:verify_counts_integrity` | called immediately after load AND immediately before save | WIRED | Called line 81 (post-load) and line 128 (pre-save), each raising `RuntimeError` on failure. `test_analyze_counts_integrity_survives_round_trip` confirms the checksum survives the full pipeline + store round-trip. |
| `analysis/pipeline.py` | `analysis/preprocess.py, analysis/cluster.py, analysis/diffexp.py` | composes all three, unpacking `AnalysisConfig` fields | WIRED | `preprocess(...)` line 88, `cluster(...)` line 95, `differential_expression(...)` line 118 (conditional on `config.run_de`), each called with `AnalysisConfig` fields as plain kwargs. |

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|-------------|-------------|--------|----------|
| ANLYS-01 | 02-02, 02-05 | Normalize, select HVGs, compute PCA as a deterministic prerequisite step | SATISFIED | `analysis/preprocess.py` implements exact order; `analysis/pipeline.py::analyze()` composes it end to end. |
| ANLYS-02 | 02-03, 02-05 | Leiden (`flavor="igraph"`) clustering + 2D UMAP embedding | SATISFIED | `analysis/cluster.py` implements with `directed=False` guard; composed in `analyze()`. |
| ANLYS-03 | 02-04, 02-05 | Wilcoxon rank-sum DE between clusters or conditions | SATISFIED | `analysis/diffexp.py` generic over any `.obs` categorical column; marker-gene recovery test proves real statistical correctness. |
| ANLYS-04 | 02-01, 02-02, 02-03, 02-04, 02-05 | Each analysis tool call returns a bounded, structured summary | SATISFIED | `analysis/summary.py` dataclasses used by all modules; boundedness explicitly asserted by dedicated tests in each test file. |

No orphaned requirements: all four ANLYS-01..04 IDs declared in plan frontmatter match REQUIREMENTS.md's Phase 2 mapping exactly (cross-checked against `.planning/REQUIREMENTS.md` lines 23-26, 100-103).

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| — | — | none found | — | Scanned all of `analysis/*.py` for TODO/FIXME/XXX/HACK/PLACEHOLDER, "not implemented", empty returns (`return null`/`return {}`/`return []`/`=> {}`), and bare `pass` bodies — no matches. |

### Human Verification Required

None. All four success criteria are mechanically verifiable via unit/integration tests against real scanpy computations (not mocked), and were independently re-run as part of this verification (not just trusted from SUMMARY.md claims).

### Test Suite Verification (Independent Run)

```
$ uv run pytest tests/ -q
..........................................................               [100%]
58 passed, 7 warnings in 15.72s
```

Matches the SUMMARY.md-claimed count (58 passed) exactly, independently confirmed. Warnings are benign (`UserWarning: Some cells have zero counts` on a normalize_total call against a small edge-case fixture with an intentionally all-zero cell; `Variable names are not unique` from Phase 1 fixture reads) — none indicate broken behavior.

Additionally confirmed:
- `uv run python -c "import igraph"` succeeds (`igraph==1.0.0` installed, `>=0.10.8` constraint in `pyproject.toml` line 8).
- `uv run python -c "from analysis.summary import PreprocessSummary, ClusterSummary, DEGeneResult, DESummary"` succeeds.

### Gaps Summary

No gaps found. All four observable truths, all required artifacts, all key links, and all four ANLYS requirements are verified against actual, executing code — not just SUMMARY.md claims. The phase goal (deterministic, typed, agent-callable scanpy analysis tools validated standalone) is achieved: `analysis/pipeline.py::analyze()` demonstrates the full ANLYS-01→02→(03) chain end to end on top of Phase 1's `DatasetStore`, with the raw-counts immutability contract (Pitfall 6) explicitly closed at both pipeline boundaries, and every returned summary independently verified as bounded (never O(n_cells) or O(n_genes)).

---

*Verified: 2026-09-05T03:36:13Z*
*Verifier: Claude (gsd-verifier)*
