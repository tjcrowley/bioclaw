# Phase 1: Ingest + QC Pipeline - Research

**Researched:** 2026-09-03
**Domain:** Single-cell RNA-seq ingest/QC (scanpy/AnnData ecosystem)
**Confidence:** HIGH (core stack/API verified against current official docs; dataset-versioning approach is MEDIUM — a defensible build-vs-buy call, not a hard fact)

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-------------------|
| INGEST-01 | Ingest standard 10x Genomics output (`.mtx`, `.h5`) and normalize to canonical `.h5ad` | `sc.read_10x_mtx` / `sc.read_10x_h5` are the correct, current scanpy entry points (verified against current docs). See Standard Stack + Code Examples. |
| INGEST-02 | Persist raw counts to an immutable `adata.layers['counts']` at load time, before any normalization | Confirmed as the #1 pitfall in prior project research (PITFALLS.md Pitfall 1: `.raw` is a reference, not a copy). See Common Pitfalls + Code Examples for a concrete copy + write-protection + checksum pattern. |
| INGEST-03 | Canonical datasets stored in a versioned dataset store the agent can reference by name | Two viable approaches researched: hand-rolled filesystem+SQLite registry (STACK.md's existing recommendation) vs. LaminDB (scverse-native, purpose-built artifact/versioning tool). See Don't Hand-Roll + Architecture Patterns for the recommendation and tradeoff. |
| QC-01 | Compute standard QC metrics (mito %, doublet score, low-count/gene filtering) | `sc.pp.calculate_qc_metrics` (mito%) + `sc.pp.scrublet` (doublets) + `sc.pp.filter_cells`/`filter_genes` (count/gene filtering) are the current, correct scanpy calls — verified against current docs. See Code Examples. |
| QC-02 | QC thresholds explicit and logged per run, not hard-coded | Directly maps to PITFALLS.md Pitfall 3 (naive global QC thresholds silently bias which cell types survive). See Architecture Patterns (QC config + structured filtering report) and Common Pitfalls. |
</phase_requirements>

## Summary

Phase 1 is a CPU-only, deterministic, agent-independent pipeline — no LLM, no GPU, no MCP wiring yet (those come in Phase 3+). The entire domain is well-trodden scanpy/AnnData territory: this phase is about disciplined engineering of a known workflow, not novel research. The two genuinely load-bearing design decisions are (1) how to make the raw-counts contract in INGEST-02 actually hard to violate, not just a documentation promise, and (2) how much infrastructure to build for the "versioned dataset store referenced by name" in INGEST-03.

This project's own prior research (`.planning/research/*.md`, written earlier the same day) already did substantial domain investigation and converges cleanly with what this phase-specific pass confirms: `sc.read_10x_h5`/`sc.read_10x_mtx` for ingest, `sc.pp.calculate_qc_metrics(qc_vars=["mt"])` for mitochondrial %, `sc.pp.scrublet` for doublet detection, and `sc.pp.filter_cells`/`sc.pp.filter_genes` for count-based filtering — all current, non-deprecated scanpy 1.12.x APIs. The one new finding this pass adds is that `adata.raw = adata` is a genuine landmine (reference semantics, not a copy) that a well-intentioned implementer could easily fall into by "following the scanpy tutorial pattern" — the ingest pipeline must use `adata.layers['counts'] = adata.X.copy()` and should go further, additionally freezing the underlying buffer's writeable flag and storing a checksum, since AnnData itself has no built-in immutability enforcement.

For the versioned dataset store (INGEST-03), a hand-rolled filesystem + SQLite registry (as STACK.md already proposed) remains the right call for a single-developer MVP — it is simple, has zero new dependencies to learn, and is trivially testable. LaminDB (built by the scanpy/anndata team, scverse-native, supports a local SQLite backend with no Docker/server requirement) is a legitimate, low-friction upgrade path if multi-user/lineage-tracking needs grow later, but adopting it now would add a new tool to learn for a problem (name → versioned `.h5ad` lookup) that a ~150-line module solves adequately at this scale.

**Primary recommendation:** Build `ingest/loaders.py` (10x → AnnData), `ingest/qc.py` (metrics + explicit config + structured filtering report), and `ingest/store.py` (filesystem + SQLite registry, `save(name, adata) -> version` / `load(name, version=None)`) as three deterministic, agent-independent Python modules with one coarse-grained `ingest_10x(path, name, qc_config) -> dataset_id` entrypoint function, following ARCHITECTURE.md's existing "deterministic pipeline behind a coarse-grained tool call" pattern. Do not build agent/MCP wiring in this phase — that's Phase 3.

## Standard Stack

### Core

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| Python | 3.12+ | Runtime | Current scanpy pins `requires-python >= 3.12`; confirmed in STACK.md and unchanged this pass. |
| scanpy | 1.12.4 | Ingest (`read_10x_h5`/`read_10x_mtx`), QC (`calculate_qc_metrics`, `scrublet`, `filter_cells`/`filter_genes`) | The de facto single-cell toolkit; every function this phase needs is current, non-deprecated API, verified against https://scanpy.readthedocs.io/en/stable/. |
| anndata | 0.13.3.post0 | `.h5ad` canonical data structure, `layers`, `write_h5ad`/`read_h5ad` | Scanpy's data layer; `.h5ad` is the project's own mandated canonical format (PROJECT.md). |

### Supporting

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `scanpy[scrublet]` (`sc.pp.scrublet`) | ships with scanpy core | Doublet score/flag | Run once per ingest, on raw counts, before any normalization (Phase 2 owns normalization). |
| `scipy.sparse` | (anndata dependency) | Underlying storage for `.X`/`.layers` when data is sparse (typical for 10x output) | Needed directly for the write-protection technique in Code Examples — `csr_matrix.data` is a plain numpy array you can freeze. |
| `sqlite3` (stdlib) | stdlib | Dataset registry backing INGEST-03 | Zero-dependency, sufficient for single-developer/internal-tool scale; matches STACK.md's existing "don't reach for a vector DB / heavyweight DB yet" guidance. |
| `pytest` | current | Test framework for this phase | Standard; see Validation Architecture. |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Hand-rolled filesystem+SQLite dataset registry | LaminDB (`lamindb`, scverse-native, YC-backed, built by the scanpy/anndata authors) | LaminDB gives you artifact versioning (`ln.Artifact.from_anndata`, `revises=` for version chains), lineage tracking, and a queryable registry out of the box, with a local SQLite backend and no server/Docker requirement — genuinely low friction to try. But it's a new dependency/mental model to learn for a problem (name→version→path lookup) the hand-rolled approach solves in ~150 lines with zero new concepts. Revisit if Phase 3+ needs richer lineage (which tool call produced which dataset version) or if multiple researchers start sharing the store concurrently. |
| `sc.pp.scrublet` (in-scanpy) | `scDblFinder` (R/Bioconductor) | Some benchmarks favor scDblFinder's accuracy, but it pulls in an R dependency for no clear MVP benefit — STACK.md already made this call (MEDIUM confidence); this research pass found nothing to overturn it. |
| Manual mitochondrial-gene % calculation | `sc.pp.calculate_qc_metrics(qc_vars=["mt"])` | Don't hand-roll the percentage math — see Don't Hand-Roll. |

**Installation:**
```bash
uv venv --python 3.12 .venv-pipeline
uv pip install "scanpy[scrublet]" anndata
uv pip install -D pytest ruff
```

## Architecture Patterns

### Recommended Project Structure

```
bioclaw/
├── ingest/
│   ├── __init__.py
│   ├── loaders.py          # 10x .mtx/.h5 -> raw AnnData (format detection, var_names_make_unique)
│   ├── qc.py                # QC metrics, QCConfig, filtering report
│   ├── store.py              # DatasetStore: save/load by name+version (filesystem + SQLite index)
│   └── pipeline.py           # single entrypoint: ingest_10x(path, name, qc_config) -> dataset_id
├── data/                      # canonical .h5ad store (gitignored — already in .gitignore)
│   └── registry.sqlite        # dataset registry index
└── tests/
    ├── conftest.py             # synthetic 10x mtx/h5 fixture generators
    ├── test_loaders.py
    ├── test_qc.py
    └── test_store.py
```

This matches ARCHITECTURE.md's already-researched project structure (`ingest/loaders/`, `ingest/qc/`, `data/`) almost exactly — this phase-specific pass confirms it and adds the `store.py`/registry split as the concrete implementation of "Data / State Layer" from that doc.

### Pattern 1: Deterministic Pipeline Behind One Coarse-Grained Entrypoint

**What:** `ingest_10x(path, name, qc_config=None) -> dataset_id` is the single function this phase must produce; internally it calls `loaders.load(path)` → `qc.run(adata, qc_config)` → `store.save(name, adata)`. No LLM, no agent, no MCP tool wrapper yet.
**When to use:** This entire phase — it is explicitly the "prove the deterministic-tool contract cheaply, before the agent exists" step per ARCHITECTURE.md's suggested build order.
**Example:**
```python
# Source: pattern confirmed in .planning/research/ARCHITECTURE.md Pattern 1
def ingest_10x(path: str, name: str, qc_config: QCConfig | None = None) -> str:
    adata = loaders.load(path)                    # format-detect .mtx dir vs .h5 file
    adata.layers["counts"] = adata.X.copy()        # INGEST-02, before anything else touches .X
    _freeze_counts_layer(adata)                    # write-protect (see Code Examples)
    qc_config = qc_config or QCConfig()
    adata = qc.run(adata, qc_config)               # QC-01 + QC-02
    version = store.save(name, adata, source_path=path, qc_config=qc_config)
    return f"{name}@{version}"
```

### Pattern 2: Explicit, Logged QC Config (Not Hard-Coded Thresholds)

**What:** QC thresholds are a typed config object (dataclass or pydantic model) passed into the pipeline, with documented defaults, never silently hard-coded inline in filter calls. Every run writes the resolved config plus a per-reason filtering breakdown into `adata.uns['qc']`.
**When to use:** QC-02 requires this by name ("explicit and logged... researcher can see exactly what was filtered and why"). PITFALLS.md Pitfall 3 independently arrives at the same requirement from the failure-mode side.
**Example:**
```python
# Source: pattern derived from .planning/research/PITFALLS.md Pitfall 3 mitigation
@dataclass
class QCConfig:
    min_genes_per_cell: int = 200
    min_cells_per_gene: int = 3
    max_pct_mt: float | None = 20.0     # None = compute but don't filter on it
    doublet_action: Literal["flag", "filter"] = "flag"   # default: flag, don't silently drop

def run(adata: AnnData, cfg: QCConfig) -> AnnData:
    n_before = adata.n_obs
    adata.var["mt"] = adata.var_names.str.upper().str.startswith("MT-")
    sc.pp.calculate_qc_metrics(adata, qc_vars=["mt"], layer="counts",
                                percent_top=None, log1p=False, inplace=True)
    sc.pp.scrublet(adata, layer="counts") if hasattr(sc.pp, "scrublet") else sc.external.pp.scrublet(adata)

    removed = {}
    n_gene_filtered = adata.n_obs
    sc.pp.filter_cells(adata, min_genes=cfg.min_genes_per_cell)
    removed["low_gene_count"] = n_gene_filtered - adata.n_obs
    sc.pp.filter_genes(adata, min_cells=cfg.min_cells_per_gene)

    if cfg.max_pct_mt is not None:
        n_before_mt = adata.n_obs
        adata = adata[adata.obs["pct_counts_mt"] <= cfg.max_pct_mt].copy()
        removed["high_mito"] = n_before_mt - adata.n_obs

    if cfg.doublet_action == "filter":
        n_before_dbl = adata.n_obs
        adata = adata[~adata.obs["predicted_doublet"]].copy()
        removed["doublet"] = n_before_dbl - adata.n_obs

    adata.uns["qc"] = {
        "config": asdict(cfg),
        "n_cells_before": n_before,
        "n_cells_after": adata.n_obs,
        "removed_by_reason": removed,
    }
    return adata
```

### Anti-Patterns to Avoid

- **`adata.raw = adata` as a "safety" backup:** it's a reference, not a copy — a later `sc.pp.normalize_total()`/`log1p()` silently mutates it too. Use `adata.layers['counts'] = adata.X.copy()` (verified `.copy()` call, real independent array). Confirmed both by prior project research (PITFALLS.md Pitfall 1, citing scverse/anndata GitHub issue #3073) and unchanged in current docs.
- **Global hard-coded QC thresholds applied identically to every dataset:** ties every ingested dataset to the same cutoffs regardless of tissue/cell type, silently biasing which cell types survive (PITFALLS.md Pitfall 3). Always accept an overridable `QCConfig` with documented defaults.
- **Auto-dropping predicted doublets by default:** doublet detectors specifically struggle with continuous/transitional cell states; 10x/OSCA guidance is to treat a high doublet score as "suspect, inspect with cluster context," not an automatic removal. Default to `doublet_action="flag"` (adds `predicted_doublet`/`doublet_score` to `.obs`, doesn't filter), require explicit opt-in for `"filter"`.
- **Loading the entire `.h5ad` into memory on every dataset-store lookup for large future datasets:** not a Phase 1 blocker (public pilot datasets are small), but design `store.load()` to accept a `backed` passthrough now so it's not a later rewrite (ARCHITECTURE.md Performance Traps).

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|--------------|-----|
| 10x `.mtx`/`.h5` parsing | A custom MEX/HDF5 parser | `sc.read_10x_mtx(path)` / `sc.read_10x_h5(path)` | These already handle the MEX (`barcodes.tsv.gz`/`features.tsv.gz`/`matrix.mtx.gz`) and HDF5 feature-barcode-matrix formats exactly as Cell Ranger emits them, including gzip and legacy single-genome-vs-multi-genome `.h5` variants. |
| Mitochondrial % calculation | Manual `sum(mt_gene_counts)/sum(total_counts)` loop | `sc.pp.calculate_qc_metrics(adata, qc_vars=["mt"], inplace=True)` | Produces the standard `pct_counts_mt`, `n_genes_by_counts`, `total_counts` columns the rest of the ecosystem (and this project's later phases) expects by name; hand-rolling risks a subtly different denominator/edge-case handling. |
| Doublet detection | A custom nearest-neighbor/simulated-doublet classifier | `sc.pp.scrublet(adata)` | Scrublet's simulated-doublet + nearest-neighbor approach is a published, validated method already wrapped in scanpy core; reimplementing it is significant effort for a worse-tested result. |
| `.h5ad` serialization | Manual HDF5 group writing | `adata.write_h5ad(path)` / `sc.read_h5ad(path)` | AnnData's on-disk schema is versioned and has specific encoding conventions (categorical columns, sparse layout, `uns` nesting) that a hand-rolled writer will not reproduce compatibly with the rest of the scverse ecosystem. |
| Versioned artifact/dataset registry (if this grows beyond MVP scale) | A bespoke multi-table ORM-backed dataset lineage system | LaminDB (`lamindb`), if/when the hand-rolled SQLite registry stops being sufficient | Purpose-built by the scanpy/anndata team specifically for versioning `.h5ad`/array data with lineage; don't build a second, worse version of this later — swap in LaminDB rather than growing the hand-rolled registry into an ad hoc ORM. |

**Key insight:** Everything ingest/QC-specific in this phase already has a canonical, current scanpy function. The only place custom code is genuinely warranted is the dataset *store* (name→version→path registry) and the *contract enforcement* around `layers['counts']` (write-protection + checksum) — neither of which scanpy/anndata provide out of the box, because they're project-specific trust guarantees, not general single-cell analysis operations.

## Common Pitfalls

### Pitfall 1: `adata.raw` reference-semantics footgun (carried over from prior project research, directly load-bearing for INGEST-02)

**What goes wrong:** `adata.raw = adata` looks like a snapshot but is a reference; any later in-place `.X` mutation (even in a later phase/tool) silently corrupts what looked like a safe backup, with no error thrown.
**Why it happens:** AnnData's `.raw` attribute genuinely has reference semantics — confirmed in scverse/anndata GitHub issue #3073, not a scanpy bug.
**How to avoid:** `adata.layers['counts'] = adata.X.copy()` at ingest time, before any other pipeline step touches `.X`; never treat `.raw` as the source of truth.
**Warning signs:** Downstream tools (later phases) receive non-integer or negative values where raw counts were expected.

### Pitfall 2: AnnData has no built-in immutability — "immutable" must be actively enforced

**What goes wrong:** INGEST-02 requires `layers['counts']` to "stay unchanged through later pipeline steps," but neither `AnnData` nor `scipy.sparse` matrices are immutable by default — a later phase's code (e.g., an accidental `adata.layers['counts'] *= 2` typo) will silently succeed.
**Why it happens:** Python/numpy/scipy don't enforce read-only semantics unless you explicitly ask for it.
**How to avoid:** Two complementary techniques, both verified as valid numpy/scipy behavior: (1) freeze the underlying buffer — for a sparse `csr_matrix`/`csc_matrix`, `adata.layers['counts'].data.flags.writeable = False` causes any later in-place write attempt to raise `ValueError`; for a dense array, `adata.layers['counts'].flags.writeable = False` does the same. (2) Store a content checksum (`hashlib.sha256` of the raw bytes) in `adata.uns['counts_checksum']` at ingest time, and provide a `verify_counts_integrity(adata)` helper other phases' tests/tool boundaries can call to assert nothing snuck past the write-lock (e.g., via a full-array reassignment, which the writeable flag alone won't catch).
**Warning signs:** A test that normalizes `.X` and then asserts `layers['counts']` is unchanged passes today but would silently start failing if someone "fixes" the write-lock later without understanding why it's there.

### Pitfall 3: Naive global QC thresholds silently bias which cell types survive

**What goes wrong:** A single fixed mito%/min-genes cutoff applied to every dataset removes legitimately high-mito cell types (e.g., cardiomyocytes) or legitimately low-count cell types (e.g., microglia) — this is dataset/tissue-dependent, not a universal constant.
**Why it happens:** Fixed thresholds are the easiest thing to encode as a tool default.
**How to avoid:** QC-02's explicit/logged config (Pattern 2) is the direct mitigation — thresholds are inspectable/overridable parameters, and the per-reason filtering breakdown (`removed_by_reason`) lets a researcher notice if a QC step removed an implausibly large fraction of cells.
**Warning signs:** QC step removes >30-40% of cells with no per-reason breakdown available to explain why (10x Genomics' own QC guidance flags this as a red flag threshold).

### Pitfall 4: `sc.read_10x_mtx`'s `gex_only=True` default silently drops non-Gene-Expression features

**What goes wrong:** If a 10x run includes Antibody Capture (CITE-seq), CRISPR Guide Capture, or Custom feature types alongside Gene Expression, the default `gex_only=True` silently discards them — fine for pure scRNA-seq (this project's v1 scope, per REQUIREMENTS.md "Out of Scope: Additional modalities... CITE-seq"), but worth an explicit, documented assumption rather than an implicit one, since a researcher pointing the pipeline at a mixed-modality 10x run wouldn't be warned.
**Why it happens:** It's the scanpy default, chosen for the common case.
**How to avoid:** Keep `gex_only=True` (matches project scope) but log which feature types were present in the source data and how many were dropped, so it's visible rather than silent.
**Warning signs:** A dataset's reported cell/feature counts don't match what the researcher expected from the source Cell Ranger run summary.

### Pitfall 5: Duplicate gene symbols in `features.tsv`/`.h5` `var_names`

**What goes wrong:** 10x feature files can contain duplicate gene symbols (e.g., paralogs sharing a display name); without `make_unique=True` (the `read_10x_mtx` default) or an explicit `adata.var_names_make_unique()` call after `read_10x_h5`, downstream indexing by gene name becomes ambiguous or raises errors.
**Why it happens:** Gene symbol namespaces aren't guaranteed unique at the annotation-source level.
**How to avoid:** `read_10x_mtx` already defaults `make_unique=True`; `read_10x_h5` does not do this automatically — call `adata.var_names_make_unique()` explicitly after `read_10x_h5` in the loader, regardless of path, so both entry points behave identically.
**Warning signs:** `KeyError` or unexpected multi-row results when a later phase looks up a gene by symbol.

## Code Examples

### Format-detecting loader
```python
# Source: scanpy.readthedocs.io current API (sc.read_10x_h5, sc.read_10x_mtx), verified 2026-09-03
import scanpy as sc
from pathlib import Path

def load(path: str):
    p = Path(path)
    if p.is_dir():
        adata = sc.read_10x_mtx(p, var_names="gene_symbols", make_unique=True,
                                 gex_only=True, cache=False)
    elif p.suffix == ".h5":
        adata = sc.read_10x_h5(p)
        adata.var_names_make_unique()   # read_10x_h5 does NOT auto-dedupe (Pitfall 5)
    else:
        raise ValueError(f"Unrecognized 10x input: {path} (expected a .mtx directory or .h5 file)")
    return adata
```

### Raw-counts contract: copy, freeze, checksum
```python
# Source: scipy.sparse writeable-flag behavior + hashlib, standard library/scipy semantics
import hashlib

def _freeze_counts_layer(adata):
    counts = adata.layers["counts"]
    if hasattr(counts, "data"):          # sparse (csr/csc)
        counts.data.flags.writeable = False
    else:                                  # dense ndarray
        counts.flags.writeable = False
    adata.uns["counts_checksum"] = hashlib.sha256(
        counts.data.tobytes() if hasattr(counts, "data") else counts.tobytes()
    ).hexdigest()

def verify_counts_integrity(adata) -> bool:
    counts = adata.layers["counts"]
    current = hashlib.sha256(
        counts.data.tobytes() if hasattr(counts, "data") else counts.tobytes()
    ).hexdigest()
    return current == adata.uns.get("counts_checksum")
```

### Standard QC metrics
```python
# Source: scanpy.readthedocs.io current sc.pp.calculate_qc_metrics / sc.pp.scrublet docs, verified 2026-09-03
adata.var["mt"] = adata.var_names.str.upper().str.startswith("MT-")
sc.pp.calculate_qc_metrics(adata, qc_vars=["mt"], layer="counts",
                            percent_top=None, log1p=False, inplace=True)
# -> adds adata.obs['n_genes_by_counts'], adata.obs['total_counts'], adata.obs['pct_counts_mt']

sc.pp.scrublet(adata)
# -> adds adata.obs['doublet_score'], adata.obs['predicted_doublet']
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|-------------------|---------------|--------|
| `sc.pp.filter_cells`/`filter_genes` with inline magic numbers | Explicit `QCConfig` object passed through the pipeline, logged to `adata.uns` | Not a scanpy API change — a project-level best-practice shift this phase must adopt directly (QC-02 requirement) | Prevents the "silent hard-coded threshold" failure mode identified independently in this project's own PITFALLS.md |
| `adata.raw = adata` as the "keep a copy of raw data" pattern (still shown in some older tutorials) | `adata.layers['counts'] = adata.X.copy()` | Long-standing scverse guidance, reconfirmed via GitHub issue #3073; not a recent version change but a persistent tutorial-vs-reality gap | Directly prevents INGEST-02's core failure mode |
| `scanpy.tl.louvain` clustering | `sc.tl.leiden(flavor="igraph")` | Louvain deprecated as of scanpy 1.12 (per STACK.md, already researched) | Not used in Phase 1 (clustering is Phase 2), noted for consistency only |

**Deprecated/outdated:** None specific to ingest/QC functions used in this phase — `read_10x_h5`, `read_10x_mtx`, `calculate_qc_metrics`, `scrublet`, `filter_cells`, `filter_genes` are all current, non-deprecated scanpy 1.12.x API as of this research pass.

## Open Questions

1. **Should doublets be filtered by default or only flagged?**
   - What we know: 10x/OSCA guidance and this project's own PITFALLS.md both recommend flagging over auto-filtering, especially early on.
   - What's unclear: whether Biopunk Labs' researchers (first users) will expect doublets pre-filtered out of the "canonical" dataset by default, or want to see them and decide themselves.
   - Recommendation: default `doublet_action="flag"` (Pattern 2) — cheapest to change later (one config default), and the more conservative/safe choice per pitfall research. Planner should treat this as Claude's discretion unless the user specifies otherwise.

2. **Filesystem+SQLite registry vs. LaminDB for INGEST-03 — confirmed as build-vs-buy, not fully resolved**
   - What we know: both are technically viable; LaminDB explicitly supports local SQLite with no server; the hand-rolled approach is simpler to reason about for a single developer today.
   - What's unclear: whether Phase 3+ (agent/session memory) or later multi-user use will need LaminDB's lineage-tracking capabilities badly enough to justify adopting it now instead of later.
   - Recommendation: build the hand-rolled registry now (Standard Stack); keep `store.py`'s public interface (`save`/`load`/`list` by name+version) narrow enough that swapping the backend to LaminDB later wouldn't require changing callers.

3. **Exact 10x input variant(s) the first real test will use**
   - What we know: PROJECT.md confirms the first dataset will be public (`cellxgene-census` or VCC's public dataset), not in-house wet-lab data yet.
   - What's unclear: `cellxgene-census` datasets are typically already `.h5ad`, not raw `.mtx`/`.h5` — meaning the "point the ingest pipeline at a 10x directory" success criterion may need a *separate* raw-10x-format test dataset (e.g., a small public Cell Ranger output, or a synthetic fixture) distinct from whatever dataset validates the rest of the pipeline end-to-end.
   - Recommendation: use a small, synthetic, in-repo 10x-format fixture (see Validation Architecture) for ingest-format testing regardless of which real dataset is chosen for a fuller pilot run — this also removes a network dependency from the test suite.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest (current) — no test framework exists yet in this greenfield repo |
| Config file | none — see Wave 0 |
| Quick run command | `pytest tests/ -x -q` |
| Full suite command | `pytest tests/ -q` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|---------------------|--------------|
| INGEST-01 | Ingest a synthetic 10x `.mtx` directory and `.h5` file, get back a valid `.h5ad`-backed AnnData with correct `n_obs`/`n_vars`/`var_names` | unit | `pytest tests/test_loaders.py::test_load_mtx_dir -x` / `::test_load_h5 -x` | ❌ Wave 0 |
| INGEST-02 | `layers['counts']` set at load time, unchanged after a simulated later normalization step; write-attempt on the frozen layer raises | unit | `pytest tests/test_ingest_contract.py::test_counts_immutable_after_normalize -x` | ❌ Wave 0 |
| INGEST-03 | Save a dataset by name, load it back by name (latest and by explicit version), two saves produce two distinct versions | unit | `pytest tests/test_store.py::test_save_load_roundtrip -x` / `::test_versioning -x` | ❌ Wave 0 |
| QC-01 | `pct_counts_mt`, `doublet_score`, `predicted_doublet`, `n_genes_by_counts`, `total_counts` present in `.obs` on a synthetic dataset with known-injected `MT-` genes | unit | `pytest tests/test_qc.py::test_qc_metrics_present -x` | ❌ Wave 0 |
| QC-02 | Changing a `QCConfig` threshold changes what's filtered, and `adata.uns['qc']` records the resolved config + per-reason removal counts | unit | `pytest tests/test_qc.py::test_qc_config_logged -x` / `::test_threshold_changes_filtering -x` | ❌ Wave 0 |

### Sampling Rate
- **Per task commit:** `pytest tests/ -x -q` (fast — all Phase 1 tests are CPU-only, synthetic, small fixtures; should run in well under 30 seconds)
- **Per wave merge:** `pytest tests/ -q` (full suite)
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `tests/conftest.py` — synthetic 10x fixture generators: (a) a tiny `.mtx` directory (`matrix.mtx.gz`/`barcodes.tsv.gz`/`features.tsv.gz`, ~10-20 genes × ~30-50 cells, scipy `mmwrite` + gzip) with a few `MT-`-prefixed genes and one deliberately duplicated gene symbol; (b) an equivalent tiny `.h5` file in Cell Ranger's HDF5 feature-barcode-matrix layout. Both must be small, in-repo, and require no network access (do not rely on `sc.datasets.pbmc3k()`, which downloads from the internet on first use).
- [ ] `tests/test_loaders.py`, `tests/test_ingest_contract.py`, `tests/test_qc.py`, `tests/test_store.py` — new files, covering INGEST-01/02/03, QC-01/02 per the table above.
- [ ] `pyproject.toml` or `pytest.ini` — minimal pytest config (test discovery paths); none exists yet in this greenfield repo.
- [ ] Framework install: `uv pip install -D pytest`.

### Edge Cases to Explicitly Test
- **Empty result after filtering:** a `QCConfig` with an implausibly strict `min_genes_per_cell` (e.g., 100000) that filters out every cell — pipeline should not crash; should return a 0-`n_obs` AnnData with the filtering report showing 100% removed, not silently succeed with misleading downstream state. Verify the pipeline either raises a clear, typed error or returns an explicitly empty-but-valid dataset (planner should decide which; either is acceptable, but it must be intentional, not an unhandled exception from a downstream `.obs["pct_counts_mt"]` access on an empty frame).
- **All-cells-already-filtered input:** a 10x directory representing a `filtered_feature_bc_matrix` (already cell-called by Cell Ranger) vs. a `raw_feature_bc_matrix` (all barcodes, mostly empty droplets) — both are valid 10x inputs per 10x's own documented output structure; confirm the loader doesn't assume one or the other.
- **Duplicate gene symbols:** confirm `var_names_make_unique()` behavior is tested explicitly (both loader paths), not just implicitly relied upon.
- **Zero-count cell/gene rows:** a synthetic dataset including at least one all-zero cell and one all-zero gene, to confirm `filter_cells`/`filter_genes` behave as expected at the boundary (`min_genes=1` should remove an all-zero cell).
- **Re-ingesting the same source path under the same name:** confirms INGEST-03's versioning increments rather than silently overwriting.

*(No section can be marked "None — existing test infrastructure covers all phase requirements": this is a greenfield repo with zero existing tests.)*

## Sources

### Primary (HIGH confidence)
- https://scanpy.readthedocs.io/en/stable/api/scanpy.pp.calculate_qc_metrics.html — current `calculate_qc_metrics` signature, `qc_vars`, output column names
- https://scanpy.readthedocs.io/en/stable/api/generated/scanpy.pp.scrublet.html — current `sc.pp.scrublet` behavior, `doublet_score`/`predicted_doublet` outputs
- https://scanpy.readthedocs.io/en/stable/generated/scanpy.read_10x_mtx.html — current `read_10x_mtx` signature (`var_names`, `make_unique`, `gex_only`, `cache`)
- https://scanpy.readthedocs.io/en/stable/generated/scanpy.read_10x_h5.html — current `read_10x_h5` behavior, `genome` param for legacy multi-genome files
- https://www.10xgenomics.com/support/software/cell-ranger/latest/analysis/outputs/cr-outputs-mex-matrices — official MEX (`.mtx`) format directory structure
- https://www.10xgenomics.com/support/software/cell-ranger-arc/latest/analysis/outputs/outputs-h5-matrices — official HDF5 feature-barcode-matrix format
- https://github.com/scverse/anndata/issues/3073 — `.raw` reference-semantics confirmation (cross-referenced from this project's own prior PITFALLS.md research, re-verified this pass)
- `.planning/research/{STACK,PITFALLS,ARCHITECTURE,SUMMARY}.md` — this project's own same-day prior research; directly authoritative for this codebase's decisions and re-verified (not just copied) where claims were checkable against current docs

### Secondary (MEDIUM confidence)
- https://docs.lamin.ai/ — LaminDB local-SQLite-backend claim and `ln.Artifact.from_anndata`/`revises` versioning API (WebFetch-summarized, not independently cross-verified against a second source; recommend a hands-on spike before committing to it as a Phase 1 dependency if the planner chooses this path over the hand-rolled registry)
- https://github.com/laminlabs/lamindb — official repo, confirms scverse/scanpy-team origin and positioning

### Tertiary (LOW confidence)
- None used as authoritative for this document — all WebSearch findings were cross-checked against official scanpy/10x/anndata docs or this project's own prior HIGH/MEDIUM-confidence research before inclusion.

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — every scanpy function cited was checked against current (non-versioned-URL) official docs this session
- Architecture: HIGH — converges with this project's own same-day ARCHITECTURE.md research; no contradictions found
- Pitfalls: HIGH for the `.raw`/immutability/QC-threshold pitfalls (re-verified, not just copied); MEDIUM for the dataset-store build-vs-buy call (defensible but not the only valid answer)

**Research date:** 2026-09-03
**Valid until:** ~2026-10-03 (30 days) for the scanpy/anndata API surface (stable, slow-moving); re-check sooner if `scanpy`/`anndata` releases a major version bump before planning executes, or if LaminDB is chosen and its local-SQLite claim needs first-hand verification.

---
*Phase 1 research for: BioClaw ingest/QC pipeline*
