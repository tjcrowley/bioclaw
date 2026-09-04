# Phase 2: Analysis Tool Layer - Research

**Researched:** 2026-09-04
**Domain:** scanpy-backed single-cell analysis (normalization/HVG/PCA, Leiden clustering, UMAP, Wilcoxon differential expression), composed as deterministic, agent-callable tools on top of Phase 1's `ingest/store.py` `DatasetStore`
**Confidence:** HIGH (API specifics, verified against installed scanpy 1.12.4 source + official docs) / MEDIUM (bounded-summary return-type design, which is original synthesis, not a documented external pattern)

## Summary

Phase 2 has no ambiguity on *which* scanpy calls to use — the phase description already locks the algorithm choices (`normalize_total`/`highly_variable_genes`/`pca`, `leiden(flavor="igraph")`, `umap`, `rank_genes_groups(method="wilcoxon")`). The real planning risk is in three places: (1) two genuinely version-sensitive API gotchas around `flavor="igraph"` (a package that is **not yet a project dependency**, and a `directed` argument that must not be `True`), (2) designing the "bounded, structured summary" return type so it never leaks an `O(n_cells)` or `O(n_genes)` array into what will eventually be an LLM's context window, and (3) a direct recurrence of the Phase 1 immutability-contract pitfall: this project's counts-layer write-lock does **not** survive a `write_h5ad`/`read_h5ad` round-trip (verified empirically below), which matters a great deal once Phase 2 tools start loading datasets back out of `DatasetStore` rather than receiving a freshly-ingested in-memory `AnnData`.

Installed environment already has `scanpy==1.12.4`, `anndata==0.13.3`, and `umap-learn==0.5.12` (a transitive scanpy dependency, sufficient for `sc.tl.umap`). It is **missing** `igraph` (PyPI package `igraph`, imported as `import igraph`), which `sc.tl.leiden(flavor="igraph")` requires and will raise `ImportError` without. `leidenalg` is not required for `flavor="igraph"` and should not be added unless the planner wants an explicit fallback path.

**Primary recommendation:** Build three small, independently-testable, pure(ish) functions (`preprocess`, `cluster`, `differential_expression`) that take/return an in-memory `AnnData` — mirroring Phase 1's "independently-tested Wave 1 modules, composed in a final Wave 2 entrypoint" pattern — plus one coarse-grained orchestration entrypoint (mirroring `ingest_10x`) that loads a named/versioned dataset from `DatasetStore`, runs the pipeline, re-verifies counts integrity, saves the result as a **new store version**, and returns a small bounded summary object referencing that version — never a raw matrix.

## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-------------------|
| ANLYS-01 | Normalize, select HVGs, compute PCA as a deterministic prerequisite step | Verified exact call order/params from official scanpy tutorial + `sc.pp.normalize_total`/`highly_variable_genes`/`pca` signatures (installed 1.12.4). See Architecture Pattern 1, Code Examples. |
| ANLYS-02 | Leiden (`flavor="igraph"`) clustering + 2D UMAP embedding | Verified via scanpy source (`scanpy/tools/_leiden.py`) that `flavor="igraph"` requires `directed=False`/`None` and the separate `igraph` package; confirmed official-tutorial pairing `flavor="igraph", n_iterations=2`. UMAP determinism caveat researched (Pitfall 5). |
| ANLYS-03 | Wilcoxon rank-sum DE between two clusters or conditions | Verified `sc.tl.rank_genes_groups` signature/output fields and `sc.get.rank_genes_groups_df` (built-in bounding via `pval_cutoff`/`log2fc_min`/`log2fc_max`). Generic `groupby`/`groups`/`reference` params support both cluster-vs-cluster and condition-vs-condition (Open Question 3). |
| ANLYS-04 | Bounded, structured summary return (not raw matrix dump) | No external prescriptive standard found for this exact problem (agent-context-sized bioinformatics tool returns) — original design synthesis in Architecture Patterns / "Bounded Summary Design", flagged MEDIUM confidence. |

## Standard Stack

### Core

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|---------------|
| scanpy | 1.12.4 (already pinned `>=1.12` in `pyproject.toml`) | `pp.normalize_total`, `pp.highly_variable_genes`, `pp.pca`, `pp.neighbors`, `tl.leiden`, `tl.umap`, `tl.rank_genes_groups` | De facto standard scRNA-seq analysis toolkit; already the project's chosen ecosystem from Phase 1 |
| anndata | 0.13.3 (already pinned `>=0.13`) | Canonical container Phase 1 already produces | Same container Phase 1 writes/reads |
| igraph | >=0.10.8 (PyPI package name `igraph`, import name `igraph`) | Required backend for `sc.tl.leiden(flavor="igraph")` | Locked by phase description; NOT currently a project dependency — must be added |
| umap-learn | 0.5.12 (already present, transitive via scanpy) | Backing implementation for `sc.tl.umap` | Already installed, no action needed |

### Supporting

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| pandas | already transitive | `sc.get.rank_genes_groups_df()` returns a DataFrame for DE result shaping | Whenever building the bounded DE summary |
| leidenalg | >=0.10.1 (NOT currently installed) | Alternative Leiden backend (`flavor="leidenalg"`) | Only if the planner explicitly wants a fallback/comparison flavor — **not required** by ANLYS-02's locked `flavor="igraph"` wording |
| scikit-misc | not installed | Required only for `highly_variable_genes(flavor="seurat_v3"|"seurat_v3_paper")` | Only if HVG flavor decision changes from the tutorial-standard `seurat` default — see Pitfall 3 |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| `flavor="igraph"` (locked) | `flavor="leidenalg"` | leidenalg is the current *default* when `flavor=None`, but scanpy's own docs/source emit a deprecation-style warning steering users to `igraph` ("orders of magnitude faster"); out of scope since ANLYS-02 already locks `igraph` |
| HVG `flavor="seurat"` (log-normalized input, default) | `flavor="seurat_v3"`/`"seurat_v3_paper"` (raw-count input, needs `scikit-misc`) | `seurat_v3` reorders the pipeline (HVG before normalization) and requires an extra dependency; not what ANLYS-01's wording ("normalizes, selects... genes, and computes PCA," in that order) implies — stick with `seurat` default unless CONTEXT later says otherwise |
| Explicit `sc.pp.scale()` before PCA | Skip scaling, rely on `sc.pp.pca(zero_center=True)`'s built-in mean-centering | The current official scanpy tutorial does **not** show an explicit scale step; ANLYS-01's own wording only lists normalize/HVG/PCA. Recommend omitting `sc.pp.scale()` to match both the requirement text and current official practice — flagged as Claude's Discretion in Open Questions since expert opinion is genuinely split here |

**Installation:**
```bash
uv add "igraph>=0.10.8"
# OR, to pull both igraph and leidenalg together via scanpy's own extra:
# uv add "scanpy[leiden]"
```

## Architecture Patterns

### Recommended Project Structure
```
analysis/
├── __init__.py
├── preprocess.py      # ANLYS-01: normalize_total -> log1p -> HVG -> PCA
├── cluster.py          # ANLYS-02: neighbors -> leiden(igraph) -> umap
├── diffexp.py           # ANLYS-03: rank_genes_groups(wilcoxon) -> bounded DataFrame
├── summary.py           # ANLYS-04: dataclasses for bounded return types
└── pipeline.py           # coarse entrypoint mirroring ingest/pipeline.py::ingest_10x
```
This mirrors `ingest/{loaders,contract,qc,store}.py` + `ingest/pipeline.py`'s existing "independently-tested modules, one coarse composed entrypoint" shape from Phase 1.

### Pattern 1: Prerequisite preprocessing step (ANLYS-01)
**What:** normalize -> log1p -> HVG -> PCA, in the order the official current scanpy tutorial and ANLYS-01's own wording both use.
**When to use:** Always, as the deterministic prerequisite before clustering.
**Example:**
```python
# Source: https://scanpy.readthedocs.io/en/stable/tutorials/basics/clustering.html (verified)
# + signatures confirmed against installed scanpy==1.12.4
import scanpy as sc

def preprocess(adata, *, target_sum=None, n_top_genes=2000, n_pcs=50, random_state=0):
    adata = adata.copy()  # tool-call boundary: don't mutate caller's object
    sc.pp.normalize_total(adata, target_sum=target_sum)  # target_sum=None -> median count
    sc.pp.log1p(adata)
    n_top_genes = min(n_top_genes, adata.n_vars)  # guard for small/test datasets
    sc.pp.highly_variable_genes(adata, n_top_genes=n_top_genes)  # flavor="seurat" default, expects log data
    n_comps = min(n_pcs, adata.n_obs - 1, adata.n_vars - 1)
    sc.pp.pca(adata, n_comps=n_comps, random_state=random_state)  # auto-uses var['highly_variable']
    return adata
```
Note: `sc.pp.pca`'s `mask_var` parameter defaults to an internal sentinel that auto-detects and restricts to `adata.var['highly_variable']` when present — no need to pass it explicitly if `highly_variable_genes` ran first.

### Pattern 2: Cluster + embed (ANLYS-02)
**What:** neighbor graph -> Leiden (igraph backend) -> UMAP.
**When to use:** After Pattern 1's PCA has run.
**Example:**
```python
# Source: scanpy.tl.leiden docstring (installed 1.12.4) + official tutorial
def cluster(adata, *, resolution=1.0, n_neighbors=15, n_pcs=None, random_state=0):
    adata = adata.copy()
    n_neighbors = min(n_neighbors, adata.n_obs - 1)  # guard for small datasets
    sc.pp.neighbors(adata, n_neighbors=n_neighbors, n_pcs=n_pcs, random_state=random_state)
    sc.tl.leiden(
        adata,
        resolution=resolution,
        flavor="igraph",
        n_iterations=2,       # official recommendation paired with flavor="igraph"
        directed=False,        # REQUIRED: flavor="igraph" raises ValueError if directed=True
        random_state=random_state,
    )
    sc.tl.umap(adata, random_state=random_state)
    return adata
```

### Pattern 3: Differential expression (ANLYS-03)
**What:** Wilcoxon rank-sum between two groups, generalized over any categorical `.obs` column (cluster key or condition key).
**When to use:** After a `groupby` column exists (Leiden cluster labels, or any condition/treatment column already in `.obs`).
**Example:**
```python
# Source: scanpy.tl.rank_genes_groups + scanpy.get.rank_genes_groups_df signatures (installed 1.12.4)
def differential_expression(adata, groupby, group1, group2=None, *, n_genes=25, tie_correct=True):
    reference = group2 if group2 is not None else "rest"
    sc.tl.rank_genes_groups(
        adata,
        groupby=groupby,
        groups=[group1],
        reference=reference,
        method="wilcoxon",
        tie_correct=tie_correct,   # default False upstream; correct for tied ranks (common in sparse counts)
        pts=True,                  # adds fraction-of-cells-expressing per group -- cheap, useful for bounded summary
        corr_method="benjamini-hochberg",
    )
    df = sc.get.rank_genes_groups_df(adata, group=group1)  # bounded extraction, not a hand-parsed structured array
    top = df.reindex(df["pvals_adj"].sort_values().index).head(n_genes)
    return top  # shape further into a dataclass -- see "Bounded Summary Design" below
```

### Anti-Patterns to Avoid
- **Returning `adata.obsm['X_umap']` or `adata.obsm['X_pca']` directly from a tool call:** an `n_cells x 2` (or `x n_pcs`) float array scales with dataset size and belongs in the persisted `AnnData`/store, never in the bounded agent-facing return value.
- **Hand-parsing `adata.uns['rank_genes_groups']`'s structured numpy arrays field-by-field:** use `sc.get.rank_genes_groups_df()`, which already exists precisely to avoid this and supports `pval_cutoff`/`log2fc_min`/`log2fc_max` bounding natively.
- **Passing `directed=True` (or any truthy value) to `sc.tl.leiden` with `flavor="igraph"`:** raises `ValueError: Cannot use igraph's leiden implementation with a directed graph.` — confirmed directly in `scanpy/tools/_leiden.py`'s `_validate_flavor`.
- **Mixing HVG flavors with the wrong input state:** `flavor="seurat"` (default) expects log-normalized data; `flavor="seurat_v3"`/`"seurat_v3_paper"` expect raw counts. Running the default flavor on non-log data silently produces a numerically wrong (not erroring) HVG selection.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|--------------|-----|
| Wilcoxon rank-sum test + tie correction across thousands of genes | A per-gene `scipy.stats.mannwhitneyu` loop | `sc.tl.rank_genes_groups(method="wilcoxon", tie_correct=True)` | Scanpy's implementation is vectorized/optimized for sparse count matrices; a naive per-gene loop is slow and tie-correction/multiple-testing-correction is easy to get subtly wrong |
| Leiden community detection | A hand-rolled modularity-optimization graph algorithm | `sc.tl.leiden(flavor="igraph")` | Backed by igraph's C implementation of Traag et al. 2019's algorithm — reimplementing this is a multi-week research effort with correctness risk |
| UMAP manifold learning | A custom dimensionality-reduction routine | `sc.tl.umap` (wraps `umap-learn`) | Well-studied, widely validated implementation; UMAP's own reproducibility caveats (Pitfall 5) already require care even using the standard library — hand-rolling would only add more nondeterminism risk |
| Multiple-testing correction (Benjamini-Hochberg) | A custom p-value correction step | `rank_genes_groups(corr_method="benjamini-hochberg")` (default) | Built in; no reason to reimplement a standard, easy-to-get-wrong statistical correction |
| Extracting/filtering DE results into a bounded table | Manual iteration over `adata.uns['rank_genes_groups']`'s structured arrays | `sc.get.rank_genes_groups_df(group=..., pval_cutoff=..., log2fc_min=...)` | Already does exactly the bounding/filtering ANLYS-04 needs |

**Key insight:** scanpy's `pp`/`tl` layer already wraps every algorithm ANLYS-01 through ANLYS-04 needs with peer-reviewed, C/numba-optimized implementations. The only code Phase 2 should actually write is thin composition (calling these in the right order with the right guards) and result-shaping (bounding/summarizing) — never algorithm reimplementation.

## Common Pitfalls

### Pitfall 1: `igraph` is not yet a project dependency
**What goes wrong:** `sc.tl.leiden(adata, flavor="igraph", ...)` raises `ImportError` (via internal `_utils.ensure_igraph()`) if the `igraph` package isn't installed.
**Why it happens:** `pyproject.toml` currently only lists `scanpy[scrublet]>=1.12` and `anndata>=0.13`; `igraph` is an optional scanpy extra (`scanpy[leiden]` pulls in both `igraph>=0.10.8` and `leidenalg>=0.10.1`), not a base dependency. Verified: neither `igraph` nor `leidenalg` import successfully in the current environment.
**How to avoid:** Add `igraph>=0.10.8` (or the `scanpy[leiden]` extra) to `pyproject.toml` as part of this phase's Wave 0 setup.
**Warning signs:** `ModuleNotFoundError`/`ImportError` the first time any clustering test runs.

### Pitfall 2: `flavor="igraph"` requires `directed=False`
**What goes wrong:** Passing `directed=True` explicitly (or any code path that ends up truthy) raises `ValueError: Cannot use igraph's leiden implementation with a directed graph.`
**Why it happens:** Confirmed directly in installed scanpy source (`scanpy/tools/_leiden.py::_validate_flavor`): `if flavor == "igraph" and directed: raise ValueError(...)`. `directed=None` (the default) is fine — internally the igraph code path always builds an undirected graph (`get_igraph_from_adjacency(adjacency, directed=False)`) regardless.
**How to avoid:** Either omit `directed` entirely or pass `directed=False` explicitly for clarity/self-documentation.
**Warning signs:** `ValueError` at the `sc.tl.leiden` call site, specifically when `flavor="igraph"`.

### Pitfall 3: HVG flavor/input-state mismatch is a silent correctness bug, not a crash
**What goes wrong:** `highly_variable_genes(flavor="seurat")` (the default) expects log-normalized `.X`; running it on raw counts doesn't error, it just silently produces a semantically wrong HVG selection (dispersion stats computed on the wrong scale).
**Why it happens:** scanpy doesn't validate that normalization/log1p already ran before HVG selection under the `seurat` flavor (unlike `seurat_v3`, which has `check_values=True` to catch non-integer input).
**How to avoid:** Always call `sc.pp.normalize_total` + `sc.pp.log1p` immediately before `sc.pp.highly_variable_genes` with the default flavor, matching ANLYS-01's literal wording ("normalizes, selects... genes") and the current official tutorial's order.
**Warning signs:** HVG selection that looks implausible (e.g., dominated by the highest-raw-count genes rather than genes with real biological variance) — worth a sanity-check assertion in Wave 0 tests (e.g., `adata.var['highly_variable'].sum() == min(n_top_genes, n_vars)`).

### Pitfall 4: Small synthetic test fixtures will hit dimensionality guards
**What goes wrong:** `n_top_genes`, `n_comps` (PCA), and `n_neighbors` all have defaults (2000, 50, 15 respectively) sized for real datasets (thousands of cells/genes). Phase 1's existing fixtures (`tiny_mtx_dir`: 18 genes x 40 cells; `synthetic_adata`: 20 genes x 50 cells) will exceed these bounds and can raise solver errors (same class of bug the project already found and fixed once: Scrublet's `n_prin_comps` default crashing on small inputs, see `ingest/qc.py::_run_scrublet` and the 01-03 decision log).
**Why it happens:** scanpy's PCA/neighbors solvers require `n_comps`/`n_neighbors` to be `< min(n_obs, n_vars)`; small test fixtures violate this trivially.
**How to avoid:** Clamp every size-sensitive parameter (`n_top_genes`, `n_pcs`, `n_neighbors`) to `min(requested, n_obs - 1, n_vars - 1)` inside the Phase 2 functions themselves (see Pattern 1/2 code examples above), the same defensive style already established in `ingest/qc.py`. Additionally, Wave 0 should add a richer synthetic fixture (see Wave 0 Gaps below) sized enough to reliably exercise multi-cluster Leiden output without needing extreme clamping.
**Warning signs:** `ValueError` from PCA's SVD solver or from `sklearn`/`pynndescent`'s neighbor search on any fixture-based test.

### Pitfall 5: UMAP's `random_state` does not guarantee bit-exact reproducibility
**What goes wrong:** Even with `random_state` fixed, `umap-learn`'s multi-threaded (numba) optimization phase can introduce nondeterminism across runs due to thread race conditions during the embedding optimization loop.
**Why it happens:** This is a known, still-open upstream issue in `umap-learn` (GitHub issues lmcinnes/umap#1080, #1108): setting `random_state` is documented to force single-threaded execution, but in some code paths `n_jobs` isn't actually forced to 1, so nondeterminism can leak in. MEDIUM confidence — community-reported, not an official "confirmed bug" from the umap-learn maintainers, but consistent across multiple independent reports.
**How to avoid:** Phase 2's determinism goal should be validated on **Leiden cluster assignments** (which are fully deterministic given a fixed `random_state` and the `igraph` backend — no threading ambiguity there) rather than on UMAP's exact `(x, y)` coordinates. Treat the UMAP embedding as reproducible "for visualization/summary purposes" rather than a value asserted byte-for-byte in tests.
**Warning signs:** A UMAP-coordinate equality test that flakes intermittently across CI/local runs despite a fixed seed.

### Pitfall 6: The Phase 1 counts-layer write-lock does NOT survive a store round-trip (direct recurrence risk)
**What goes wrong:** `ingest/contract.py::set_counts_layer()` freezes `adata.layers['counts']`'s underlying buffer (`.data.flags.writeable = False`) at ingest time. This is a **runtime, in-process** protection. It does not persist through `AnnData.write_h5ad()`/`read_h5ad()` — **verified empirically in this environment**: after round-tripping a frozen layer through `.h5ad`, the reloaded buffer's `writeable` flag is back to `True`.
**Why it happens:** The writeable flag is a numpy runtime attribute, not part of the HDF5 serialization format; only the sha256 checksum in `adata.uns['counts_checksum']` (also written by `set_counts_layer`) is actually persisted and checkable after reload.
**How to avoid:** Because every Phase 2 analysis tool that composes with `DatasetStore` will operate on an `AnnData` that has already round-tripped through disk (`DatasetStore.load()` just calls `ad.read_h5ad`, with no re-freeze step), the write-lock is inert by the time Phase 2 code touches it — only `contract.verify_counts_integrity()`'s checksum comparison remains as a **detection** (not prevention) mechanism. Since `normalize_total`/`log1p`/`pca`/`neighbors`/`leiden`/`umap`/`rank_genes_groups` all default to operating on `adata.X` (not `adata.layers['counts']`) and none of them change `n_obs`/`n_vars`, this is safe as long as Phase 2 code never explicitly targets `layer='counts'`. Recommend:
  1. Call `contract.verify_counts_integrity(adata)` immediately after `DatasetStore.load()` at the start of the Phase 2 orchestration entrypoint (defense: prove nothing corrupted at rest).
  2. Call it again immediately before `DatasetStore.save()` at the end (defense: prove the analysis pipeline itself didn't touch counts).
  3. Consider re-freezing (`contract.set_counts_layer`-style write-lock) immediately after `DatasetStore.load()` too, so any *in-process* accidental mutation during the Phase 2 pipeline still raises immediately (fail-fast) rather than only being caught by a checksum comparison at the end.
This directly extends the exact gap Phase 1's own 01-05 plan found and fixed (see `01-05-SUMMARY.md`'s "Re-freeze/re-checksum after QC filtering" decision) — Phase 2 is a second call site with the same underlying property (freeze doesn't survive serialization), just triggered by store round-trips rather than in-place filtering.
**Warning signs:** `verify_counts_integrity()` returning `False` after any Phase 2 pipeline run against a store-loaded dataset; or — more dangerously — no warning at all if a future bug silently writes to `layers['counts']` without anyone calling `verify_counts_integrity()` at the tool boundary.

## Bounded Summary Design (ANLYS-04)

No external prescriptive standard exists for this exact problem (structuring bioinformatics tool returns for LLM agent context budgets) — this section is original synthesis from the general principle **"never return anything whose size scales with `n_cells` or `n_genes`; only return aggregates and top-N tables sized independently of dataset size."** MEDIUM confidence — reasonable given ANLYS-04's own wording, but the planner should treat exact field names/shapes as a starting proposal, not a locked spec.

**General principle:** full per-cell/per-gene arrays (PCA loadings, UMAP coordinates, per-cell cluster labels, full gene rankings) belong in the persisted `AnnData` (`.obs`, `.obsm`, `.uns`) and the versioned store — never in the tool's return value. The tool's return value is a small, `O(1)`-ish object (or `O(n_clusters)`/`O(top_n_genes)` at most) that references the store version plus a handful of aggregate statistics.

Suggested shapes (dataclasses or `TypedDict`, planner's call):

```python
@dataclass
class PreprocessSummary:
    dataset_id: str            # "{name}@{version}" -- points back into the store
    n_cells: int
    n_genes_total: int
    n_hvg: int
    n_pcs_computed: int
    variance_ratio_top10: list[float]   # first 10 PCA components only, not the full array
    config: dict                          # target_sum, n_top_genes, n_pcs, random_state -- logged, mirrors adata.uns['qc']

@dataclass
class ClusterSummary:
    dataset_id: str
    n_clusters: int
    cluster_sizes: dict[str, int]      # {"0": 142, "1": 89, ...} -- O(n_clusters), not O(n_cells)
    resolution: float
    modularity: float
    umap_computed: bool                  # coordinates live in adata.obsm['X_umap'] / the store, not here
    config: dict                          # n_neighbors, n_iterations, random_state

@dataclass
class DEGeneResult:
    gene: str
    score: float
    pval: float
    pval_adj: float
    logfoldchange: float
    pct_group: float | None    # from pts=True
    pct_rest: float | None

@dataclass
class DESummary:
    dataset_id: str
    groupby: str
    group1: str
    group2: str | None          # None means "rest"
    method: str                    # "wilcoxon"
    n_genes_tested: int           # total genes tested, for context -- a count, not the array
    n_significant: int             # count where pval_adj < 0.05
    top_genes: list[DEGeneResult]  # capped, e.g. top 25 by pval_adj
```

`sc.get.rank_genes_groups_df`'s built-in `pval_cutoff`/`log2fc_min`/`log2fc_max` params plus a `.head(n)` on the sorted DataFrame is sufficient to build `top_genes` without any hand-rolled filtering logic.

## Composition with Phase 1's DatasetStore

**Question posed:** should analysis tools load a dataset by name/version from the store and write results back, or operate on an in-memory `AnnData` passed by the caller?

**Recommendation: both, at different layers**, mirroring the exact shape Phase 1 already established:

- **Low-level functions** (`preprocess`, `cluster`, `differential_expression`) should be pure(ish): take an `AnnData` argument, return an `AnnData` (or `AnnData` + summary), and be independently unit-testable with in-memory fixtures — no `DatasetStore` dependency. This matches how `ingest/qc.py::run()` and `ingest/contract.py` were each built and unit-tested independently in 01-02/01-03 before any store involvement.
- **One coarse-grained orchestration entrypoint** (e.g. `analysis/pipeline.py::analyze(dataset_id, store_root="data", ...) -> (new_dataset_id, summary)`), mirroring `ingest/pipeline.py::ingest_10x()`, should: `store.load(name, version)` -> `contract.verify_counts_integrity()` (pitfall 6, step 1) -> compose `preprocess` -> `cluster` -> (optionally `differential_expression`) -> `contract.verify_counts_integrity()` again (pitfall 6, step 2) -> `store.save(name, adata, ...)` (creates a **new version**, per `DatasetStore.save()`'s `MAX(version)+1` behavior — there is no "update in place" method) -> return the new `"{name}@{version}"` id plus the bounded summary.

`DatasetStore` has no update/overwrite method by design (per its own 01-04 docstring: "auto-incrementing a version each time"). Composing analysis as "load version N, run pipeline, save as version N+1" is the only interface the store actually offers, and it preserves the versioned-history property (a researcher can diff pre-/post-analysis versions) that INGEST-03 already established as a project value. Recommend the planner adopt this explicitly rather than inventing an in-place update path.

## Code Examples

Verified patterns from official sources (cross-checked against installed scanpy 1.12.4):

### Deterministic preprocessing (ANLYS-01)
```python
# Source: https://scanpy.readthedocs.io/en/stable/tutorials/basics/clustering.html
sc.pp.normalize_total(adata)
sc.pp.log1p(adata)
sc.pp.highly_variable_genes(adata, n_top_genes=2000, batch_key="sample")  # batch_key optional
sc.tl.pca(adata)
```

### Clustering + embedding (ANLYS-02)
```python
# Source: https://scanpy.readthedocs.io/en/stable/tutorials/basics/clustering.html
sc.pp.neighbors(adata)
sc.tl.leiden(adata, flavor="igraph", n_iterations=2)
sc.tl.umap(adata)
```

### DE result extraction (ANLYS-03)
```python
# Source: scanpy.get.rank_genes_groups_df docstring (installed 1.12.4)
sc.tl.rank_genes_groups(adata, groupby="leiden", method="wilcoxon")
dedf = sc.get.rank_genes_groups_df(adata, group="0")
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|---------------|--------------------|-----------------|---------|
| `sc.tl.louvain` clustering | `sc.tl.leiden` (Traag et al. 2019) | Years ago; long-established as the current community standard | Guarantees well-connected communities, unlike Louvain; already locked by ANLYS-02 |
| `sc.tl.leiden(flavor="leidenalg")` (implicit default) | `sc.tl.leiden(flavor="igraph", n_iterations=2)` | Ongoing in current scanpy releases (1.10+); source code's own deprecation-style message says the default will switch to `igraph` in a future release | "Orders of magnitude faster" per scanpy's own source comment; already what ANLYS-02 locks, so no decision needed, but worth knowing this is the direction upstream is heading anyway |
| Explicit `sc.pp.scale()` before PCA | Many current scanpy workflows (including the official tutorial) omit an explicit scale step, relying on `pca(zero_center=True)`'s mean-centering | Gradual shift in community practice; not a hard version cutover | Genuinely disputed among practitioners — flagged as Claude's Discretion, not a settled "old vs new" |

**Deprecated/outdated:**
- `sc.tl.louvain`: superseded by `sc.tl.leiden`, already reflected in this phase's requirements.
- `flavor=None`/`"leidenalg"` as the implicit Leiden default: scanpy's own source (`_validate_flavor`) already emits guidance toward `flavor="igraph"`; ANLYS-02 has already made this decision, so no further action needed beyond following it.

## Open Questions

1. **Should analysis parameters be an explicit, logged, overridable config dataclass (mirroring `QCConfig`)?**
   - What we know: Phase 1 established a hard-won pattern (QC-02: "thresholds are explicit and logged per run, not silently hard-coded") via `QCConfig` + `adata.uns['qc']`.
   - What's unclear: ANLYS-01..04's wording doesn't explicitly require this for analysis parameters (`target_sum`, `n_top_genes`, `n_pcs`, `n_neighbors`, `resolution`, `random_state`).
   - Recommendation: Strongly recommend an equivalent `AnalysisConfig` dataclass logged to `adata.uns['analysis']`, both for consistency with the established project pattern and because it directly supports ANLYS-04's "structured" requirement (a logged config is itself a useful part of the bounded summary).

2. **Is `n_top_genes=2000` (the tutorial default) usable against small test fixtures?**
   - What we know: existing Phase 1 fixtures (`tiny_mtx_dir`: 18 genes; `synthetic_adata`: 20 genes) are far below 2000.
   - What's unclear: whether Wave 0 should add a larger/richer fixture, clamp `n_top_genes` defensively (both), or both.
   - Recommendation: both — clamp defensively in the function itself (`min(n_top_genes, adata.n_vars)`, per Pitfall 4) AND add a new, larger synthetic fixture in Wave 0 so tests can exercise realistic multi-cluster behavior rather than only edge-case-sized inputs (see Wave 0 Gaps).

3. **Should the DE tool support condition-vs-condition comparisons, not just cluster-vs-cluster?**
   - What we know: `sc.tl.rank_genes_groups`'s `groupby`/`groups`/`reference` params are already fully generic over any categorical `.obs` column — nothing scanpy-specific ties DE to the Leiden cluster key.
   - What's unclear: the requirement text says "between two clusters or conditions," implying both should be supported, but doesn't specify the tool signature.
   - Recommendation: design `differential_expression(adata, groupby, group1, group2=None)` generically (as in Pattern 3) so it transparently supports both use cases and will already be ready for later phases (e.g. perturbation/VCC condition comparisons in Phase 5) without rework.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest (already configured) |
| Config file | `pyproject.toml` `[tool.pytest.ini_options]` (`testpaths=["tests"]`, `pythonpath=["."]`) |
| Quick run command | `uv run pytest tests/test_analysis.py -x` |
| Full suite command | `uv run pytest tests/ -q` |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|---------------------|---------------|
| ANLYS-01 | normalize/HVG/PCA prerequisite pipeline runs deterministically on a QC'd `.h5ad` | unit | `uv run pytest tests/test_analysis.py -k preprocess -x` | ❌ Wave 0 |
| ANLYS-02 | Leiden (`flavor="igraph"`) clusters cells; 2D UMAP embedding produced | unit | `uv run pytest tests/test_analysis.py -k cluster -x` | ❌ Wave 0 |
| ANLYS-03 | Wilcoxon rank-sum DE between two clusters/conditions returns ranked genes | unit | `uv run pytest tests/test_analysis.py -k differential -x` | ❌ Wave 0 |
| ANLYS-04 | Each tool call returns a bounded, structured summary (no raw matrix/array) | unit | `uv run pytest tests/test_analysis.py -k summary -x` | ❌ Wave 0 |
| (integration) | Full pipeline: load from store -> analyze -> save new version -> `verify_counts_integrity()` still `True` | integration | `uv run pytest tests/test_analysis_pipeline.py -x` | ❌ Wave 0 |

### Sampling Rate
- **Per task commit:** `uv run pytest tests/test_analysis.py -x`
- **Per wave merge:** `uv run pytest tests/ -q`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `tests/test_analysis.py` — new file; covers ANLYS-01/02/03/04 unit behavior
- [ ] `tests/test_analysis_pipeline.py` — new file; covers the store-composed integration path and Pitfall 6's checksum-preservation property end to end (mirrors `tests/test_pipeline.py`'s existing pattern)
- [ ] New `conftest.py` fixture: a synthetic `AnnData` with enough cells/genes/structure (e.g. ~150-300 cells, ~60-100 genes, two well-separated pseudo-populations) to reliably produce ≥2 stable Leiden clusters and a non-trivial DE result at default `resolution=1.0`/`n_neighbors=15` — the existing `synthetic_adata` fixture (20 genes x 50 cells, built for QC edge cases) is almost certainly too small/unstructured for this
- [ ] Framework install: `uv add "igraph>=0.10.8"` — required before any `flavor="igraph"` test can even import successfully (Pitfall 1)

## Sources

### Primary (HIGH confidence)
- Installed package introspection (`scanpy==1.12.4`, `anndata==0.13.3`, `umap-learn==0.5.12`; `igraph`/`leidenalg` confirmed NOT installed) — this repo's `uv` environment, verified directly
- `scanpy/tools/_leiden.py` source (installed 1.12.4, read via `inspect.getsource`) — confirmed `flavor="igraph"` + `directed` validation logic, `n_iterations` semantics, output fields written to `adata.uns[key_added]`
- Empirical test in this repo's environment: `AnnData.write_h5ad`/`read_h5ad` round-trip does NOT preserve a frozen (`writeable=False`) sparse buffer flag — directly informs Pitfall 6
- `pyproject.toml` (this repo) — confirmed current dependencies and scanpy extras (`Provides-Extra`: `leiden` pulls `igraph>=0.10.8` + `leidenalg>=0.10.1`)
- [scanpy.tl.leiden — Read the Docs](https://scanpy.readthedocs.io/en/stable/generated/scanpy.tl.leiden.html)
- [scanpy.tl.rank_genes_groups — Read the Docs](https://scanpy.readthedocs.io/en/stable/generated/scanpy.tl.rank_genes_groups.html)
- [scanpy.pp.highly_variable_genes — Read the Docs](https://scanpy.readthedocs.io/en/stable/generated/scanpy.pp.highly_variable_genes.html)
- [scanpy.pp.normalize_total — Read the Docs](https://scanpy.readthedocs.io/en/stable/generated/scanpy.pp.normalize_total.html)
- [Preprocessing and clustering — official scanpy tutorial](https://scanpy.readthedocs.io/en/stable/tutorials/basics/clustering.html)
- `01-05-SUMMARY.md` (this repo) — Phase 1's own checksum-invalidation-after-mutation discovery, the direct precedent for Pitfall 6
- `ingest/pipeline.py`, `ingest/qc.py`, `ingest/contract.py`, `ingest/store.py` (this repo) — read directly to determine composition pattern and store interface

### Secondary (MEDIUM confidence)
- WebSearch on `sc.tl.leiden` flavor deprecation status and the official `igraph`+`n_iterations=2` recommendation, cross-verified against scanpy source directly — [Change default leiden clustering backend to igraph — scverse/scanpy#2865](https://github.com/scverse/scanpy/issues/2865)
- UMAP `random_state` reproducibility caveat — [Setting a random state still leads to stochastic results — lmcinnes/umap#1080](https://github.com/lmcinnes/umap/issues/1080), [Semi-deterministic output even though random_state is set — lmcinnes/umap#1108](https://github.com/lmcinnes/umap/issues/1108)

### Tertiary (LOW confidence)
- The "Bounded Summary Design" section's exact field names/shapes: original synthesis, not sourced from any external documented pattern — flagged explicitly for planner discretion

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — verified against live installed package versions and official readthedocs pages, not training-data recall alone
- Architecture (pipeline composition, store interaction): HIGH — directly derived from Phase 1's own already-implemented, already-tested code (`ingest/pipeline.py`, `ingest/store.py`)
- Architecture (bounded summary return-type shapes): MEDIUM — no external prescriptive source exists for this specific problem; reasoned from ANLYS-04's wording and general LLM-context-budget principles
- Pitfalls (igraph dependency gap, `directed` requirement, HVG flavor mismatch, small-fixture dimensionality guards, counts-layer round-trip): HIGH — each verified either via source-code introspection or an empirical test run in this repo's actual environment
- Pitfalls (UMAP determinism caveat): MEDIUM — community-reported upstream GitHub issues, not an official confirmed-bug statement from umap-learn maintainers

**Research date:** 2026-09-04
**Valid until:** ~30 days (scanpy is a fast-moving but not weekly-breaking library; the `igraph`-default-flavor transition mentioned in State of the Art could land in a scanpy point release within that window and should be re-checked if planning is delayed)
