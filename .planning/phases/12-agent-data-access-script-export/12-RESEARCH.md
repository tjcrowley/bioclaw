# Phase 12: Agent Data Access + Script Export — Research

**Researched:** 2026-09-16
**Domain:** cellxgene-census API, asyncio integration, scanpy script generation, FastAPI endpoint
**Confidence:** HIGH (primary findings from installed library source + official docs)

## Summary

Phase 12 delivers two features: census-fetch (DATA-01) and scanpy script export (EXPORT-02). The census-fetch feature plugs into the existing agent tool layer (`agent/tools.py`) following the exact same `@tool` + pipeline-call pattern as the four existing tools. The script export is a new FastAPI endpoint, following the `GET /api/export/csv` pattern from EXPORT-01.

Both features are additive — no existing code is modified except `agent/server.py` (add the new tool) and `webapp/backend/main.py` (add the new endpoint). All parameter provenance exists in the data: QC thresholds live in `adata.uns['qc']`, analysis params live in `adata.uns['analysis']`, and the dataset source (census or file path) lives in `DatasetStore.list()['source_path']`. The only gap is that a census query's `obs_value_filter`, `organism`, and cell-count cap are not currently persisted — they must be recorded at fetch time so the script export can reconstruct them.

**Primary recommendation:** Add a `fetch_census_dataset` agent tool that wraps the census fetch in `asyncio.to_thread()` and routes through `ingest.loaders.load()` + `ingest.pipeline.ingest_10x()`. Add a `GET /api/export/script` endpoint that reads `adata.uns` and the store registry to generate a self-contained `.py` file. Add a new `census_data` marker to pyproject.toml for network-gated tests.

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| DATA-01 | Researcher asks agent for a dataset by tissue/organism/assay; agent fetches from cellxgene-census without a file upload; census fetch runs in `asyncio.to_thread()` | cellxgene-census `open_soma` + `get_anndata` are synchronous/blocking; `asyncio.to_thread()` is the correct wrapper; resulting AnnData routes through `ingest.loaders.load()` path so it matches production ingest structure; new `@tool` follows the exact existing pattern |
| EXPORT-02 | Researcher requests scanpy script export from any session; receives `.py` file reproducing every QC threshold, analysis parameter, dataset source reference, and random seed | All parameters are in `adata.uns['qc']` (QC thresholds), `adata.uns['analysis']` (analysis config including `random_state`), and `DatasetStore.list()['source_path']`; census query params must be stored at fetch time; script generation is a string-rendering function, not a library |
</phase_requirements>

---

## Standard Stack

### Core (already installed — no new top-level dependencies)

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| `cellxgene-census` | 1.18.0 (installed) | Open the CZI Census, filter by obs metadata, return AnnData | Already in pyproject.toml; the only supported API for programmatic census access |
| `tiledbsoma` | 2.2.0 (installed, transitive) | Underlying SOMA query engine used by cellxgene-census | Transitive dep; `open_soma` returns a `tiledbsoma.Collection` |
| `asyncio.to_thread` | stdlib | Run blocking census calls on a thread pool without blocking the event loop | Built-in; required because `open_soma` + `get_anndata` are fully synchronous |
| `fastapi` | installed (web extra) | New `GET /api/export/script` endpoint | Same framework as EXPORT-01 CSV endpoint |

### Marker (new pytest marker needed)

A `census_data` pytest marker must be added to `pyproject.toml` for network-gated tests. Pattern mirrors the existing `vcc_data` marker.

### Supporting

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `ingest.loaders.load()` | project | Route census-materialized AnnData through the standard loader | Always — per Phase 11 decision, use `ingest.loaders.load()` (not raw scanpy) so AnnData structure matches production |
| `ingest.pipeline.ingest_10x()` | project | QC + store the fetched AnnData | After materializing from census; source_path should be a census URI string, not a filesystem path |

---

## Architecture Patterns

### Pattern 1: Census Fetch Tool — Fits the Existing `@tool` Pattern Exactly

The four existing tools (`ingest_10x_tool`, `analyze_dataset_tool`, `annotate_cell_type_tool`, `predict_perturbation_tool`) all follow this shape:

```python
@tool("tool_name", "description", {"arg": type, ...})
async def tool_fn(args: dict[str, Any]) -> dict[str, Any]:
    try:
        result = some_pipeline_fn(args["arg"], ...)
    except Exception as exc:
        return {"content": [{"type": "text", "text": str(exc)}], "is_error": True}
    return {
        "content": [{"type": "text", "text": json.dumps({"dataset_id": result})}],
        "is_error": False,
    }
```

`fetch_census_dataset_tool` plugs in identically — the handler is `async`, the census fetch is blocking, so `asyncio.to_thread()` wraps the blocking work.

### Pattern 2: asyncio.to_thread() Wrapping for the Blocking Census Call

`cellxgene_census.open_soma()` opens a remote TileDB-SOMA collection (network I/O). `cellxgene_census.get_anndata()` materializes cells into an AnnData (more network I/O, CPU-bound array building). Both are synchronous and will block the event loop if called directly in an `async` handler. The correct pattern:

```python
# Source: installed cellxgene_census._get_anndata source (verified synchronous)
import asyncio
import cellxgene_census

async def _census_fetch_blocking(
    organism: str,
    obs_value_filter: str,
    max_cells: int,
) -> anndata.AnnData:
    def _blocking() -> anndata.AnnData:
        with cellxgene_census.open_soma() as census:
            adata = cellxgene_census.get_anndata(
                census=census,
                organism=organism,
                obs_value_filter=obs_value_filter,
                obs_coords=slice(0, max_cells),   # cell count cap
                obs_column_names=["tissue", "assay", "cell_type", "disease",
                                  "is_primary_data", "sex", "suspension_type"],
            )
        return adata
    return await asyncio.to_thread(_blocking)
```

**Critical:** `open_soma()` is a context manager — it must be entered and exited inside the same thread. The entire `with open_soma() as census: get_anndata(...)` block must be inside the `_blocking` closure passed to `asyncio.to_thread()`. Do not open the census outside the thread and pass it in.

### Pattern 3: Census obs_value_filter Syntax

The SOMA `value_filter` is a Python-like expression string evaluated server-side. Key columns and syntax:

```python
# Confirmed obs metadata columns (from official docs, verified):
# 'tissue', 'tissue_general', 'assay', 'assay_ontology_term_id',
# 'cell_type', 'cell_type_ontology_term_id', 'disease', 'sex',
# 'organism', 'suspension_type', 'is_primary_data', 'donor_id',
# 'development_stage', 'dataset_id', 'soma_joinid'

# Example filters:
"tissue_general == 'lung' and is_primary_data == True"
"tissue_general == 'lung' and assay == '10x 3\\' v3'"
"tissue in ['brain', 'heart'] and organism == 'Homo sapiens'"
"cell_type == 'B cell' and tissue_general == 'lung' and disease == 'COVID-19'"
```

Organism is passed as a positional argument to `get_anndata()`, not as a filter: `"Homo sapiens"` or `"Mus musculus"`. The `organism` parameter is NOT part of `obs_value_filter`.

### Pattern 4: Cell-Count Cap via obs_coords

Without a cap, an unrestricted tissue filter can return millions of cells. The cap uses `obs_coords=slice(0, max_cells)` — this slices by `soma_joinid` (integer row index), not by biological criteria. A reasonable default is 5000–20000 cells for analysis-ready datasets. The `obs_value_filter` acts first; `obs_coords` then slices the result.

**Important:** `obs_coords` slices by soma_joinid position, not by count of matching cells after filtering. If the filter produces cells at joinids 1M–1.1M, `slice(0, 5000)` returns 0 cells (no joinids in that range match 0–5000). The correct approach is to use `obs_coords=None` (no coords filter) and let the value filter alone determine which cells are returned, then pass a cell-count limit separately if needed — or document this limitation clearly for users.

**Verified approach:** Use `obs_value_filter` to scope the query tightly enough (specific tissue + is_primary_data == True) that the result is manageable without obs_coords, and document a warning if the result exceeds a configured maximum. Alternatively, fetch obs metadata first with `get_obs()`, take the first N `soma_joinid` values, then pass those as `obs_coords`.

### Pattern 5: Census-Aware ingest_10x() Call

The existing `ingest_10x()` loads from a file path. For census data, we must:
1. Materialize the AnnData via `get_anndata()` (in thread)
2. Write it to a temp `.h5ad` file
3. Call `ingest.loaders.load(temp_h5ad_path)` to normalize loading
4. Run QC and store (calling `ingest.pipeline.ingest_10x(temp_h5ad_path, name, ...)`)

OR: Create a parallel `ingest_from_anndata()` function in `ingest/pipeline.py` that accepts a pre-built AnnData directly (skipping the `loaders.load()` step) and runs `contract.set_counts_layer() -> qc.run() -> store.save()`. This avoids a temp file write.

The `source_path` argument to `DatasetStore.save()` must encode the census query parameters so `export/script` can reconstruct them. Suggested format:

```
"cellxgene-census:stable:Homo sapiens:tissue_general == 'lung' and is_primary_data == True"
```

This is stored in `registry.sqlite` as the `source_path` column.

### Pattern 6: Script Export — Read uns, Generate Python

The script export reads three sources:
1. `DatasetStore.list(name)` → `source_path` (census URI or file path), `qc_config`
2. `adata.uns['qc']` → QC thresholds used (redundant with qc_config in registry, but available from the store)
3. `adata.uns['analysis']` → `AnalysisConfig` fields (target_sum, n_top_genes, n_pcs, resolution, n_neighbors, random_state, and DE config)

The script generator is a pure string-rendering function. No template engine needed; f-strings with the extracted dict values are sufficient. The generated script must be self-contained: no bioclaw imports, only scanpy + cellxgene-census.

Generated script structure (for a census-sourced dataset):

```python
# Reproducible scanpy script — generated by bioclaw EXPORT-02
# Session: {session_id}, Dataset: {dataset_id}
# Generated: {timestamp}

import cellxgene_census
import scanpy as sc

# 1. Fetch dataset from cellxgene-census
#    organism: {organism}
#    filter:   {obs_value_filter}
with cellxgene_census.open_soma(census_version="{census_version}") as census:
    adata = cellxgene_census.get_anndata(
        census=census,
        organism="{organism}",
        obs_value_filter="{obs_value_filter}",
    )

# 2. QC (thresholds used in this session)
sc.pp.filter_cells(adata, min_genes={min_genes_per_cell})
sc.pp.filter_genes(adata, min_cells={min_cells_per_gene})
# max_pct_mt={max_pct_mt}
if {max_pct_mt is not None}:
    adata.var["mt"] = adata.var_names.str.upper().str.startswith("MT-")
    sc.pp.calculate_qc_metrics(adata, qc_vars=["mt"], inplace=True)
    adata = adata[adata.obs["pct_counts_mt"] <= {max_pct_mt}].copy()

# 3. Analysis
sc.pp.normalize_total(adata, target_sum={target_sum})
sc.pp.log1p(adata)
sc.pp.highly_variable_genes(adata, n_top_genes={n_top_genes})
sc.pp.pca(adata, n_comps={n_pcs}, random_state={random_state})
sc.pp.neighbors(adata, n_neighbors={n_neighbors}, random_state={random_state})
sc.tl.leiden(
    adata,
    resolution={resolution},
    flavor="igraph",
    n_iterations=2,
    directed=False,
    random_state={random_state},
)
sc.tl.umap(adata, random_state={random_state})
```

For file-sourced datasets (`source_path` is a filesystem path), replace the census fetch block with `adata = sc.read_h5ad("{source_path}")`.

The endpoint returns a `StreamingResponse` with `content-disposition: attachment; filename="{dataset_name}_analysis.py"` and `media_type="text/x-python"`. Follow the same streaming pattern as the CSV export in `webapp/backend/main.py`.

### Pattern 7: New Agent Tool Registration

After adding `fetch_census_dataset_tool` to `agent/tools.py`, it must be added to the `bioclaw_server` in `agent/server.py`:

```python
bioclaw_server = create_sdk_mcp_server(
    name="bioclaw",
    version="1.0.0",
    tools=[
        ingest_10x_tool,
        analyze_dataset_tool,
        annotate_cell_type_tool,
        predict_perturbation_tool,
        fetch_census_dataset_tool,   # NEW — DATA-01
    ],
)
```

This is the only modification to `agent/server.py`.

### Anti-Patterns to Avoid

- **Calling `open_soma()` outside `asyncio.to_thread()`:** The context manager and `get_anndata()` call must both be inside the thread. Opening outside and passing the census object in is not thread-safe.
- **Using `obs_coords=slice(0, N)` as a reliable row-count cap:** soma_joinids are not dense starting from 0 after filtering — the slice operates on the pre-filter index space.
- **Generating the script from the JSONL tool-call log:** The audit log captures tool inputs/outputs but not the raw parameter values cleanly. `adata.uns` is the canonical source of truth.
- **Importing bioclaw modules in the generated script:** The exported `.py` must be self-contained, runnable without the bioclaw codebase installed.
- **Adding new top-level dependencies:** `cellxgene-census` is already in pyproject.toml. No new packages are needed.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Census network I/O | Custom HTTP client to CZI S3 | `cellxgene_census.open_soma()` + `get_anndata()` | The census is a TileDB-SOMA array, not a file; requires the SOMA query engine for metadata pushdown |
| Asyncifying blocking calls | Custom thread pool management | `asyncio.to_thread()` | stdlib; correct way to run sync code in an async context in Python 3.9+ |
| Script templating | Jinja2 or similar template engine | f-strings with extracted dict values | No conditionals or loops in the generated script that warrant a template engine; f-strings are sufficient and add no dependency |

---

## Common Pitfalls

### Pitfall 1: Blocking the Event Loop with Census I/O
**What goes wrong:** `open_soma()` makes a network request to resolve the census URI; `get_anndata()` makes multiple network requests (S3/TileDB reads). Called directly in an `async def` handler, they block the asyncio event loop for several seconds, stalling all other requests.
**Why it happens:** TileDB-SOMA has no async API; everything is synchronous.
**How to avoid:** The entire `with open_soma() as census: get_anndata(...)` block must be wrapped in `asyncio.to_thread()`. The closure must be self-contained — do not pass the census object across thread boundaries.
**Warning signs:** The websocket stream stalls silently during census fetch; other requests time out.

### Pitfall 2: obs_coords Slice Semantics
**What goes wrong:** Developer assumes `obs_coords=slice(0, 5000)` limits output to 5000 cells; actual result is 0 cells because filtered cells have soma_joinids in the millions, outside the [0, 5000) range.
**Why it happens:** `soma_joinid` is a globally unique integer assigned at Census construction time, not an ordinal within the filtered result. The slice operates on the global index, not the filtered subset.
**How to avoid:** For a genuine cell-count cap, either (a) pre-fetch obs joinids with `get_obs()`, take the first N joinids, and pass that list as `obs_coords`, or (b) rely on tight `obs_value_filter` to scope the result, and add an explicit post-fetch check that raises if `adata.n_obs > MAX_CELLS_LIMIT`.

### Pitfall 3: Census open_soma Requires Network at Test Time
**What goes wrong:** Tests that call `fetch_census_dataset` without mocking attempt a real network connection; CI fails or tests hang.
**Why it happens:** `open_soma()` contacts CZI's S3 infrastructure on first call.
**How to avoid:** All tests that call `fetch_census_dataset_tool` with real network access must be gated by `@pytest.mark.census_data` (new marker) and `@pytest.mark.skipif` on absence of a `CENSUS_DATA` env var. Unit tests mock `cellxgene_census.open_soma` and `cellxgene_census.get_anndata` with `unittest.mock.patch`.

### Pitfall 4: source_path Lost After Census Fetch
**What goes wrong:** The `source_path` stored in `DatasetStore` is the temp `.h5ad` path (or `None`), not the census query parameters. `GET /api/export/script` cannot reconstruct the census fetch line.
**Why it happens:** `ingest_10x()` uses `source_path=str(path)` — always a filesystem path.
**How to avoid:** The census fetch tool must pass the census query string as `source_path` when calling `DatasetStore.save()` (or calling the modified `ingest_from_anndata()` wrapper). Format: `"cellxgene-census:{version}:{organism}:{obs_value_filter}"`. This is a string in an existing TEXT column; no schema change needed.

### Pitfall 5: adata.uns['analysis'] Missing if analyze() Was Never Called
**What goes wrong:** A session that only fetched a dataset (no analysis call) produces a script export endpoint with no analysis block. Or worse, `KeyError` when reading `adata.uns['analysis']`.
**Why it happens:** `adata.uns['analysis']` is written by `analysis/pipeline.py::analyze()` — it only exists if the dataset has been analyzed.
**How to avoid:** The script generator must check `adata.uns.get('analysis')` (not `adata.uns['analysis']`). If absent, emit a comment: `# No analysis was run in this session — add your analysis steps here.`

### Pitfall 6: Scrublet doublet_action in QC Script
**What goes wrong:** The generated QC block omits the doublet detection step, producing a script that does not faithfully reproduce the session QC.
**Why it happens:** Scrublet (`sc.pp.scrublet`) is a non-trivial step; easy to omit from a generated script template.
**How to avoid:** Read `adata.uns['qc']['config']['doublet_action']` and emit the corresponding code block in the generated script.

---

## Code Examples

### Census Fetch (Verified Against Installed Library Source)

```python
# Source: cellxgene_census._get_anndata (verified synchronous; asyncio.to_thread required)
import asyncio
import cellxgene_census

def _census_fetch_blocking(
    organism: str,
    obs_value_filter: str,
    obs_column_names: list[str],
    census_version: str = "stable",
) -> "anndata.AnnData":
    """Blocking function — must be run via asyncio.to_thread()."""
    with cellxgene_census.open_soma(census_version=census_version) as census:
        adata = cellxgene_census.get_anndata(
            census=census,
            organism=organism,
            X_name="raw",
            obs_value_filter=obs_value_filter,
            obs_column_names=obs_column_names,
        )
    return adata


async def census_fetch_tool_handler(organism, obs_value_filter, ...):
    adata = await asyncio.to_thread(
        _census_fetch_blocking, organism, obs_value_filter, obs_column_names
    )
    # Route through ingest pipeline...
```

### DatasetStore source_path for Census

```python
# In the census fetch pipeline (new ingest/census.py or added to ingest/pipeline.py)
census_source = (
    f"cellxgene-census:{census_version}:{organism}:{obs_value_filter}"
)
store = DatasetStore(root=store_root)
version = store.save(name, adata, source_path=census_source, qc_config=asdict(qc_config))
```

### Script Export Endpoint (FastAPI — mirrors EXPORT-01 pattern)

```python
# In webapp/backend/main.py
@app.get("/api/export/script", dependencies=[Depends(require_password)])
async def export_script(dataset_id: str, session_id: str) -> StreamingResponse:
    # Parse dataset_id "name@version"
    # Load adata from store
    # Generate script string from adata.uns and store registry
    script = generate_analysis_script(adata, dataset_record, session_id)
    safe_name = name.replace("/", "_").replace(" ", "_")
    return StreamingResponse(
        io.BytesIO(script.encode()),
        media_type="text/x-python",
        headers={"Content-Disposition": f'attachment; filename="{safe_name}_analysis.py"'},
    )
```

### pytest marker registration

```toml
# pyproject.toml [tool.pytest.ini_options] markers section — add:
"census_data: requires real network access to cellxgene-census S3; excluded from fast/CI runs"
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `column_names={"obs": [...], "var": [...]}` kwarg in `get_anndata` | `obs_column_names=[...]` and `var_column_names=[...]` as separate kwargs | cellxgene-census 1.x | The old `column_names` dict still works (FutureWarning) but will be removed; use the new kwargs |
| Raw tiledbsoma Experiment query | `cellxgene_census.get_anndata()` convenience wrapper | ~2023 | Much simpler for the common "get AnnData slice" use case |

**Deprecated:**
- `column_names={"obs": [...]}` kwarg: use `obs_column_names=[...]` instead (FutureWarning in 1.18.0, confirmed from source).

---

## Open Questions

1. **Cell-count cap strategy for DATA-01**
   - What we know: `obs_coords=slice(0, N)` does not reliably cap cell count post-filter (soma_joinid semantics). `get_obs()` + joinid list is reliable but requires an extra network round-trip.
   - What's unclear: Whether a post-fetch check (`if adata.n_obs > MAX: raise`) is sufficient UX, or whether the tool should proactively cap.
   - Recommendation: Implement a tight-filter-first strategy: require `is_primary_data == True` and tissue/organism specificity in the filter; raise a descriptive error if result exceeds a configured `MAX_CELLS` (default 50000). Document this in the tool's description string.

2. **ingest_from_anndata() vs temp-file approach**
   - What we know: `ingest_10x()` takes a path; the census AnnData is in memory.
   - What's unclear: Whether writing to a temp `.h5ad` and re-reading through `loaders.load()` adds meaningful correctness value vs. directly routing the in-memory AnnData through `contract.set_counts_layer() -> qc.run() -> store.save()`.
   - Recommendation: Add `ingest_from_anndata(adata, name, qc_config, store_root, source_path)` to `ingest/pipeline.py`. This avoids a temp file write, keeps the census AnnData in memory (which is already there), and matches the "call through the pipeline, not around it" discipline. No new public interface; this is an internal helper for the census tool.

3. **Session parameter for EXPORT-02 endpoint**
   - What we know: The script export success criterion says "from any session." The CSV export uses only `dataset_id`. A session_id may not add value if all parameters are in `adata.uns` and the store registry.
   - Recommendation: Export endpoint uses `dataset_id` only (same as CSV export). `session_id` is not needed since all reproducible parameters are stored in the dataset itself.

---

## Validation Architecture

nyquist_validation is enabled (key absent from config.json, treated as enabled).

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest 8.x |
| Config file | pyproject.toml `[tool.pytest.ini_options]` |
| Quick run command | `uv run pytest tests/ -m "not live_llm and not bio_fm_smoke and not vcc_data and not census_data" -q` |
| Full suite command | `uv run pytest tests/ -m "not live_llm and not bio_fm_smoke and not vcc_data" -q` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| DATA-01 | `fetch_census_dataset_tool` returns a `dataset_id` given organism + obs_filter (mocked census) | unit | `uv run pytest tests/test_census_tool.py -x` | ❌ Wave 0 |
| DATA-01 | Census fetch runs in `asyncio.to_thread()` (monkeypatch confirms threading) | unit | `uv run pytest tests/test_census_tool.py::test_census_fetch_runs_in_thread -x` | ❌ Wave 0 |
| DATA-01 | Resulting dataset_id is loadable by `DatasetStore` | unit | `uv run pytest tests/test_census_tool.py::test_fetched_dataset_loadable -x` | ❌ Wave 0 |
| DATA-01 | Agent tool is registered in bioclaw_server tool list | unit | `uv run pytest tests/test_census_tool.py::test_tool_registered -x` | ❌ Wave 0 |
| DATA-01 | Real census network round-trip returns >=1 cell AnnData | census_data (network) | `uv run pytest tests/test_census_smoke.py -m census_data -x` | ❌ Wave 0 |
| EXPORT-02 | `GET /api/export/script` returns 200 with `.py` content for analyzed dataset | unit | `uv run pytest tests/test_webapp_script_export.py::test_export_script_returns_py -x` | ❌ Wave 0 |
| EXPORT-02 | Generated script contains correct QC thresholds from `adata.uns['qc']` | unit | `uv run pytest tests/test_webapp_script_export.py::test_script_contains_qc_thresholds -x` | ❌ Wave 0 |
| EXPORT-02 | Generated script contains correct random_state from `adata.uns['analysis']` | unit | `uv run pytest tests/test_webapp_script_export.py::test_script_contains_random_state -x` | ❌ Wave 0 |
| EXPORT-02 | Generated script contains census fetch call for census-sourced datasets | unit | `uv run pytest tests/test_webapp_script_export.py::test_script_census_source -x` | ❌ Wave 0 |
| EXPORT-02 | Script is rejected without password | unit | `uv run pytest tests/test_webapp_script_export.py::test_script_export_requires_auth -x` | ❌ Wave 0 |
| EXPORT-02 | Dataset with no analysis emits comment, not KeyError | unit | `uv run pytest tests/test_webapp_script_export.py::test_script_no_analysis_graceful -x` | ❌ Wave 0 |

### Sampling Rate

- **Per task commit:** `uv run pytest tests/ -m "not live_llm and not bio_fm_smoke and not vcc_data and not census_data" -q`
- **Per wave merge:** `uv run pytest tests/ -m "not live_llm and not bio_fm_smoke and not vcc_data" -q`
- **Phase gate:** Full fast suite green + `census_data` smoke test green on a machine with network access before `/gsd:verify-work`

### Wave 0 Gaps

- [ ] `tests/test_census_tool.py` — DATA-01 unit tests with mocked census (mock `cellxgene_census.open_soma` and `cellxgene_census.get_anndata`)
- [ ] `tests/test_census_smoke.py` — DATA-01 real network round-trip test (`@pytest.mark.census_data`)
- [ ] `tests/test_webapp_script_export.py` — EXPORT-02 unit tests using `TestClient` + `analyzable_mtx_dir` fixture
- [ ] `pyproject.toml` update — register `census_data` pytest marker
- [ ] New `ingest/census.py` module (or addition to `ingest/pipeline.py`) — `ingest_from_anndata()` function

---

## Sources

### Primary (HIGH confidence)

- Installed `cellxgene_census._get_anndata` source — `get_anndata()` is fully synchronous; `open_soma()` is fully synchronous; `asyncio.to_thread()` required
- Installed `cellxgene_census._open` source — `open_soma()` is a context manager returning a `tiledbsoma.Collection`
- `cellxgene_census.get_anndata` docstring (installed 1.18.0) — obs metadata columns, filter syntax, obs_column_names kwarg
- Project source: `agent/tools.py`, `agent/server.py`, `ingest/pipeline.py`, `ingest/store.py`, `ingest/qc.py`, `analysis/pipeline.py`, `webapp/backend/main.py` — all read directly from filesystem

### Secondary (MEDIUM confidence)

- [cellxgene-census docs: census_query_extract](https://chanzuckerberg.github.io/cellxgene-census/notebooks/api_demo/census_query_extract.html) — verified obs column names, filter syntax examples
- [cellxgene-census quickstart](https://chanzuckerberg.github.io/cellxgene-census/cellxgene_census_docsite_quick_start.html) — context manager pattern, obs filter with multiple conditions

### Tertiary (LOW confidence)

- None required; all key claims verified against installed source or official docs.

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — cellxgene-census is installed (1.18.0); API verified from source; all other stack is existing project code
- Architecture: HIGH — tool layer pattern verified from four existing tools; census blocking behavior verified from source; store schema verified from existing code
- Pitfalls: HIGH — obs_coords semantics verified from source; source_path gap verified from existing `ingest_10x()` implementation; adata.uns gaps verified from pipeline code

**Research date:** 2026-09-16
**Valid until:** 2026-12-16 (cellxgene-census API is stable; obs schema changes are versioned; library is maturing/stable lifecycle)
