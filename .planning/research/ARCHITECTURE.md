# Architecture Research

**Domain:** Agent-orchestrated bioinformatics (LLM agent + scientific data pipeline + specialist ML models as tools)
**Researched:** 2026-09-03
**Confidence:** MEDIUM — the pattern is consistent across multiple independent 2025-2026 systems (CellAgent, CellAtria/CellExpress, OmicVerse, Biomni, scBench, ChatSpatial), but this is an actively forming subfield with no single canonical reference architecture. Component boundaries below are HIGH confidence (converge across every source found); specific infra choices (serving frameworks, GPU sizing) are MEDIUM/LOW and should be re-verified against scGPT/Geneformer's actual model cards before Phase implementation.

## Standard Architecture

### System Overview

```
┌───────────────────────────────────────────────────────────────────────┐
│                    AGENT ORCHESTRATOR (OpenClaw pattern)                │
│  ┌────────────┐  ┌────────────┐  ┌────────────┐  ┌─────────────────┐  │
│  │  Session/   │  │  Planning  │  │   Tool     │  │  Persistent      │  │
│  │  Turn Loop  │  │  (plan →   │  │   Router   │  │  Memory (dataset │  │
│  │             │  │  call →    │  │            │  │  refs, findings) │  │
│  │             │  │  observe)  │  │            │  │                  │  │
│  └─────┬──────┘  └─────┬──────┘  └─────┬──────┘  └────────┬─────────┘  │
│        └───────────────┴──────────────┬┴──────────────────┘            │
│                                        │ typed tool calls (JSON in/out) │
└────────────────────────────────────────┼────────────────────────────────┘
                                          │  (never sees raw matrices —
                                          │   only structured summaries)
┌─────────────────────────────────────────┴──────────────────────────────┐
│                            TOOL LAYER (bounded, typed)                  │
│  ┌────────────────┐   ┌────────────────────┐   ┌─────────────────────┐ │
│  │ Ingest Tools    │   │ Analysis Tools      │   │ Bio-FM Tools        │ │
│  │ ingest_10x()    │   │ cluster()           │   │ annotate_celltype() │ │
│  │ run_qc()        │   │ diff_expr()         │   │ predict_perturbation│ │
│  │ (deterministic  │   │ (scanpy-backed,     │   │ ()  (thin client →  │ │
│  │  pipeline)      │   │  deterministic)     │   │  model server)      │ │
│  └───────┬─────────┘   └──────────┬──────────┘   └──────────┬──────────┘ │
└──────────┼─────────────────────────┼───────────────────────┼───────────┘
           │                         │                        │ network/RPC
           ▼                         ▼                        ▼ boundary
┌──────────────────────────────────────────┐   ┌──────────────────────────┐
│         DATA / STATE LAYER                │   │   MODEL SERVING LAYER    │
│  ┌────────────┐  ┌────────────────────┐   │   │  (separate process(es), │
│  │ Canonical   │  │ Session/Memory     │   │   │   GPU-resident)         │
│  │ AnnData     │  │ Store (dataset     │   │   │  ┌─────────┐┌─────────┐ │
│  │ Store       │  │ refs, findings,    │   │   │  │ scGPT   ││Geneformer│ │
│  │ (.h5ad,     │  │ conversation state)│   │   │  │ server  ││ server  │ │
│  │  versioned) │  │                    │   │   │  └─────────┘└─────────┘ │
│  └────────────┘  └────────────────────┘   │   │  ┌─────────────────────┐ │
└──────────────────────────────────────────┘   │  │ Perturbation-response│ │
                                                 │  │ model server         │ │
                                                 │  └─────────────────────┘ │
                                                 └──────────────────────────┘
                          ▲
                          │ same tool contract, bypasses agent loop
┌─────────────────────────┴────────────────────────────────────────────┐
│              BENCHMARK / EVAL HARNESS (offline, out-of-band)          │
│   VCC public dataset loader → drives predict_perturbation() directly  │
│   → scores against Arc Institute's held-out ground truth              │
└─────────────────────────────────────────────────────────────────────┘
```

### Component Responsibilities

| Component | Responsibility | Typical Implementation |
|-----------|----------------|------------------------|
| Agent Orchestrator | Multi-turn session loop, planning (plan → tool call → observe → continue), tool routing, persistent memory of dataset/finding context. Never touches raw data directly. | Claude via Anthropic API, OpenClaw-style agentic loop; tool calling via native function-calling or MCP tool schema |
| Ingest Pipeline | Raw 10x `.mtx`/`.h5` → canonical `.h5ad`; standard QC (mito %, doublets, low-count filtering); versioned storage | Deterministic Python pipeline (scanpy/anndata/scanpy.pp), exposed to the agent as 1-2 coarse-grained tool calls, not a multi-step agent conversation |
| Analysis Tool Layer | scanpy-backed operations: clustering, differential expression, trajectory inference | Wrapped scanpy functions with strict typed I/O (dataset ref in, structured result out); deterministic, no LLM involvement inside the tool |
| Bio-FM Tool Layer | Bounded, typed tool wrappers around scGPT/Geneformer/perturbation models — annotate cell type, embed cells, predict perturbation response | Thin client (HTTP/gRPC) that calls a separate model-serving process; the tool wrapper itself has no GPU dependency |
| Model Serving Layer | Loads and runs bio-FM weights on GPU, exposes an inference API | Standalone Python service (FastAPI/Triton/vLLM-style) per model, GPU-resident, decoupled from the agent process |
| Data / State Layer | Canonical dataset store (versioned `.h5ad` + metadata index) and session/memory store (dataset refs, findings, conversation state) | Filesystem or object store for `.h5ad`; OpenClaw's existing session/memory primitives for conversation state |
| Benchmark/Eval Harness | Loads Virtual Cell Challenge public dataset/task, drives the perturbation-prediction tool directly (not through the full agent loop), scores against VCC's held-out ground truth | Offline runner/script, consumes the same tool contract as the agent so scoring is apples-to-apples with what a researcher would actually get |

## Recommended Project Structure

```
bioclaw/
├── agent/                    # OpenClaw-pattern orchestrator
│   ├── sessions/              # multi-turn session state
│   ├── memory/                # persistent dataset/finding memory
│   └── tool_registry/         # typed tool schemas, routes calls to tool layer
├── ingest/                    # deterministic ingest pipeline
│   ├── loaders/                # 10x .mtx/.h5 → AnnData
│   ├── qc/                     # mito %, doublet detection, filtering
│   └── pipeline.py             # single entrypoint the agent calls as a tool
├── analysis/                  # scanpy-backed analysis tools
│   ├── cluster.py
│   ├── diff_expr.py
│   └── trajectory.py
├── models/                    # bio-FM tool layer
│   ├── clients/                 # thin HTTP/gRPC clients invoked by agent tools
│   └── serving/                 # standalone GPU-resident inference services
│       ├── scgpt_server.py
│       ├── geneformer_server.py
│       └── perturbation_server.py
├── data/                       # canonical dataset store + metadata index (versioned)
├── eval/                       # benchmark harness
│   ├── vcc/                     # Virtual Cell Challenge dataset/task loader
│   └── scoring.py               # scoring against VCC ground truth, offline runner
└── shared/                     # AnnData schema conventions, typed tool I/O contracts
```

### Structure Rationale

- **`agent/` is isolated from `models/serving/`:** the orchestrator process should have zero GPU dependency. This lets the agent run anywhere (including no local GPU) while the model servers run on whatever hardware Biopunk Labs allocates — resolves the open "self-host vs. hosted" question from PROJECT.md without hard-coding a GPU dependency into the orchestrator's deployment.
- **`ingest/` and `analysis/` are deterministic, not agentic:** these are plain Python pipelines with fixed logic (QC thresholds, clustering algorithms), each exposed to the agent as a small number of coarse-grained typed tool calls. This matches the pattern seen in CellAtria/CellExpress and OmicVerse — the LLM plans and interprets, but does not micromanage every pipeline step, which keeps results reproducible.
- **`models/clients/` vs `models/serving/` split:** the tool wrapper the agent calls (`clients/`) is a thin, stateless network client; the actual model weights and GPU inference logic live in `serving/`, a separate long-running process. This boundary is the direct answer to "where does GPU inference infra fit relative to the agent" — it fits *behind* the tool layer, never inside the agent process.
- **`eval/` is structurally parallel to `agent/`, not nested under it:** the benchmark harness calls the same tool contract (`models/clients/perturbation.py`) that the agent calls, but drives it directly for deterministic, repeatable scoring — it does not go through the LLM planning loop. This lets VCC validation run in CI without burning agent/LLM calls and without planning-loop nondeterminism polluting the score.

## Architectural Patterns

### Pattern 1: Deterministic Pipeline Behind a Coarse-Grained Tool Call

**What:** Ingest/QC and scanpy analysis steps are implemented as ordinary, deterministic Python functions/pipelines. The agent invokes them as a small number of typed tool calls (`ingest_10x(path)`, `run_qc(dataset_id, params?)`, `cluster(dataset_id, resolution?)`) rather than reasoning step-by-step through each pipeline stage.
**When to use:** Any operation with a well-defined, reproducible bioinformatics procedure (QC thresholds, standard scanpy workflows). This is most ingest and analysis work.
**Trade-offs:** Loses some flexibility (agent can't improvise a novel QC heuristic mid-pipeline) but gains reproducibility, testability, and speed — critical for scientific validity. Confirmed pattern across CellAtria/CellExpress and OmicVerse's agent-enabled framework.

### Pattern 2: Bio-FM as Bounded Typed Tool, Never a Chat Endpoint

**What:** scGPT/Geneformer/perturbation models are wrapped so the agent calls them with structured input (dataset reference + operation) and receives structured output (embeddings, cell-type labels, predicted expression deltas) — never a free-form conversation with the model.
**When to use:** Every bio-FM integration point. This is explicitly required by PROJECT.md ("Chat interface to the bio foundation models directly" is out of scope).
**Trade-offs:** None significant — this is the correct pattern; the alternative (treating a bio-FM as conversational) doesn't map to how these models work (they embed/predict/score, they don't converse) and would reintroduce hallucination risk on structured biological output.

### Pattern 3: Model Serving Decoupled from the Agent Process (Client/Server Split)

**What:** GPU-resident bio-FM inference runs as a separate long-lived service (one per model, or a shared inference server), reachable over a local network/RPC boundary. The agent's tool layer holds a thin client, not the model weights.
**When to use:** Any model requiring GPU inference. Applies to scGPT, Geneformer, and the perturbation-response model.
**Trade-offs:** Adds a network hop and a second deployable, but decouples GPU capacity planning from agent iteration — the agent can be redeployed/updated without touching model servers, and vice versa. It also directly resolves PROJECT.md's open question (self-host vs. hosted inference) since the client/server boundary is identical either way — only the endpoint URL changes.

```python
# tool layer (no GPU dependency)
def annotate_celltype(dataset_id: str) -> dict:
    adata_ref = data_store.get(dataset_id)
    result = scgpt_client.post("/annotate", {"dataset_ref": adata_ref})
    return {"cell_types": result["labels"], "confidence": result["scores"]}

# separate process, GPU-resident
# models/serving/scgpt_server.py — loads scGPT weights once, serves /annotate, /embed
```

## Data Flow

### Primary Flow: Raw Data → Interpreted Answer

```
Raw 10x output (.mtx/.h5)
    ↓  ingest_10x()  [deterministic pipeline]
Canonical AnnData (.h5ad) — versioned, stored, referenced by dataset_id
    ↓  run_qc()  [deterministic pipeline]
QC'd AnnData (mito%, doublets flagged, low-count filtered) — new version
    ↓  agent plans: cluster() → annotate_celltype() → diff_expr() → predict_perturbation()
Analysis tool layer (scanpy) + Bio-FM tool layer (scGPT/Geneformer/perturbation) operate
on the same canonical AnnData, writing results into .obs/.uns or a derived AnnData
    ↓  each tool returns a small structured JSON summary (NOT the full matrix)
Agent context accumulates structured findings across tool calls
    ↓  agent synthesizes
Natural-language answer to researcher, with session memory recording dataset_id +
key findings so a follow-up question ("what about cluster 3?") doesn't require
re-stating context
```

### Key Data Flows

1. **Ingest → canonical store:** raw lab data enters exactly once through the deterministic ingest pipeline; everything downstream (agent, analysis tools, bio-FM tools) references the canonical `.h5ad` by `dataset_id`, never re-parses raw 10x files. This is the single point of format normalization.
2. **Tool call → structured summary → agent context:** large artifacts (full AnnData matrices, embeddings) never enter the agent's context window. Tools write full results to the data store and return a bounded JSON summary (cluster counts, top DE genes, predicted-vs-control deltas). This keeps the agent loop fast and avoids context-window blowup on large single-cell matrices.
3. **Bio-FM inference → network boundary:** any call touching scGPT/Geneformer/the perturbation model crosses a client/server boundary (agent tool layer → model serving process). This is the one flow that requires GPU and is the natural place to add batching/queuing later if concurrent researchers show up.
4. **Eval harness → tool layer, bypassing the agent:** VCC benchmark scoring calls `predict_perturbation()` directly against VCC's public dataset, using the exact same tool contract and model server the agent uses in production — this validates the *tool*, and by extension what the agent can actually deliver, without agent-loop nondeterminism in the score.

## Scaling Considerations

| Scale | Architecture Adjustments |
|-------|--------------------------|
| Single researcher, internal (v1 target) | Single-box deployment: agent process + tool layer as one local service, one GPU box (Biopunk Labs hardware) running model servers, local filesystem for the AnnData store. No queue needed. |
| Small lab team (multiple concurrent researchers) | Add a job queue for ingest/analysis pipeline runs (long-running QC/clustering shouldn't block the agent's turn loop); shared dataset store (NAS or S3-compatible) instead of local filesystem; per-researcher session isolation in the memory layer; bio-FM servers may need request queuing/batching if concurrent tool calls exceed single-GPU throughput. |
| External/multi-tenant (explicitly out of scope in v1) | Proper inference serving (batching-aware server, e.g. Triton or vLLM-style) for bio-FMs; auth/tenancy on both the agent session layer and the dataset store; ingest pipeline likely needs a real workflow manager (Nextflow/Snakemake) invoked as an agent tool rather than a single Python function. |

### Scaling Priorities

1. **First bottleneck:** GPU inference throughput once more than one researcher is calling bio-FM tools concurrently — single-request model servers will queue. Fix: add request batching or a queue in front of the model serving layer before touching the agent orchestrator.
2. **Second bottleneck:** Dataset store contention/versioning once multiple researchers reference and mutate `.h5ad` files concurrently — local filesystem versioning breaks down. Fix: move to an object store with explicit dataset versioning/locking before scaling past a single-user internal tool.

## Anti-Patterns

### Anti-Pattern 1: Agent-in-the-Loop for Every Pipeline Step

**What people do:** Let the LLM decide QC thresholds, filtering cutoffs, or clustering parameters cell-by-cell or step-by-step via chain-of-thought, instead of calling a deterministic pipeline.
**Why it's wrong:** Nondeterministic, slow, expensive (many LLM calls for what should be one function call), and breaks scientific reproducibility — the same raw data could QC differently across runs.
**Do this instead:** Ingest/QC/standard analysis are deterministic pipelines with sane defaults, exposed as a small number of coarse-grained tools. The agent can override specific parameters (e.g., "use a stricter mito% cutoff") but doesn't micromanage the procedure.

### Anti-Pattern 2: Loading Model Weights in the Agent Process

**What people do:** Import scGPT/Geneformer directly into the same process as the agent loop for simplicity.
**Why it's wrong:** Ties agent uptime and deployability to GPU availability; makes the agent process heavyweight and hard to redeploy independently; blocks the "self-host vs. hosted" decision from being deferred, since the model becomes structurally baked into the agent's deployment target.
**Do this instead:** Model serving is always a separate process/service behind a stable client API, regardless of whether it's self-hosted on Biopunk Labs hardware or hosted elsewhere.

### Anti-Pattern 3: Chat Interface to a Bio Foundation Model

**What people do:** Expose scGPT/Geneformer as something the researcher (or the agent) can "converse" with directly.
**Why it's wrong:** These models embed/classify/score — they have no dialogue capability, and forcing conversational framing around structured outputs invites hallucinated interpretation. Explicitly excluded in PROJECT.md's scope.
**Do this instead:** Bio-FMs are always invoked through bounded, typed tool calls; the agent (not the model) does the natural-language interpretation of the structured output.

### Anti-Pattern 4: Streaming Full AnnData Objects Through Agent Context

**What people do:** Return raw matrices, full `.obs`/`.var` tables, or entire embeddings as tool output so the agent "has everything."
**Why it's wrong:** Single-cell matrices are large (hundreds of thousands of cells × thousands of genes); this blows the context window, wastes tokens, and doesn't help the LLM reason better.
**Do this instead:** Tools write full results to the data store (referenced by ID) and return small structured summaries (counts, top genes, confidence scores) sized for agent context.

## Integration Points

### External Services

| Service | Integration Pattern | Notes |
|---------|---------------------|-------|
| Anthropic Claude API | Agent orchestrator's LLM backend, native tool/function calling | Core dependency for the agentic loop; same integration point OpenClaw already uses |
| Bio-FM model weights (scGPT, Geneformer) | Downloaded checkpoints (typically via HuggingFace Hub or the models' own repos), loaded into the model serving layer at process start | Both are self-hostable on modest single-GPU hardware per PROJECT.md's own framing (LOW confidence on exact VRAM figures — verify against current scGPT/Geneformer model cards before Phase implementation, as checkpoint sizes vary by variant) |
| Virtual Cell Challenge public dataset (Arc Institute) | Downloaded once by the eval harness, not the live agent; ~300K scRNA-seq profiles, H1 hESC cells, 300 CRISPRi perturbations, 10x Genomics Flex chemistry | 2026 challenge format is zero-shot (no training set released — models predict on unperturbed baseline + gene list only); confirm current-year task format at virtualcellchallenge.org / arcinstitute.org before building the harness, since format changed between 2025 and 2026 |
| GPU compute (self-hosted vs. cloud) | Model serving layer is a stable client/server boundary regardless of where the server runs | Open per PROJECT.md — decouple this decision from the tool layer design so it can be resolved later without rework |

### Internal Boundaries

| Boundary | Communication | Notes |
|----------|---------------|-------|
| Agent Orchestrator ↔ Tool Layer | Typed function/tool calls (JSON in/out), native Claude tool calling or MCP-style tool schema | Agent never sees raw data — only structured tool results sized for context |
| Tool Layer ↔ Data/State Layer | Direct file I/O / AnnData object handles (dataset_id → `.h5ad` path/version) | Not exposed to the agent directly; tool layer owns all reads/writes to canonical datasets |
| Analysis Tools ↔ Bio-FM Tools | No direct coupling — both operate on the same canonical AnnData store; the agent composes them at the orchestration level (e.g., cluster, then annotate) | Keeps ingest/analysis and bio-FM concerns independently testable and deployable |
| Bio-FM Tool Layer ↔ Model Serving Layer | HTTP/gRPC client-server call, crosses process (and possibly host) boundary | This is the one boundary that carries GPU dependency; everything else in the tool layer is CPU-only |
| Eval Harness ↔ Tool Layer | Calls the same `predict_perturbation()` contract directly, bypassing the agent's planning loop | Ensures benchmark scoring reflects what the tool actually does, not agent-loop variance |

## Suggested Build Order (Dependency-Driven)

1. **Ingest pipeline** (raw 10x → canonical `.h5ad` + QC) — foundational; every other component depends on canonical data existing. Build and test standalone (no agent, no bio-FM) against a public dataset.
2. **Analysis tool layer** (scanpy-backed cluster/DE) — depends only on canonical AnnData from step 1. Validate as plain Python functions before wrapping as agent tools; this proves the "coarse-grained deterministic tool" contract cheaply.
3. **Agent orchestrator wiring** (OpenClaw-style session/memory/tool routing) — wire the loop to call the tools from steps 1-2 first, since they're CPU-only and deterministic. This validates the tool-calling contract and session/memory behavior before adding GPU complexity.
4. **Model serving layer + Bio-FM tool layer** (scGPT/Geneformer annotation) — add once the tool contract is proven; this is where the self-host vs. hosted GPU decision must be resolved.
5. **Perturbation-prediction tool** — builds directly on the model serving infra from step 4; this is the tool the VCC benchmark will exercise.
6. **Benchmark/eval harness** (Virtual Cell Challenge) — built last; consumes the perturbation tool from step 5 directly (not through the full agent loop) for repeatable scoring. This is the validation step, not a build dependency for anything else — nothing downstream needs it, but it needs everything upstream.

This ordering front-loads the deterministic, agent-independent pieces (ingest, analysis) so the hardest infra decision (GPU model serving) is made only once the tool-calling pattern is already proven end-to-end on cheap, CPU-only tools.

## Sources

- [An agentic AI framework for ingestion and standardization of single-cell RNA-seq data analysis (CellAtria/CellExpress) — npj Artificial Intelligence](https://www.nature.com/articles/s44387-025-00064-0) — MEDIUM confidence, abstract/search-summary level detail on the two-component agent+pipeline architecture
- [CellAgent: LLM-Driven Multi-Agent Framework for Natural Language-Based Single-Cell Analysis — bioRxiv](https://www.biorxiv.org/content/10.1101/2024.05.13.593861v4) — LOW/MEDIUM confidence, full architectural detail not accessible via abstract alone
- [OmicVerse: An Agent-Enabled Unified Framework for Bulk, Single-Cell, and Spatial Transcriptomics Data Analysis — Stanford Digital Repository](https://purl.stanford.edu/cv694yk7414) — MEDIUM confidence, confirms agent-enabled framework integrating scGPT/Geneformer/CellPLM for embeddings/annotation
- [Biomni — snap-stanford/Biomni GitHub](https://github.com/snap-stanford/biomni) — MEDIUM confidence, confirms retrieval-augmented planning + code-execution pattern and MCP server support for general biomedical agents
- [scBench: Evaluating AI Agents on Single-Cell RNA-seq Analysis — arXiv](https://arxiv.org/pdf/2602.09063) — MEDIUM confidence, confirms benchmark-as-separate-harness pattern (task definitions, real-workflow-derived problems, agent interface decoupled from scoring)
- [Large language model agents for biological intelligence across genomics, proteomics, spatial biology, and biomedicine — Briefings in Bioinformatics](https://academic.oup.com/bib/article/27/2/bbag110/8540361) — MEDIUM confidence, survey-level confirmation of "LLM plans/orchestrates, does not process raw data directly" pattern
- [ChatSpatial: Schema-Enforced Agentic Orchestration for Reproducible and Cross-Platform Spatial Transcriptomics — bioRxiv](https://www.biorxiv.org/content/10.64898/2026.02.26.708361v3.full) — LOW confidence, search-summary only; supports the "tools with strict typed I/O specifications" pattern
- [The 2026 Virtual Cell Challenge: predicting perturbation responses in cell contexts a model has never seen — Arc Institute](https://arcinstitute.org/news/virtual-cell-challenge-2026) — HIGH confidence, official source on current-year (zero-shot) task format
- [Virtual Cell Challenge: Toward a Turing test for the virtual cell — Cell](https://www.cell.com/cell/fulltext/S0092-8674(25)00675-0) — HIGH confidence, official framing paper for the benchmark's design rationale and dataset structure
- [Virtual Cell Initiative — Arc Institute](https://arcinstitute.org/virtual-cell-initiative) — HIGH confidence, official program page
- [Model Context Protocol: The unexpected catalyst of a bioinformatics interoperability revolution — PLOS Computational Biology](https://journals.plos.org/ploscompbiol/article?id=10.1371%2Fjournal.pcbi.1014543) — MEDIUM confidence, confirms MCP's client-server architecture as the emerging standard for tool integration in bioinformatics agents
- scGPT/Geneformer VRAM and deployment sizing — LOW confidence, not independently verified this session; general knowledge that both are single-GPU-class models (scGPT ~tens of millions of parameters, Geneformer 6-12 layer BERT-scale) but exact figures should be re-checked against current model cards before Phase 4 implementation

---
*Architecture research for: Agent-orchestrated bioinformatics (BioClaw)*
*Researched: 2026-09-03*
