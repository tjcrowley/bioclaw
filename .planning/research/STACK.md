# Stack Research

**Domain:** Agentic harness for biological foundation models (single-cell transcriptomics MVP)
**Researched:** 2026-09-03
**Confidence:** MEDIUM-HIGH (core Python/agent stack verified against current PyPI/official docs; bio-FM hardware specifics are thinner in public docs — flagged LOW where relevant)

## Recommended Stack

### Core Technologies

| Technology | Version | Purpose | Why Recommended | Confidence |
|------------|---------|---------|------------------|------------|
| Python | 3.12+ | Runtime for the ingest/QC/analysis pipeline | Current `scanpy` (main branch and 1.12.x releases) pins `requires-python = ">=3.12"`. This is the domain-standard version for new scverse-ecosystem code as of 2026. | HIGH |
| scanpy | 1.12.4 (released 2026-08-27) | Ingest, QC, clustering, DE — the de facto single-cell analysis toolkit | It *is* the standard: `sc.read_10x_h5`/`sc.read_10x_mtx` for ingest, `sc.pp.*` for QC/normalization, `sc.tl.leiden` for clustering, `sc.tl.rank_genes_groups` for DE. Everything else in the ecosystem (squidpy, decoupler, pertpy, scvi-tools) is built to interoperate with it. Replacing hand-written researcher scripts with scanpy-backed *tools* (not a new format) is exactly what PROJECT.md's domain-interop constraint requires. | HIGH |
| anndata | 0.13.3.post0 (released 2026-08-27) | `.h5ad` canonical data structure | The project's own constraint (PROJECT.md) names `.h5ad` as the target canonical format. anndata is scanpy's data layer and is fiscally sponsored by NumFOCUS/scverse — this is not a choice, it's the ecosystem's shared substrate. Supports on-disk "backed" mode and now Zarr v3 (`zarr>=3.2` dependency) for datasets too large for memory. | HIGH |
| Claude Agent SDK (Python) | `claude-agent-sdk` 0.2.x (0.2.152 as of 2026-09-02, weekly releases) | Agent orchestration loop — sessions, subagents, tool routing, permissions | PROJECT.md explicitly wants to "reuse a proven orchestration pattern instead of building agent infrastructure from scratch." This SDK *is* that pattern (it's literally the harness Claude Code and OpenClaw-style agents run on) exposed as a Python library: `ClaudeSDKClient` gives bidirectional multi-turn sessions, built-in subagents/session-forking, and native MCP tool-calling (in-process "SDK MCP servers" or external stdio/HTTP servers). Building a custom agent loop here would duplicate work the SDK already does well. | HIGH |
| Model Context Protocol (MCP) | spec 2025-06-18 generation; `mcp` Python SDK current | Tool-calling contract between the agent and the bioinformatics/bio-FM tool layer | MCP is the standard the Claude Agent SDK uses natively for tool definitions (`mcp__server__tool` naming, `allowedTools` permissioning). Wrapping the ingest/QC/FM-inference tools as MCP tools (in-process for lightweight scanpy ops, external stdio/HTTP servers for GPU-bound FM inference) gets you typed, bounded tool calls "for free" instead of hand-rolling a function-calling dispatcher. | HIGH |
| PyTorch | 2.x (pin per bio-FM requirements, see Version Compatibility) | Deep learning runtime for scGPT / Geneformer / GEARS | All three candidate bio FMs (scGPT, Geneformer, GEARS) are PyTorch-native. No alternative framework is worth introducing — this is the universal substrate for the tool layer's model-serving side. | HIGH |

### Supporting Libraries

| Library | Version | Purpose | When to Use | Confidence |
|---------|---------|---------|-------------|------------|
| `scanpy[leiden]` (igraph + leidenalg) | leiden via `flavor="igraph"` | Clustering backend | Always for clustering. `scanpy.tl.louvain` is deprecated since scanpy 1.12; `leiden(flavor="igraph", n_iterations=2)` is the current recommended default (faster, higher-quality partitions per the library authors' own recommendation). | HIGH |
| `scanpy[scrublet]` (built-in `sc.pp.scrublet`) | ships with scanpy core | Doublet detection during QC | Default QC step for 10x droplet data — adds `doublet_score`/`predicted_doublet` to `.obs`. `scDblFinder` (R/Bioconductor) is a stronger alternative per some benchmarks but pulls in an R dependency for no MVP benefit — stay in-ecosystem with Scrublet unless annotation accuracy demands otherwise later. | MEDIUM |
| `decoupler` | current (scverse core package as of 2025 expansion) | Marker-gene-based cell-type scoring / enrichment, useful as a cheap sanity check against scGPT/Geneformer FM annotations | Use to cross-validate FM-based cell-type calls against classical marker-gene ORA scoring — cheap, fast, no GPU, good guardrail against silently trusting FM hallucination. | MEDIUM |
| `pertpy` | current (scverse core package as of 2025 expansion) | Perturbation-experiment dataset harmonization, DE scoring, metrics matching Virtual Cell Challenge-style evaluation (MAE, differential-expression score, perturbation discrimination) | Use for the perturbation-response tool: load/harmonize the Virtual Cell Challenge public dataset, and reuse its scoring utilities so BioClaw's predictions are comparable to the published benchmark task format PROJECT.md calls out. | MEDIUM |
| `cell-gears` (GEARS, Stanford SNAP lab) | pip package `cell-gears` | Perturbation-response prediction model — predicts transcriptional outcome of a gene knockdown from control profiles | This is the most directly-applicable existing model for the "predict how a cell population responds to a CRISPR knockdown" requirement — it's a published (Nat. Biotech 2023), maintained, PyG-based GNN specifically built for this task, and pairs naturally with the Virtual Cell Challenge dataset/task format. Requires its own isolated environment (pinned PyTorch Geometric stack — see Version Compatibility). | MEDIUM |
| `scgpt` (bowang-lab) | 0.2.4 (2025-03-31) | Cell-type annotation / embedding foundation model (zero-shot or fine-tuned) | Use as one of the two candidate cell-type-annotation tools named in PROJECT.md. Requires Python <4,>=3.7.12 (practically 3.8–3.10) and an isolated env — incompatible with the Python 3.12 scanpy pipeline env. Flash-attention is optional (CPU/GPU-only PyTorch backend works without it); only pin `flash-attn<1.0.5`+CUDA 11.7 if you need the speedup. | MEDIUM |
| Geneformer (NVIDIA/BioNeMo checkpoints, or CTHeodoris original) | `geneformer-10M-240530` (10.3M params) or `geneformer-106M-240530` (106M params) via NVIDIA BioNeMo, or HF `ctheodoris/Geneformer` | Alternative/complementary cell-type-annotation and gene-network foundation model | Much smaller than scGPT's typical deployment footprint — both variants are documented as compatible with Volta/Ampere/Hopper GPUs, i.e. runs comfortably on a single modern GPU (a 106M-parameter transformer is small by 2026 LLM standards). Good second option or fallback if scGPT's flash-attn/CUDA pinning proves painful to reproduce on Biopunk Labs' hardware. Exact inference VRAM figures were not published in the docs consulted — verify empirically before committing (LOW confidence on precise VRAM numbers). | LOW (hardware specifics) / MEDIUM (model choice) |
| `cellxgene-census` | current (CZI CELLxGENE Discover) | Programmatic access to public single-cell datasets (>500 datasets, ~33M+ cells, human/mouse/primate) | Use to source a public pilot/validation dataset for the internal-tool demo before Biopunk Labs' own wet-lab data is available — directly answers the open question in CONCEPT.md about a first dataset. | HIGH |
| FastMCP (or Claude Agent SDK's built-in "SDK MCP server") | `fastmcp` 4.0.2 (2026-09-02) if standalone servers needed | Framework for building the bio-FM/pipeline MCP tool servers | Claude Agent SDK's Python package already provides an in-process "SDK MCP server" mechanism (`create_sdk_mcp_server`) for lightweight tools that share the orchestrator's process — prefer this for scanpy-backed pipeline tools that don't need a separate GPU/dependency environment. Use FastMCP (a separate stdio/HTTP process) specifically for the GPU-bound bio-FM tools that must live in an isolated Python env (see Version Compatibility) — FastMCP is the standard, most widely adopted way (~70% of MCP servers per community usage) to stand up a decorator-based external MCP server in Python. | MEDIUM |
| SQLite (stdlib `sqlite3`, or DuckDB for analytics-heavy queries) | stdlib / DuckDB current | Dataset registry + structured session/finding memory | Claude Agent SDK's session store persists conversation transcripts, but BioClaw also needs domain memory ("the dataset we've been discussing," QC results, prior findings) — the same lightweight pattern OpenClaw itself uses (structured files/index, not a heavyweight vector DB) for an internal single-team tool at this scale. Don't reach for a vector database yet — see What NOT to Use. | MEDIUM |
| Modal | current (per-second billed serverless GPU) | Elastic/hosted GPU compute for bio-FM inference if Biopunk Labs lacks always-available local GPU capacity | PROJECT.md flags hosting as an open question ("self-host vs. hosted inference depends on Biopunk Labs' available GPU capacity"). Modal's scale-to-zero, per-second billing (~$0.0006/s A100, ~$0.0011/s H100) is a strong fit for an internal, low-frequency-call tool where an always-on GPU box would be wasted spend — deploy the scGPT/Geneformer/GEARS inference functions as Modal functions, call them from an HTTP-transport MCP tool. | MEDIUM |

### Development Tools

| Tool | Purpose | Notes |
|------|---------|-------|
| `uv` | Fast Python package/venv management for the orchestrator + scanpy pipeline env | Current gold-standard for pure-Python/PEP 621 projects; resolves and installs far faster than pip/poetry. Use `uv` for the orchestrator env and the scanpy pipeline env. |
| `pixi` (or conda/mamba) | Environment management for the bio-FM tool env(s) that need native CUDA/PyTorch/PyG binaries | The pure-`uv` approach struggles when native CUDA extension modules (flash-attn, PyTorch Geometric) need build-time access to a matching torch install. Use `pixi` (conda-family, purpose-built for exactly this bioinformatics dependency pattern) or plain conda/mamba for the scGPT and GEARS environments specifically. |
| `ruff` | Lint/format | Standard for new Python projects in 2025/2026; replaces flake8+black+isort. |
| `pytest` | Testing | Standard; test the pipeline tools (QC thresholds, ingest parsing) independent of any live FM/GPU calls (mock the FM tool boundary). |
| Jupyter / IPython | Exploratory dev only, not shipped in the agent runtime | Useful during pipeline development to validate scanpy steps against real 10x/CELLxGENE data before wrapping them as MCP tools — keep entirely out of the production agent path. |

## Installation

```bash
# --- Orchestrator env (Python 3.12+, uv) ---
uv venv --python 3.12 .venv-agent
uv pip install claude-agent-sdk mcp fastmcp

# --- Pipeline env (Python 3.12+, uv) — scanpy-backed ingest/QC/clustering tools ---
uv venv --python 3.12 .venv-pipeline
uv pip install "scanpy[leiden,scrublet]" anndata decoupler pertpy cellxgene-census

# --- Bio-FM env #1 (Python 3.10, conda/pixi) — scGPT ---
# Isolated: scGPT pins Python <4,>=3.7.12 and (optionally) flash-attn<1.0.5 + CUDA 11.7
pixi init scgpt-env --channel conda-forge --channel bioconda
pixi add python=3.10 pytorch
pixi run pip install scgpt  # flash-attn optional; skip for CPU/GPU-without-flash-attn baseline

# --- Bio-FM env #2 (Python 3.10, conda/pixi) — GEARS perturbation model ---
# Isolated: GEARS pins an older PyTorch Geometric stack — do not share with scGPT or scvi-tools envs
pixi init gears-env --channel conda-forge
pixi add python=3.10 pytorch pyg
pixi run pip install cell-gears

# --- Dev tooling ---
uv pip install -D ruff pytest
```

## Alternatives Considered

| Recommended | Alternative | When to Use Alternative |
|-------------|-------------|--------------------------|
| Claude Agent SDK + MCP for orchestration | LangChain / LlamaIndex agent framework | Only if you need multi-LLM-provider portability or a large pre-built tool/retriever ecosystem beyond what MCP servers cover. For BioClaw, PROJECT.md explicitly wants to reuse the OpenClaw/Claude Agent SDK pattern, and adding LangChain on top would duplicate the agent loop the SDK already provides — avoid. |
| scGPT + Geneformer as annotation tools | scVI / scANVI (scvi-tools) reference-based label transfer | If self-hosting a transformer FM proves too heavy for Biopunk Labs' hardware, or if you have good reference-labeled data, scVI-based label transfer is faster, far lower VRAM, and more mature for pure cell-type annotation (though it's not a "foundation model" in the same generalization sense, which weakens the pitch angle). Keep as a documented fallback, not the default. |
| GEARS for perturbation prediction | scGen (also in the scvi-tools/pertpy ecosystem) | scGen is simpler (VAE-based, not graph-based) and may be an easier first perturbation-prediction baseline to stand up; GEARS is the more directly comparable choice to what recent Virtual Cell Challenge submissions used. Consider prototyping the tool interface against scGen first if GEARS' PyG environment setup becomes a blocker, then swap in GEARS. |
| SQLite/DuckDB for session+dataset memory | Vector DB (Chroma, pgvector, etc.) | Only once you need semantic search over free-text findings/notes across many past sessions — premature for an internal single-team MVP. Add later if/when memory retrieval by keyword/structured lookup proves insufficient. |
| Self-host on Biopunk Labs hardware (if available) | Modal serverless GPU | Use Modal specifically when local GPU capacity is unavailable/unreliable, or when call volume is low/bursty (internal tool, not constant traffic) — the per-second billing model directly fits that usage pattern. If Biopunk Labs has a dedicated always-on GPU box, self-hosting avoids network latency and per-call cost entirely. |

## What NOT to Use

| Avoid | Why | Use Instead |
|-------|-----|-------------|
| `scanpy.tl.louvain` | Deprecated since scanpy 1.12; superseded by Leiden, which is faster and produces better-quality partitions per the algorithm authors' own guidance. | `scanpy.tl.leiden(flavor="igraph", n_iterations=2)` |
| A single shared Python environment for the whole stack | Scanpy's pipeline env requires Python 3.12+; scGPT requires Python <4,>=3.7.12 (practically ≤3.10) and version-pinned `flash-attn`/CUDA; GEARS pins an older PyTorch Geometric stack incompatible with scGPT's and scvi-tools' pinned versions. Forcing these into one venv/conda env produces unresolvable dependency conflicts. | Separate environments per concern (orchestrator, scanpy pipeline, scGPT, GEARS), bridged by MCP tool calls (stdio subprocess or HTTP), exactly as the MCP/agent-tool boundary is designed for. |
| Building a custom agent loop / function-calling dispatcher from scratch | PROJECT.md explicitly chose to reuse a proven orchestration pattern; Claude Agent SDK already provides sessions, subagents, permissioning, and native MCP tool routing — reimplementing this is wasted effort and a maintenance burden with no differentiation value (the differentiation is in the bio tool layer, not the agent loop). | Claude Agent SDK (Python) + MCP |
| Reimplementing 10x Genomics' Cell Ranger pipeline (raw BCL/FASTQ → aligned counts) | Explicitly out of scope per PROJECT.md ("Ingest raw 10x Genomics single-cell output (`.mtx`/`.h5`)" — i.e., Cell Ranger's *output*, not its input). Building an aligner/quantifier is a multi-month bioinformatics-engineering project on its own. | Consume Cell Ranger's standard output formats directly via `sc.read_10x_h5`/`sc.read_10x_mtx`; assume upstream sequencing/alignment already happened. |
| Building flash-attn from source in CI/production | Notoriously slow/fragile build (CUDA toolchain + torch-must-be-preinstalled chicken-and-egg problem widely reported in 2025/2026 community discussion). | Use prebuilt wheels matching your exact CUDA/torch/Python combination, or skip flash-attn entirely — scGPT's pretrained-weight loader supports plain PyTorch CPU/GPU backends without it (only inference/training speed is affected, not correctness). |
| A general-purpose vector database for memory from day one | Premature complexity for an internal, single-researcher-team tool with a handful of concurrent sessions; adds an operational dependency with no validated need yet. | SQLite/DuckDB-backed structured memory (dataset registry, finding log); revisit if/when semantic recall across many sessions becomes a real, observed pain point. |

## Stack Patterns by Variant

**If Biopunk Labs has a dedicated GPU (24GB+ VRAM, e.g. RTX 4090/A6000/A100):**
- Self-host scGPT, Geneformer, and GEARS as local stdio MCP servers (subprocess, isolated conda/pixi envs) invoked directly by the Claude Agent SDK orchestrator on the same machine or LAN.
- Because this avoids network latency, avoids per-call cloud cost, and keeps wet-lab data on-premises (relevant if any data governance concerns exist with Biopunk Labs' researchers' data).

**If Biopunk Labs has no reliable local GPU:**
- Deploy the bio-FM inference functions on Modal (or a similar scale-to-zero GPU provider) behind a thin HTTP MCP server; the orchestrator calls them as HTTP-transport MCP tools.
- Because per-second billing with scale-to-zero matches an internal tool's low, bursty call volume far better than renting an always-on GPU instance.

**If dataset scale grows past what fits comfortably in memory (beyond the Virtual Cell Challenge's ~300K-profile public dataset):**
- Use AnnData's backed (`sc.read_h5ad(..., backed="r")`) mode and scanpy's dask-compatible `sc.pp.*` operations; store canonical datasets as Zarr (supported natively as of anndata/scanpy's `zarr>=3.2` dependency) rather than monolithic `.h5ad` files.
- Because this avoids a rewrite later — scanpy 1.12's dask/Zarr support exists specifically for this scaling path and costs little to adopt from the start.

## Version Compatibility

| Package A | Compatible With | Notes |
|-----------|------------------|-------|
| `scanpy` 1.12.4 | `anndata` ≥0.12.14 (0.13.3.post0 recommended), Python ≥3.12, `numpy` ≥2.2.5, `zarr` ≥3.2 | Pipeline env. Do not attempt to install scGPT or GEARS into this same env. |
| `claude-agent-sdk` 0.2.x | Python ≥3.10 | Orchestrator env; can technically share the 3.12 pipeline env's Python version, but keep as its own venv to avoid the scanpy dependency tree colliding with SDK updates. |
| `scgpt` 0.2.4 | Python <4,>=3.7.12 (practically 3.8–3.10); optional `flash-attn<1.0.5` + CUDA 11.7 | Isolated env, required — incompatible Python ceiling with scanpy's 3.12 floor. |
| `cell-gears` (GEARS) | Pinned/older PyTorch Geometric stack (per pertpy maintainers' own guidance: "give it its own environment rather than sharing one with scGPT or scvi-tools") | Isolated env, required. |
| `pertpy` / `decoupler` | scanpy/anndata pipeline env | These are scverse-core and designed to interoperate directly with the pipeline env — no isolation needed. |
| MCP transport | Claude Agent SDK ≥0.2.x | stdio for local subprocess tools (scanpy pipeline, local scGPT/GEARS), HTTP/SSE for remote (Modal-hosted) bio-FM tools — mix both transport types in one `mcp_servers` config as needed. |

## Sources

- https://scanpy.readthedocs.io/en/stable/release-notes/index.html — scanpy 1.12.x release notes, Louvain deprecation (MEDIUM, cross-checked with PyPI + GitHub pyproject.toml)
- https://pypi.org/project/scanpy/ and https://raw.githubusercontent.com/scverse/scanpy/main/pyproject.toml — current version, `requires-python`, core dependency pins (HIGH)
- https://pypi.org/project/anndata/ — current anndata version (HIGH)
- https://github.com/scverse/scanpy/issues/2865 — Leiden `flavor="igraph"` becoming the recommended default (MEDIUM)
- https://code.claude.com/docs/en/agent-sdk/mcp — Claude Agent SDK MCP integration: transport types, SDK MCP servers, tool permissioning (HIGH, official docs)
- https://pypi.org/project/claude-agent-sdk/ — current SDK version, session/subagent capabilities (HIGH)
- https://pypi.org/project/fastmcp/ — current FastMCP version and positioning (MEDIUM)
- https://github.com/bowang-lab/scGPT and https://pypi.org/project/scgpt/ — scGPT Python/CUDA/flash-attn requirements, ~20GB GPU memory reported for full 20k-gene fine-tuning workloads (MEDIUM; precise inference-only VRAM not independently confirmed — LOW)
- https://docs.nvidia.com/bionemo-framework/latest/models/geneformer/ — Geneformer model variants (10M/106M params), supported GPU architectures (Volta/Ampere/Hopper); explicit VRAM figures not published (MEDIUM model info / LOW hardware specifics)
- https://github.com/snap-stanford/GEARS — GEARS/`cell-gears` installation and GPU device usage (MEDIUM)
- https://scverse.org/blog/2025-core-expansion/ — pertpy and decoupler joining scverse core (2025) (HIGH, official scverse announcement)
- https://pertpy.readthedocs.io/ and community commentary on pertpy/GEARS/scGen environment isolation (MEDIUM)
- https://chanzuckerberg.github.io/cellxgene-census/ — CELLxGENE Census Python API for public dataset access (HIGH, official docs)
- https://arcinstitute.org/news/virtual-cell-challenge-2025-wrap-up and https://arcinstitute.org/news/virtual-cell-challenge-2026 — Virtual Cell Challenge dataset/task format, evaluation metrics (HIGH, official Arc Institute source; already partially verified in PROJECT.md)
- Modal pricing/architecture (multiple aggregator sources, cross-checked for consistency: per-second billing, scale-to-zero, ~$0.0006/s A100 / ~$0.0011/s H100) (MEDIUM — aggregator-sourced pricing, not fetched directly from modal.com's pricing page; verify exact current rates before budgeting)
- Community discussion on uv/pixi/conda hybrid patterns for bioinformatics + flash-attn build issues (MEDIUM, WebSearch-sourced, consistent across multiple independent sources)

---
*Stack research for: agentic bioinformatics harness (single-cell transcriptomics MVP)*
*Researched: 2026-09-03*
