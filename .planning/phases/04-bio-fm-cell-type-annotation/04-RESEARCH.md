# Phase 4: Bio-FM Tool Layer — Cell-Type Annotation - Research

**Researched:** 2026-09-05
**Domain:** Self-hosted bio foundation model (scGPT or Geneformer) inference for scRNA-seq cell-type annotation, paired with a `decoupler` marker-gene statistical baseline, wrapped as a Claude Agent SDK `@tool` following Phase 3's established in-process MCP pattern.
**Confidence:** MEDIUM-HIGH (scGPT vs. Geneformer practicality comparison — verified against official docs, live PyPI metadata, and GitHub issue activity, not training-data recall alone) / HIGH (`decoupler` current API existence and lightweight dependency footprint — verified via live PyPI JSON) / MEDIUM (exact current `decoupler` v2 function signatures — module-path renames confirmed, but exact kwargs not directly quotable from a fetched page this session — flagged as Open Question) / LOW (scGPT-specific compute/latency numbers on this project's actual hardware — extrapolated from one third-party CPU benchmark, not measured in this repo)

## Summary

This phase adds the project's first GPU-capable-but-not-GPU-available foundation-model dependency on top of three phases of CPU-only, lightweight Python (`scanpy`/`anndata`/`igraph`). The single most important finding is that **scGPT and Geneformer are not equally practical to self-host on this project's current CPU-only Apple Silicon dev environment**, and the choice is not close: scGPT is `pip install`-able from PyPI, explicitly supports loading pretrained weights on a plain PyTorch CPU backend (`load_pretrained` works identically on CPU/GPU/flash-attn backends — flash-attn is an optional CUDA-only extra, not a hard requirement), and ships a documented, code-complete **zero-shot reference-mapping** workflow (embed query cells with the pretrained "whole-human" checkpoint, cosine-similarity/KNN-match against a labeled reference's embeddings, propagate the reference's cell-type label) that requires **no fine-tuning step** — a good fit for "inference-only." Geneformer's official model card is unambiguous that "GPU resources are required for efficient usage," is not distributed via PyPI (requires a `git-lfs clone` of the HuggingFace repo, then `pip install .`), and its standard path to cell-type classification is a **fine-tuning** step (train a classifier head on the user's own labeled data) rather than an out-of-the-box zero-shot call — a materially heavier lift for an MVP tool that must "just work" on CPU. **Recommendation: scGPT**, with its zero-shot reference-mapping tutorial as the concrete implementation pattern.

The catch, confirmed directly against scGPT 0.2.4's live PyPI dependency metadata, is that scGPT's own dependency pins are old and heavy: `scvi-tools<1.0,>=0.16.0` (a pre-1.0 scvi-tools release line, historically capped at older Python versions and itself a large transitive dependency tree), `torch>=1.13.0` + unpinned `torchtext` (upstream-archived/deprecated by the PyTorch org — an open scGPT GitHub issue as of June 2026 tracks exactly this), `orbax<0.1.8` (a JAX-ecosystem pin), and `cell-gears<0.0.3` (notably the same `cell-gears`/GEARS package Phase 5's own research will need — this pin may already conflict with whatever version Phase 5 needs, and the two phases should coordinate on one shared isolation strategy rather than each solving it independently). None of scGPT's dependencies are individually incompatible with this project's Python `>=3.12` floor, but `scvi-tools<1.0` was never validated against Python 3.12+ and installing this whole stack into the same `venv` as the project's already-pinned `scanpy>=1.12`/`anndata>=0.13` risks a resolver conflict or a silent downgrade. **The concrete architectural implication for planning: install scGPT (and its dependency tree) into an isolated environment, not the main project `venv`**, and call it either via a subprocess/CLI boundary or a standalone (non-in-process) MCP server — Phase 3's own research already flagged this exact scenario as the reason a standalone `mcp` server exists as an alternative to the in-process `@tool` pattern ("Revisit for Phase 4, not Phase 3"). By contrast, `decoupler` (the ANNOT-02 statistical baseline) has a genuinely lightweight, modern dependency footprint (`anndata`, `scipy`, `numba`, `tqdm`, `requests`, no `torch`) confirmed via live PyPI metadata, requires only Python `>=3.11`, and can be installed directly into the main project `venv` alongside the rest of the pipeline with no isolation needed.

For ANNOT-03's ontology-metadata requirement, the pragmatic, boundable answer is: **don't build an ontology-mapping pipeline.** `cellxgene-census` — already the project's own chosen public-data source per PROJECT.md — enforces the CELLxGENE schema's `cell_type_ontology_term_id` field (a Cell Ontology, `CL:xxxxx`, term) as a required, pre-populated column on every cell in every dataset it serves. If the scGPT reference-mapping baseline's labeled reference is built from a `cellxgene-census` subsample (rather than an arbitrary hand-labeled dataset), the CL ID and reference-dataset identity travel with the reference data for free — annotation output attaches the *reference cell's* existing `cell_type_ontology_term_id` and the reference's own known identity (e.g. "cellxgene-census subsample, tissue=X, N cells"), with no separate ontology-lookup service to build or maintain.

**Primary recommendation:** Build one `annotate_cell_type` tool (mirroring `analyze_dataset_tool`'s thin-wrapper shape) that (1) calls a scGPT-backed zero-shot reference-mapping module running in an isolated environment/subprocess against a small pre-built `cellxgene-census` reference embedding index, (2) unconditionally also runs a `decoupler` `dc.mt.ora`-based marker-gene score against a PanglaoDB/CellMarker resource (installed directly, no isolation needed) over the same clustered AnnData, and (3) returns one bounded, structured JSON result carrying both calls' outputs side by side, each with `{label, confidence, reference_dataset, ontology_term_id}` — never a bare label string, and never the FM result alone.

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-------------------|
| ANNOT-01 | System calls a bio foundation model (scGPT or Geneformer) as a tool to annotate cell type from normalized expression | scGPT recommended over Geneformer (Standard Stack, Summary) — zero-shot reference-mapping tutorial (Pattern 1) is the concrete, no-fine-tuning workflow; PyPI-installable but must be isolated from the main venv (Common Pitfalls 1-2, Architecture "Isolation Boundary"). |
| ANNOT-02 | Every FM-backed annotation call is accompanied by a `decoupler`-based statistical baseline for comparison | `decoupler` 2.2.0 (live-PyPI-verified, lightweight, no `torch`) `dc.op.resource`/`dc.mt.ora` (or successor ORA-family method) against PanglaoDB/CellMarker (Standard Stack, Pattern 2). Runs directly in the main venv alongside `scanpy`/`analysis/*` — no isolation needed, confirmed fast on CPU by design (no neural inference). |
| ANNOT-03 | Annotation output includes reference dataset, confidence score, and ontology metadata — not a bare label string | `cellxgene-census`'s CELLxGENE-schema-enforced `cell_type_ontology_term_id` (CL ID) as the ontology-metadata source, attached via the scGPT reference's own pre-existing labels (Pattern 1, "Don't Hand-Roll" — ontology mapping). Confidence derived from cosine-similarity/KNN vote margin (scGPT side) and enrichment score (decoupler side) — see Pattern 3/Bounded Summary Contract. |
</phase_requirements>

## User Constraints

No `CONTEXT.md` exists for this phase yet (`/gsd:discuss-phase` has not been run) — no locked user decisions to copy verbatim. The only binding constraints found are the project-wide ones already logged in `.planning/STATE.md`/`PROJECT.md`:
- Bio-FM hosting is **self-hosted by default**, with a hosted-inference option kept available behind the same tool/client boundary (STATE.md Decisions, 2026-09-03) — the annotation tool's interface should not hard-wire "runs scGPT in-process"; keep the door open to swapping the backend for a remote inference call later without changing the tool's external contract.
- Elliot Roth (Biopunk Labs) is the real domain partner — no specific technical constraint from him is recorded yet for this phase.
- STATE.md's own Blockers/Concerns section already flags: *"Phase 4 (Bio-FM annotation): scGPT/Geneformer VRAM requirements are LOW confidence per research — verify against current model cards before implementation. Self-hosted-by-default decision... makes this sizing question load-bearing for Phase 4 planning, not just a nice-to-know."* This research directly addresses that flag (see Standard Stack, Common Pitfalls) — the answer is: **VRAM is not the binding constraint, CPU-only feasibility and dependency isolation are** (this project has no GPU today; scGPT's CPU path is confirmed real but slow, and its dependency stack is the harder self-hosting problem, not VRAM sizing).

## Standard Stack

### Core

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|---------------|
| `scgpt` | 0.2.4 (current on PyPI, verified via live PyPI JSON, 2026-09-05); `requires_python <4,>=3.7.12` | Pretrained single-cell transformer foundation model; zero-shot cell embedding + reference mapping for cell-type annotation (ANNOT-01) | Only one of the two roadmap-approved options (scGPT/Geneformer) that is PyPI-installable, has a documented zero-shot (no-fine-tuning) annotation workflow, and confirms CPU-backend support in its own `load_pretrained` API — see Summary and Pattern 1. |
| `decoupler` | 2.2.0 (current on PyPI, verified via live PyPI JSON, 2026-09-05); `requires_python >=3.11`; now published under the `scverse` org (renamed from `saezlab/decoupler-py`, per its own README) | Marker-gene-based statistical enrichment scoring — the ANNOT-02 baseline, run against PanglaoDB/CellMarker resources | Named explicitly in the phase spec; confirmed live-PyPI to have a genuinely lightweight dependency footprint (`anndata`, `scipy`, `numba`, `requests`, `tqdm`, `docrep`, `marsilea`, `adjusttext`, `session-info2` — **no `torch`**), so it installs directly into the existing project venv with no isolation concern, unlike `scgpt`. |

### Supporting

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `torch` (CPU wheel only) | `>=1.13.0` (scgpt's own floor; verify the actual resolved version once scgpt's isolated env is built) | scGPT's inference backend | Only inside the isolated scGPT environment/subprocess — never added to the main project `pyproject.toml` (see Architecture, Isolation Boundary). |
| `mcp` (official Python MCP SDK, standalone server) | `2.1.1` (per Phase 3's own research, current as of 2026-09-04) | Cross-process/cross-environment tool boundary for the scGPT-backed handler, if isolation is implemented as a standalone MCP server rather than a plain `subprocess.run` call | Needed only if the planner chooses "standalone MCP server in a second Python env" over "subprocess/CLI shim" for isolation — see Alternatives Considered. Phase 3's own research already named this exact scenario as the reason a standalone server exists (`mcp_servers={"bioclaw-fm": {"command": ..., "args": [...]}}` transport). |
| `cellxgene-census` | current (not version-pinned by this research; verify at implementation time) | Source of the labeled reference dataset for scGPT's zero-shot reference-mapping baseline, and the source of pre-existing `cell_type_ontology_term_id` (CL) values for ANNOT-03 | Used once (or occasionally) to build/refresh a small, static, checked-in-or-cached reference embedding index — not queried live on every tool call. |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| scGPT (recommended) | Geneformer | Geneformer's own model card states GPU is required "for efficient usage" (a stronger, more explicit negative signal than scGPT's "CPU works, just slower"); Geneformer's standard cell-type-classification path is fine-tuning a classifier head on labeled data, not a documented zero-shot embed-and-match workflow; not on PyPI (requires `git-lfs clone` + `pip install .`, real install friction for a self-hosted-by-default MVP). Geneformer would only become attractive if this project later needs its specific strength (single-cell perturbation/gene-network tasks) or if GPU capacity becomes available — worth a one-line note in the plan, not a blocker to revisit now. |
| Zero-shot scGPT reference mapping (recommended) | Fine-tuning scGPT's classification head on a labeled dataset | Fine-tuning would likely improve accuracy on a specific tissue/cell population but adds a training step, a labeled-dataset-curation burden, and GPU-desirable training time this MVP doesn't need yet — zero-shot reference mapping is explicitly documented by scGPT's own maintainers as adequate "with considerable accuracy" for exactly this out-of-the-box use case. |
| Isolated environment (subprocess/standalone MCP server) for scGPT (recommended) | `uv add scgpt` directly into the main project venv | scGPT's own live-PyPI dependency pins (`scvi-tools<1.0,>=0.16.0`, unpinned `torchtext`, `orbax<0.1.8`, `cell-gears<0.0.3`) are old and heavy; installing them into the same venv as this project's `scanpy>=1.12`/`anndata>=0.13` pins risks resolver conflicts or silent downgrades of packages Phase 1-3 already depend on and have tested against. Isolating scGPT protects the already-working, already-tested pipeline environment. |
| `decoupler`'s ORA-family method (recommended) | Hand-rolled marker-gene scoring (e.g. mean expression of marker genes per cluster) | `decoupler` already implements multiple statistically principled enrichment methods (ORA, ULM, etc.) with proper background/enrichment-significance handling; a hand-rolled mean-expression score has no statistical grounding and is exactly the kind of "don't hand-roll" problem this domain has a mature library for (see Don't Hand-Roll). |

**Installation (illustrative — verify exact resolved versions when building the isolated scGPT env):**
```bash
# Main project venv (no change to existing pins) -- decoupler is lightweight, no isolation needed:
uv add decoupler

# Isolated scGPT environment (NOT the main project venv) -- e.g. a separate uv-managed
# subdirectory/venv, or a Docker image, invoked via subprocess/standalone MCP server:
#   python -m venv .venv-bio-fm && .venv-bio-fm/bin/pip install scgpt
# or an equivalent uv workspace member with its own pyproject.toml/lockfile.
```

## Architecture Patterns

### Recommended Project Structure
```
agent/
├── tools.py            # existing: ingest_10x_tool, analyze_dataset_tool
│                        # + new: annotate_cell_type_tool (thin wrapper, same shape)
├── server.py            # existing bioclaw_server -- register annotate_cell_type_tool here
├── ...                  # logging.py, memory.py, session.py unchanged (PostToolUse hooks
│                        # already generalize to any tool per Phase 3's design)
annotation/
├── __init__.py
├── baseline.py          # decoupler-backed marker-gene scoring (ANNOT-02) -- runs in-process,
│                        # main venv, no isolation
├── fm_client.py          # thin client the in-process handler calls -- talks to the isolated
│                        # scGPT process via subprocess/stdio or a standalone MCP server
├── reference.py          # builds/loads the small cellxgene-census-derived reference embedding
│                        # index (cell_type, cell_type_ontology_term_id, embedding vector)
├── summary.py             # AnnotationSummary bounded dataclass(es), mirrors analysis/summary.py
└── pipeline.py             # annotate() entrypoint composing fm_client + baseline into one
                            # bounded summary, mirrors analysis/pipeline.py::analyze()

bio_fm_worker/                # SEPARATE Python environment (own pyproject.toml/venv or
├── pyproject.toml            # equivalent isolation mechanism) -- scGPT + torch + its full
├── run_scgpt_embed.py         # dependency tree live ONLY here, never in the main venv
└── ...
```
This keeps `analysis/`'s established shape (small testable modules + one composed `pipeline.py` entrypoint returning a bounded dataclass) while introducing exactly one new architectural seam — the isolated bio-FM worker boundary — that Phase 5's GEARS/`cell-gears` tool will very likely need to reuse (both `scgpt` and `cell-gears` are already coupled in scGPT's own dependency graph, per the live PyPI pin `cell-gears<0.0.3`).

### Pattern 1: scGPT zero-shot reference mapping (ANNOT-01)
**What:** Embed the query dataset's cells with scGPT's pretrained "whole-human" checkpoint, compare against a pre-built reference embedding index via cosine similarity/KNN, and propagate the nearest reference cells' cell-type label (and, per Don't Hand-Roll below, their `cell_type_ontology_term_id`) to each query cell/cluster.
**When to use:** The ANNOT-01 core annotation call. No fine-tuning step.
**Example (sketch — verify exact function names/kwargs against the installed `scgpt` version before implementation, per Open Questions):**
```python
# Source: scGPT official docs, "Reference Mapping Using cell embedding by
# pretrained scGPT model" tutorial (scgpt.readthedocs.io/en/latest/tutorial_reference_mapping.html) --
# summarized/paraphrased via WebFetch this session, exact call signatures not
# directly quoted -- confirm against the installed package's own tutorial
# notebook (tutorials/Tutorial_Reference_Mapping.ipynb in bowang-lab/scGPT)
# before writing the real implementation.
import scgpt as scg

# Runs on CPU via the same load_pretrained() call path used for GPU/flash-attn --
# confirmed in official docs: "pretrained weights can be loaded on pytorch CPU,
# GPU, and flash-attn backends using the same load_pretrained function."
ref_embed = scg.tasks.embed_data(reference_adata, model_dir="scGPT_human", gene_col="feature_name")
query_embed = scg.tasks.embed_data(query_adata, model_dir="scGPT_human", gene_col="feature_name")

# Reference mapping: propagate reference_adata.obs["cell_type"] (and
# cell_type_ontology_term_id) to query cells via cosine similarity / KNN over
# the two embedding matrices -- see tutorial for the exact helper used.
```
**Verification property:** because the reference dataset carries its own pre-existing `cell_type_ontology_term_id` (see Don't Hand-Roll), the annotation result's ontology metadata is a direct lookup on the matched reference cell(s), never a separately-computed mapping.

### Pattern 2: `decoupler` marker-gene ORA baseline (ANNOT-02)
**What:** Score each cluster (or cell) against a canonical marker-gene resource (PanglaoDB or CellMarker) using an over-representation-style enrichment method, and report the top-scoring cell type per cluster as the statistical baseline that always accompanies the FM call.
**When to use:** Unconditionally, every time `annotate_cell_type` is called — never optional (this is the literal ANNOT-02 requirement).
**Example (sketch — decoupler's public API has recently moved from `dc.get_resource`/`dc.run_ora` (v1.x) to a `dc.op.*`/`dc.mt.*` module layout (v2.x, current); confirm exact current signatures before implementation, see Open Questions):**
```python
# Source: decoupler v1.9.2 tutorial ("Cell type annotation from marker genes",
# decoupler.readthedocs.io/en/v1.9.2/notebooks/cell_annotation.html) for the
# conceptual workflow, CROSS-CHECKED against decoupler-py GitHub/PyPI metadata
# confirming a v1->v2 module rename (dc.op.*/dc.mt.* replacing dc.get_resource/
# dc.run_ora) -- exact v2 kwarg names NOT directly quoted this session, flagged
# LOW-MEDIUM confidence, verify against the installed decoupler==2.2.0 package
# (`help(dc.op.resource)`, `help(dc.mt.ora)`) before writing real code.
import decoupler as dc

markers = dc.op.resource(name="PanglaoDB", organism="human")  # or dc.get_resource() on <2.0
markers = markers[(markers["canonical_marker"] == "True") & (markers["human_sens"] > 0.5)]

dc.mt.ora(data=clustered_adata, net=markers, source="cell_type", target="genesymbol", min_n=3)
# Per-cluster top score extraction: aggregate the per-cell ORA scores by
# clustered_adata.obs["leiden"] (Phase 2's existing cluster column) and take
# the max-scoring cell_type per cluster as the baseline call + its score as
# the baseline's confidence proxy.
```
**Why this pairs well with Phase 2:** `clustered_adata` here is exactly the output of `analysis/pipeline.py::analyze()` — the annotation tool should accept an already-clustered dataset (same `name`/`version` store convention as `analyze_dataset_tool`), not re-run clustering itself.

### Pattern 3: Bounded annotation summary contract (ANNOT-03)
**What:** Mirror `analysis/summary.py`'s dataclass-per-result-type convention with a new `AnnotationSummary` (and a shared `AnnotationCall` sub-shape used by both the FM and baseline sides) so the tool never returns a bare label string.
**When to use:** The single return contract for `annotation/pipeline.py::annotate()`, following `analysis/pipeline.py::analyze()`'s `(new_dataset_id, summary_dict)` shape.
**Example:**
```python
from dataclasses import dataclass

@dataclass
class AnnotationCall:
    """One method's call for one cluster -- FM or baseline, same shape."""
    cluster: str
    label: str
    confidence: float          # scGPT: cosine-sim/KNN-vote margin; decoupler: ORA score
    reference_dataset: str     # e.g. "cellxgene-census: tissue=lung, n=5000" or "PanglaoDB (human)"
    ontology_term_id: str | None  # CL:XXXXXXX where available, None if no confident match

@dataclass
class AnnotationSummary:
    dataset_id: str | None
    fm_calls: list[AnnotationCall]        # scGPT-backed, one per cluster
    baseline_calls: list[AnnotationCall]  # decoupler-backed, one per cluster
    fm_model: str               # e.g. "scGPT (whole-human checkpoint)"
    baseline_method: str        # e.g. "decoupler ORA vs PanglaoDB (human, canonical markers)"
```
Bounding invariant (matching `analysis/summary.py`'s established rule): both `fm_calls`/`baseline_calls` are O(n_clusters), never O(n_cells) — this is a per-cluster call list, not a per-cell label array, consistent with `ClusterSummary.cluster_sizes`'s existing precedent.

### Isolation Boundary: keep scGPT/torch out of the main venv
**What:** The `annotate_cell_type_tool`'s handler (in `agent/tools.py`, in-process, same pattern as Phase 3) should call a thin `annotation/fm_client.py` function that itself either (a) shells out via `subprocess.run([...isolated venv's python.../run_scgpt_embed.py, ...])` and parses a JSON result from stdout, or (b) talks to a standalone (non-in-process) MCP server running in the isolated environment, per Phase 3's own "Alternatives Considered" note that a standalone `mcp` server is the documented path for tools that "can't share the orchestrator's Python env."
**When to use:** Any code path that imports `scgpt`/`torch` — never in `agent/`, `analysis/`, or `ingest/`'s existing modules/venv.
**Why:** scGPT's live-PyPI dependency pins (`scvi-tools<1.0,>=0.16.0`, `torch>=1.13.0`, unpinned `torchtext`, `orbax<0.1.8`, `cell-gears<0.0.3`) are old, heavy, and only loosely version-floored — installing them into the same resolved environment as this project's already-pinned `scanpy>=1.12`/`anndata>=0.13`/`igraph>=0.10.8`/`claude-agent-sdk>=0.2.152` risks the `uv` resolver either failing outright or silently selecting older versions of shared transitive dependencies (e.g. `numpy`, `numba`, `pandas`) than Phase 1-3's tests were written/passing against.
**Also matters for Phase 5:** `cell-gears<0.0.3` is scGPT's own pinned dependency, and STATE.md already separately flags Phase 5's GEARS/`cell-gears` integration as its own "environment isolation... version-sensitive" blocker. Building one reusable isolation mechanism now (subprocess shim or standalone MCP server pattern) rather than a scGPT-specific one-off avoids solving the same problem twice in back-to-back phases.

### Anti-Patterns to Avoid
- **`uv add scgpt` directly into the root `pyproject.toml`:** will pull `scvi-tools<1.0`/`torchtext`/`orbax` into the same resolved environment as the already-tested Phase 1-3 stack — high risk of a resolver conflict or silent transitive-dependency downgrade breaking existing, passing tests.
- **Treating Geneformer's "GPU resources are required for efficient usage" as a soft recommendation:** it's stated as a hard requirement in the model's own official card, not a performance tip — don't plan around "it'll probably work slowly on CPU" without first re-verifying this claim directly against the current model card at implementation time (see Open Questions).
- **Building a general-purpose ontology-mapping layer (arbitrary free-text label → CL ID) for ANNOT-03:** out of scope per the phase's own framing ("without turning this into its own ontology-mapping project") — use the reference dataset's pre-existing `cell_type_ontology_term_id` instead (see Don't Hand-Roll).
- **Making the `decoupler` baseline call conditional/optional (e.g. only run it if the FM call succeeds):** ANNOT-02's literal wording is "every FM-backed annotation call is accompanied by" the baseline — the tool handler should call both unconditionally and return both, even if one fails (mirror Phase 3's own "log the error result the same as a success result" precedent from `agent/tools.py`'s docstring).

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|--------------|-----|
| Cell-type embedding + zero-shot classification | A custom transformer/embedding model, or a hand-rolled nearest-centroid classifier over raw expression | scGPT's pretrained whole-human checkpoint + documented reference-mapping tutorial | This is precisely what a bio foundation model exists to avoid building from scratch — training data alone (this project has none of its own labeled cell-type data yet) is nowhere near sufficient to train a comparable model. |
| Marker-gene statistical scoring | Hand-rolled mean-expression-per-marker-set scoring, or a manual hypergeometric test implementation | `decoupler`'s ORA-family method (`dc.mt.ora`/successor) | `decoupler` already implements the statistically correct background/enrichment-significance handling multiple published papers rely on; a hand-rolled mean-expression score has no principled null distribution and would need its own validation the library has already done. |
| Cell-type-label-to-ontology-ID mapping | A custom free-text-label → Cell Ontology (CL) term matcher/fuzzy-matching pipeline | The reference dataset's own pre-existing, schema-enforced `cell_type_ontology_term_id` field (if the reference is sourced from `cellxgene-census`) | `cellxgene-census`'s underlying CELLxGENE schema *requires* every cell to carry a valid `CL:XXXXXXX` term (or "unknown") — this metadata already exists on the reference data for free; building a separate mapping pipeline (fuzzy string matching against the Cell Ontology's OBO/OWL file, or adopting a heavier tool like CellO/CellOntologyMapper) duplicates work that dedicated ontology-curation projects already do far more rigorously, and is explicitly out of this phase's intended scope. |
| Marker-gene reference-set curation | Hand-curating a marker-gene-to-cell-type table from papers | PanglaoDB or CellMarker 2.0, accessed via `decoupler`'s resource-retrieval function | Both are large, actively-maintained, peer-reviewed community marker databases (CellMarker 2.0: 656 tissues, 2,578 cell types, 26,915 markers) already wrapped by `decoupler`'s resource API — no reason to hand-curate a smaller, less-validated table. |

**Key insight:** every piece of domain-specific "intelligence" this phase needs (the FM itself, the statistical baseline method, the ontology vocabulary) already exists as a mature, purpose-built artifact from the single-cell/bioinformatics ecosystem — Phase 4's actual engineering work is entirely in the *plumbing* (isolating scGPT's environment, wrapping both calls in one bounded tool contract, sourcing a reference dataset with useful metadata already attached), not in any new modeling or mapping logic.

## Common Pitfalls

### Pitfall 1: scGPT's dependency pins are old, heavy, and likely to conflict with this project's already-pinned stack
**What goes wrong:** `uv add scgpt` (or `pip install scgpt`) in the main project venv pulls in `scvi-tools<1.0,>=0.16.0` (a multi-year-old release line with its own large transitive dependency tree, historically validated against older Python versions than this project's `>=3.12` floor), an unpinned `torchtext` (upstream-archived by the PyTorch project — an open scGPT GitHub issue, "#352 torchtext is Deprecated," opened June 2026, confirms this is a live, unresolved concern in the upstream repo itself), and `orbax<0.1.8` (a JAX-ecosystem pin unrelated to anything else in this project).
**Why it happens:** scGPT (`bowang-lab/scGPT`) is an actively-issue-tracked but not aggressively-dependency-modernized research-lab repository — its `setup.py`/PyPI metadata pins reflect when it was last substantially maintained for packaging, not the current PyPI/PyTorch ecosystem state.
**How to avoid:** Isolate scGPT into a separate environment (own venv/uv workspace member or container) called via subprocess or a standalone MCP server, per Architecture's "Isolation Boundary" — never add `scgpt` to the root `pyproject.toml`.
**Warning signs:** A `uv add scgpt` (or equivalent) that either fails resolution outright, or succeeds but silently changes the resolved version of `numpy`/`pandas`/`numba` that Phase 1-3's already-passing tests were written against — re-run the full fast-tier test suite (`uv run pytest tests/ -q -m "not live_llm"`) immediately after any dependency change touching the shared venv to catch this early.

### Pitfall 2: CPU-only scGPT inference is real but slow — plan for it as a latency/timeout concern, not just a feasibility concern
**What goes wrong:** A tool call that blocks for multiple minutes inside a single agentic turn is a poor interactive experience and risks hitting `ClaudeAgentOptions(max_turns=...)`/client-side timeout assumptions inherited from Phase 3's session wiring (`agent/session.py`'s `run_session()` currently has no explicit long-running-tool accommodation).
**Why it happens:** One third-party benchmark (LOW confidence, single source, not independently cross-verified) reports scGPT CPU embedding extraction at roughly 5,164 seconds (~86 minutes) for ~140,000 cells — extrapolating linearly, a dataset of a few thousand cells (plausible for this project's real 10x fixtures) would be on the order of low single-digit minutes, not hours, but this has not been measured against this repo's own fixtures or hardware.
**How to avoid:** (1) Measure actual latency against this project's own representative dataset size early in implementation (a Wave 0 spike), before committing to a synchronous in-turn tool-call design; (2) if latency is material, consider capping the query dataset to a representative per-cluster cell subsample before embedding (embedding a few hundred cells per cluster is sufficient for a majority-vote cell-type call — this is a legitimate, bounded design choice, not a hack) rather than embedding every cell in a large dataset.
**Warning signs:** A live `ClaudeSDKClient` session (mirroring Phase 3's own `live_llm`-marked integration test) that hangs or times out specifically on the annotation tool call, not on `ingest_10x`/`analyze`.

### Pitfall 3: `decoupler`'s public API has moved (v1.x → v2.x module rename) — training-data-recalled `dc.get_resource`/`dc.run_ora` calls are likely stale
**What goes wrong:** Code written from memory/training data (or copied from an older tutorial URL like `decoupler.readthedocs.io/en/v1.9.2/...`) calling `dc.get_resource(...)`/`dc.run_ora(...)` may not match the installed `decoupler==2.2.0`'s actual current API surface, which live WebSearch/GitHub evidence indicates has moved to a `dc.op.*`/`dc.mt.*` module layout (the package itself also moved orgs, `saezlab/decoupler-py` → `scverse/decoupler`).
**Why it happens:** `decoupler` is an actively-developed package (`scverse` NumFOCUS-sponsored ecosystem) that underwent a deliberate v1→v2 API reorganization; most existing tutorials/blog posts/training data predate this rename.
**How to avoid:** Before writing the real `annotation/baseline.py` implementation, run `python -c "import decoupler as dc; help(dc.op); help(dc.mt)"` (or equivalent introspection) against the actually-installed `decoupler==2.2.0` to confirm the exact current function names/kwargs — do not trust Pattern 2's sketch code verbatim, it is explicitly flagged LOW-MEDIUM confidence on exact signatures (confirmed only that the module-path rename happened, not each parameter name).
**Warning signs:** `AttributeError: module 'decoupler' has no attribute 'get_resource'`/`'run_ora'` at implementation time — this is the expected signal that the v1 API sketch needs updating to the installed v2 surface, not a sign something else is broken.

### Pitfall 4: Geneformer's "zero-shot" community usage exists but is not the officially-documented path — don't assume it's equally turnkey to scGPT's
**What goes wrong:** A `microsoft/zero-shot-scfoundation` community notebook (`Geneformer_zero_shot.ipynb`) demonstrates zero-shot Geneformer embeddings exist as a technique, which could be mistaken for an equally mature, officially-supported workflow to scGPT's own first-party reference-mapping tutorial.
**Why it happens:** Geneformer's own official documentation and model card frame downstream cell-type tasks as a fine-tuning exercise ("we strongly recommend tuning hyperparameters for each downstream task"); the zero-shot pattern is a third-party research contribution, not Geneformer's maintainers' own recommended path.
**How to avoid:** This is one more piece of evidence supporting the scGPT recommendation (Summary) — Geneformer *can* possibly be pushed into a zero-shot-like workflow by following community-contributed code, but this is materially less battle-tested/first-party-supported than scGPT's own maintained tutorial, and isn't a good foundation for an MVP tool that must reliably "just work."
**Warning signs:** N/A for this phase (Geneformer not being implemented) — flag as an Open Question only if a future phase revisits the scGPT-vs-Geneformer choice.

### Pitfall 5: The exact runtime shape of scGPT's own tool-facing API (`scg.tasks.embed_data` and whatever reference-mapping helper the tutorial actually calls) was not directly fetchable/quotable this session
**What goes wrong:** Analogous to Phase 3's own flagged gap (its research underestimated the exact `PostToolUse` hook signature, discovered only at implementation time via `inspect.signature` against the installed package) — this research's Pattern 1/2 code sketches are paraphrased from WebFetch summaries of tutorial pages, not directly-quoted, verified source code or API-reference text.
**Why it happens:** WebFetch of `scgpt.readthedocs.io`'s reference-mapping tutorial and `decoupler`'s API reference page(s) either 404'd or returned an LLM-summarized paraphrase rather than the literal notebook/API-reference content this session.
**How to avoid:** Before writing real `annotation/fm_client.py`/`annotation/baseline.py` code, directly open (or have the isolated scGPT env's Python `help()`/`inspect.signature()` against) the actual installed packages' source, exactly as Phase 3's `agent/session.py` and `agent/tools.py` docstrings record having done for `claude_agent_sdk`. Treat every function name/kwarg in this document's code sketches as a hypothesis, not a verified fact.
**Warning signs:** Any `ImportError`/`AttributeError` on the exact function names sketched in Pattern 1/2 — expected, not surprising, given this pitfall.

## Code Examples

See Pattern 1 (scGPT reference mapping), Pattern 2 (`decoupler` ORA baseline), and Pattern 3 (bounded summary dataclasses) above — each sketch is explicitly annotated with its confidence level and what still needs runtime verification, per Pitfall 5.

### Thin `@tool` wrapper following Phase 3's exact established shape
```python
# Mirrors agent/tools.py's existing ingest_10x_tool/analyze_dataset_tool shape verbatim --
# same STORE_ROOT module constant, same try/except -> {"content": [...], "is_error": True}
# pattern, same "serialize the bounded dataclass as JSON text" convention (Phase 3's own
# Pitfall 1: structuredContent is silently dropped by the in-process @tool decorator).
import json
from typing import Any

from claude_agent_sdk import tool

from annotation.pipeline import annotate

@tool(
    "annotate_cell_type",
    "Run bio-FM-backed (scGPT) cell-type annotation on a named/versioned, already-"
    "clustered dataset from the store, always paired with a decoupler marker-gene "
    "statistical baseline. Returns per-cluster calls from both methods, each with "
    "confidence, reference dataset, and Cell Ontology (CL) metadata -- never a bare label.",
    {"name": str},  # 'version' optional, omitted from schema per Phase 3's Pitfall 2 pattern
)
async def annotate_cell_type_tool(args: dict[str, Any]) -> dict[str, Any]:
    version = args.get("version")
    try:
        new_id, summary = annotate(args["name"], version=version, store_root=STORE_ROOT)
    except Exception as exc:
        return {"content": [{"type": "text", "text": str(exc)}], "is_error": True}
    return {
        "content": [{"type": "text", "text": json.dumps({"dataset_id": new_id, **summary})}],
        "is_error": False,
    }
```
Registration in `agent/server.py` follows Phase 3's identical pattern: append `annotate_cell_type_tool` to `create_sdk_mcp_server(..., tools=[ingest_10x_tool, analyze_dataset_tool, annotate_cell_type_tool])`. No change needed to `agent/session.py`'s `PostToolUse` hooks (`log_tool_call`, `record_dataset_reference`) — both already operate generically on `tool_name`/`tool_input`/`tool_response` regardless of which tool produced them, and `record_dataset_reference`'s existing `dataset_id`-in-JSON-text parsing pattern will work unchanged if `annotate()`'s summary also carries a `dataset_id` key (recommended, for consistency, even though annotation may not need to write a *new* store version the way `analyze()` does — verify this design choice during planning: does annotation output get persisted as a new dataset version, or just returned as a transient tool result?).

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|---------------|--------|
| `decoupler` `dc.get_resource()`/`dc.run_ora()` (v1.x API, `saezlab/decoupler-py` org) | `dc.op.resource()`/`dc.mt.ora()` (v2.x module layout, `scverse/decoupler` org) | Confirmed via live GitHub/PyPI evidence this session (exact version/date of the rename not pinned down — treat as "sometime before the current 2.2.0 release") | Any tutorial, blog post, or training-data-recalled code using the v1 function names will `AttributeError` against the current installed package — see Pitfall 3. |
| Standalone-server-only MCP tool integration | In-process `create_sdk_mcp_server`/`@tool` for same-venv tools (established Phase 3 pattern) | Already the case as of Phase 3 (2026-09-04) | Still correct for `decoupler`'s baseline call (same venv); **does not apply** to the scGPT-backed call, which needs the cross-environment boundary Phase 3's own research flagged as the reason a standalone server exists — this phase is the first to actually need that alternative. |

**Deprecated/outdated:**
- `torchtext` (a `scgpt` transitive dependency): archived/no-longer-actively-developed by the PyTorch org; flagged as a live, unresolved open issue in `bowang-lab/scGPT`'s own GitHub issue tracker as of June 2026 — another reason to isolate scGPT's environment rather than let this concern touch the main project venv.

## Open Questions

1. **Exact current `decoupler` v2 API signatures (`dc.op.resource`/`dc.mt.ora` or whatever the actual current function names/kwargs are).**
   - What we know: the v1→v2 module-path rename happened (confirmed via GitHub/PyPI-adjacent WebSearch evidence, current version 2.2.0, `scverse` org); the v1.x tutorial's conceptual workflow (retrieve PanglaoDB markers → run ORA → extract top score per group) is almost certainly still the right shape.
   - What's unclear: exact v2 function/parameter names — WebFetch of the versioned v1.9.2 tutorial page and an attempted v2 API-reference page either summarized-paraphrased or 404'd this session.
   - Recommendation: implementer should run `pip install decoupler==2.2.0` (or whatever `uv add decoupler` resolves) and directly introspect (`help(dc.op)`, `help(dc.mt)`, or read the installed package's own `docs/source/api.rst`) before writing `annotation/baseline.py` — treat Pattern 2's code as a conceptual sketch only.

2. **Exact scGPT reference-mapping helper function name(s), and how the "confidence" number is actually computed/exposed by the library (vs. hand-derived from raw embeddings).**
   - What we know: the tutorial exists (`Tutorial_Reference_Mapping.ipynb` in `bowang-lab/scGPT`), uses cosine similarity between query/reference embeddings, and is explicitly billed as zero-shot/no-further-training.
   - What's unclear: whether scGPT's own tutorial code directly exposes a per-cell/per-cluster confidence score (e.g. top-1 vs. top-2 cosine-similarity margin, or KNN vote fraction) or whether this needs to be hand-derived from the raw embedding comparison in `annotation/fm_client.py`.
   - Recommendation: open the actual notebook (`github.com/bowang-lab/scGPT/blob/main/tutorials/Tutorial_Reference_Mapping.ipynb`) directly at implementation time rather than relying on this research's WebFetch-summarized description of it.

3. **Does the isolated scGPT environment need to be a standalone MCP server (per Phase 3's alternative) or is a simpler `subprocess.run` + JSON-over-stdout shim sufficient for this phase's scale?**
   - What we know: Phase 3's own research explicitly named "standalone `mcp` Python SDK server (stdio subprocess)" as the documented alternative for tools needing process isolation, but a plain subprocess call (no MCP protocol involved, just a CLI script producing JSON) would also satisfy the isolation requirement with less new-dependency surface (`mcp` package) and less protocol complexity.
   - What's unclear: whether a future hosted-inference swap (per the project's own "self-hosted default, hosted-inference option kept in the architecture" decision) is better served by the MCP-server abstraction (which naturally generalizes to "a server, wherever it runs") vs. a subprocess shim (which would need its own refactor to become a network call later).
   - Recommendation: the planner should weigh this explicitly as a design decision for Wave 0 of Phase 4 — this research recommends leaning toward the simpler subprocess/CLI shim for this phase's scope (fewer moving parts, no new `mcp` dependency needed yet) unless the hosted-inference option is expected imminently, in which case building the standalone-MCP-server abstraction now avoids a near-term rewrite.

4. **Where does the scGPT reference embedding index (the labeled `cellxgene-census` subsample) get built, stored, and refreshed?**
   - What we know: `cellxgene-census` is the project's own already-decided public-data source; its schema guarantees `cell_type`/`cell_type_ontology_term_id` per cell.
   - What's unclear: whether this reference index is built once as a static, checked-in-or-cached artifact (simplest, matches this phase's "boundable" framing) or needs to be dynamically queryable/updatable — and how large a reference subsample is "enough" for reasonable annotation coverage without ballooning the isolated environment's storage/compute footprint.
   - Recommendation: start with a small, static, single-tissue-or-few-tissue reference subsample (a few thousand cells, pre-embedded once and cached) sufficient to demonstrate the tool working end-to-end — treat expanding reference coverage as a fast-follow, not a Phase 4 blocker.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest (already configured, unchanged from Phase 1-3) |
| Config file | `pyproject.toml` `[tool.pytest.ini_options]` (`testpaths=["tests"]`, `pythonpath=["."]`) |
| Quick run command | `uv run pytest tests/test_annotation_baseline.py tests/test_annotation_pipeline.py tests/test_agent_tools.py -x` |
| Full suite command | `uv run pytest tests/ -q -m "not live_llm"` |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|---------------------|---------------|
| ANNOT-02 | `decoupler`-backed baseline scoring runs against a clustered synthetic fixture and returns a per-cluster top cell-type call with a confidence/score value | unit (main venv, no isolation needed — `decoupler` has no `torch`) | `uv run pytest tests/test_annotation_baseline.py -x` | ❌ Wave 0 |
| ANNOT-01 (tool wiring, mocked FM) | `annotate_cell_type_tool`'s handler calls the FM client and baseline, and returns a valid `{"content": [...]}`-shaped dict, with the FM call itself mocked/stubbed (no real scGPT inference in the fast unit tier — mirrors Phase 3's own live-LLM exclusion precedent) | unit | `uv run pytest tests/test_agent_tools.py -k annotate -x` | ❌ Wave 0 |
| ANNOT-01 (real scGPT inference, smoke) | The isolated scGPT environment actually embeds a small synthetic/real dataset and returns a plausible cell-type call, measured for latency (Pitfall 2) | integration/smoke, excluded from default CI (analogous to `live_llm` marker), requires the isolated env to be built | `uv run pytest tests/test_bio_fm_integration.py -m bio_fm_smoke -x` (new marker, register in `pyproject.toml`) | ❌ Wave 0 |
| ANNOT-03 | `AnnotationSummary`/`AnnotationCall` dataclasses always carry non-null `reference_dataset` and `confidence`, and `ontology_term_id` is populated whenever the reference/baseline resource provides one | unit | `uv run pytest tests/test_annotation_pipeline.py -x` | ❌ Wave 0 |

### Sampling Rate
- **Per task commit:** `uv run pytest tests/test_annotation_baseline.py tests/test_annotation_pipeline.py tests/test_agent_tools.py -k annotate -x` (fast tier only — no real scGPT inference, no live LLM)
- **Per wave merge:** `uv run pytest tests/ -q -m "not live_llm and not bio_fm_smoke"` (fast tier; both the live-LLM and the real-scGPT-inference smoke tests are opt-in/manual, matching Phase 3's own precedent for `live_llm`)
- **Phase gate:** Full fast-tier suite green before `/gsd:verify-work`; at least one manual `bio_fm_smoke` run demonstrated against the isolated scGPT environment and its latency measured (closes Pitfall 2 and the STATE.md VRAM/compute-sizing blocker with real evidence, not estimation).

### Wave 0 Gaps
- [ ] `annotation/` package skeleton (mirrors `analysis/`'s existing shape: `__init__.py`, `baseline.py`, `fm_client.py`, `reference.py`, `summary.py`, `pipeline.py`)
- [ ] Isolated scGPT environment (subprocess-invokable or standalone-MCP-server-invokable — resolve Open Question 3 first) — this is the single largest new infrastructure piece this phase introduces
- [ ] A small, static, pre-built reference embedding index sourced from `cellxgene-census` (resolve Open Question 4: scope/size)
- [ ] `tests/test_annotation_baseline.py`, `tests/test_annotation_pipeline.py` — new files, unit-tested against a synthetic clustered fixture (likely reusable/extending `structured_adata` from `tests/test_fixtures.py`, per Phase 2's own precedent)
- [ ] `tests/test_bio_fm_integration.py` — new file, new `bio_fm_smoke` pytest marker registered in `pyproject.toml` (mirrors the existing `live_llm` marker's registration pattern)
- [ ] Framework install: `uv add decoupler` (main venv); scGPT installed only into the isolated environment, not the root `pyproject.toml` (see Isolation Boundary)

## Sources

### Primary (HIGH confidence)
- Live PyPI JSON API (`pypi.org/pypi/scgpt/json`, `pypi.org/pypi/decoupler/json`), fetched directly this session (2026-09-05): `scgpt` current version `0.2.4`, full `requires_dist` list (`scanpy<2.0.0,>=1.9.1`, `scvi-tools<1.0,>=0.16.0`, `torch>=1.13.0`, `torchtext`, `orbax<0.1.8`, `cell-gears<0.0.3`, etc.); `decoupler` current version `2.2.0`, `requires_python>=3.11`, full lightweight `requires_dist` list (no `torch`).
- `huggingface.co/ctheodoris/Geneformer` model card (WebFetch, this session) — model sizes (10M/104M/316M param variants), explicit "GPU resources are required for efficient usage" statement, git-lfs-clone install instructions, fine-tuning-oriented downstream-task framing.
- `github.com/bowang-lab/scGPT` README + issues page (WebFetch, this session) — `pip install scgpt "flash-attn<1.0.5"` (optional), Python `>=3.7.13`/R `>=3.6.1` floor, CPU/GPU/flash-attn `load_pretrained` compatibility statement, live issue #352 ("torchtext is Deprecated," opened June 2026) confirming the dependency-staleness concern is a current, unresolved upstream issue.
- `decoupler.readthedocs.io/en/v1.9.2/notebooks/cell_annotation.html` (WebFetch, this session) — conceptual workflow for `dc.get_resource`/`dc.run_ora`-based marker-gene cell-type annotation (v1.x API, superseded per PyPI/GitHub evidence — see Pitfall 3).
- `github.com/saezlab/decoupler-py/blob/main/README.md` (WebFetch, this session) — confirmed `scverse` org move, Python `>=3.11` floor, `pip install decoupler`/`decoupler[full]`.
- This repo's own `agent/tools.py`, `agent/server.py`, `agent/session.py`, `analysis/pipeline.py`, `analysis/summary.py`, `ingest/store.py` — read directly to determine the exact existing tool-wrapper/bounded-summary/store patterns this phase's new code must match.
- `.planning/phases/03-agent-orchestration-wiring/03-RESEARCH.md` (this repo) — Phase 3's own confirmed findings (in-process `@tool` mechanics, `structuredContent` drop, hook-callback signature verification process) and its own "standalone MCP server... revisit for Phase 4" note, directly informing this phase's Isolation Boundary recommendation.
- Web search on `cellxgene-census`/CELLxGENE schema (this session) — `cell_type_ontology_term_id` (`CL:XXXXXXX`) confirmed as a schema-required, pre-populated field.

### Secondary (MEDIUM confidence)
- WebSearch synthesis on scGPT reference-mapping tutorial content (`scgpt.readthedocs.io/en/latest/tutorial_reference_mapping.html`, and the `bowang-lab/scGPT` `Tutorial_Reference_Mapping.ipynb` notebook, referenced but not directly opened this session) — conceptual workflow (embed → cosine similarity → label propagation, "zero-shot... no further training needed") consistent across multiple independent search-result summaries, but exact function/parameter names not directly quoted from source.
- WebSearch on `decoupler` v1→v2 API rename (`dc.op.resource`/`dc.mt.ora` replacing `dc.get_resource`/`dc.run_ora`) — consistent across two independent WebSearch passes and corroborated by the live-PyPI-confirmed org/version change, but the exact current function signatures were not independently re-confirmed against a directly-fetched, current API-reference page (both attempts 404'd this session).

### Tertiary (LOW confidence)
- Single third-party CPU-inference latency benchmark for scGPT (~5,164 seconds for ~140,000 cells) — one WebSearch-summarized source, not independently cross-verified against a second source or measured against this project's own hardware/fixtures — flagged explicitly in Pitfall 2 as needing a real Wave 0 measurement before being trusted for timeout/design decisions.
- `microsoft/zero-shot-scfoundation`'s Geneformer zero-shot notebook, cited only to note its existence as a counter-consideration to the primary scGPT recommendation, not independently evaluated for maturity/correctness.

## Metadata

**Confidence breakdown:**
- Standard stack (scGPT vs. Geneformer PyPI-availability, install-path, and official GPU/CPU stance): HIGH — verified directly against live PyPI JSON metadata and each project's own official model card/README, not training-data recall.
- Standard stack (`decoupler`'s lightweight dependency footprint, version, org move): HIGH — verified directly against live PyPI JSON metadata and the package's own current README.
- Architecture (isolation-boundary recommendation): HIGH on the *problem* (scGPT's dependency pins are confirmed old/heavy via live metadata) — MEDIUM on the *specific solution shape* (subprocess vs. standalone MCP server is an original synthesis recommendation extending Phase 3's own research, not an externally-documented "the" pattern for this exact situation).
- Pitfalls (`decoupler` API rename, scGPT dependency staleness, Geneformer's GPU/fine-tuning framing): HIGH for the *fact* of each pitfall (confirmed via live metadata/official docs/live GitHub issue), MEDIUM-LOW for exact current function signatures needed to act on them (flagged explicitly in Open Questions 1-2).
- Ontology-metadata approach (`cellxgene-census`'s `cell_type_ontology_term_id`): HIGH — confirmed via direct WebSearch of the CELLxGENE schema's own documented field requirements.
- Compute/latency sizing (STATE.md's flagged blocker): MEDIUM on the qualitative conclusion ("CPU-only is feasible but slow, dependency isolation is the harder problem than VRAM sizing") — LOW on the specific quantitative latency estimate (single unverified benchmark, explicitly flagged for Wave 0 re-measurement).

**Research date:** 2026-09-05
**Valid until:** ~14 days for the `claude-agent-sdk`/tool-wiring mechanics (unchanged from Phase 3's own fast-moving-SDK caveat); ~30 days for the scGPT/Geneformer/`decoupler` ecosystem comparison (slower-moving research-software release cadence, but re-verify live PyPI metadata again before implementation if more than ~2-3 weeks elapse, since exact dependency pins are the load-bearing finding here).
