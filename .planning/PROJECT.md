# BioClaw

## What This Is

An agentic harness for biological foundation models, built on OpenClaw's
orchestration pattern (LLM agent + sessions + subagents + persistent memory +
tool routing) and retargeted at computational biology. A researcher describes
an analysis in plain language; the agent ingests raw lab data, QCs and
processes it through a bioinformatics pipeline, calls bio foundation models as
tools, and reports back — instead of the researcher hand-writing and debugging
scanpy scripts. Built as a new product/venture with Biopunk Labs (Elliot Roth)
as domain/wet-lab partner; first user is Biopunk Labs' own researchers.

## Core Value

A Biopunk Labs researcher can ask a plain-language question about a
single-cell dataset and get back a QC'd, annotated, interpreted answer without
writing a scanpy script by hand.

## Current Milestone: v1.2 Real Data + Bio FM Integration

**Goal:** Replace synthetic demo data with real public single-cell datasets, wire real bio foundation model inference into the annotation and perturbation tools, surface session conversation history in the UI, add result export, and ship a Docker compose that lets any researcher run the full stack with one command.

**Target features:**
- cellxgene-census query tool — agent can fetch real public datasets by query (tissue, organism, assay) without a file upload
- Direct `.h5ad` upload support — the standard single-cell format, not just the MTX trio
- Real scGPT cell-type annotation — replace the subprocess shim stub with a working inference call against a real scGPT checkpoint
- Geneformer perturbation prediction — add Geneformer as a second perturbation-response model option alongside the current linear baseline
- Session history replay — resuming a session shows the prior conversation thread, not just a "Resuming…" message
- Result export — download cluster assignments, DE tables, and annotation results as CSV; export the conversation's analysis as a reproducible scanpy script
- Docker compose deployment — `docker compose up` starts the full stack (backend + frontend + optional GPU worker) with no manual setup steps

## Requirements

### Validated

- Single-cell transcriptomics MVP wedge matches Biopunk Labs' actual daily bioinformatics pain point (confirmed 2026-09-03)
- Bio-FM hosting: self-hosted by default, with a hosted-inference option/fallback built into the architecture (confirmed 2026-09-03)
- First dataset: public data (e.g. `cellxgene-census`, VCC's own public dataset) — not waiting on in-house wet-lab data to start the build (confirmed 2026-09-03)
- Virtual Cell Challenge scope: benchmark against VCC's public task format and official metrics — not a competitive entry against the live 2026 leaderboard (confirmed 2026-09-03)
- Ingest raw 10x Genomics single-cell output (`.mtx`/`.h5`) and normalize to canonical AnnData `.h5ad` (v1.0, shipped 2026-09-11)
- Run standard QC on ingested data (mitochondrial %, doublet detection, low-count filtering) (v1.0, shipped 2026-09-11)
- Cluster cells and compute standard analyses (differential expression) via scanpy-backed tools (v1.0, shipped 2026-09-11)
- Call a bio foundation model (scGPT or Geneformer) as a tool for cell-type annotation (v1.0, shipped 2026-09-11)
- Call a perturbation-response model as a tool, predicting how a cell population responds to a genetic perturbation (CRISPR knockdown) given control profiles (v1.0, shipped 2026-09-11)
- Orchestrate the above via a Claude-based agent using an OpenClaw-style agentic loop (plan → tool call → observe → continue) (v1.0, shipped 2026-09-11)
- Persist dataset and finding context across a multi-turn research conversation (session/memory layer) (v1.0, shipped 2026-09-11)
- Researcher can ask a natural-language question and receive an interpreted answer (not raw model output) — the end-to-end demo (v1.0, shipped 2026-09-11)
- Agent's perturbation predictions can be evaluated against the Virtual Cell Challenge's public dataset/task format (Arc Institute) as an external, credible benchmark (v1.0, shipped 2026-09-11)
- Password-gated FastAPI backend wraps `ask_question()` as HTTP/WebSocket endpoints with live tool-call streaming (v1.1, shipped 2026-09-12)
- Session list/resume endpoints backed by `SessionMemory` (v1.1, shipped 2026-09-12)
- Dataset upload endpoint invoking `ingest_10x` as part of the conversation flow (v1.1, shipped 2026-09-12)
- Vanilla-JS chat frontend: message thread, live activity view, citation resolution, session sidebar, upload control, login gate, OpenClaw-styled visuals (v1.1, shipped 2026-09-14)
- Webapp ships self-contained with no OpenClaw dependency; runs via single documented command (v1.1, shipped 2026-09-15)

### Active

- [ ] cellxgene-census query tool — researcher asks for a dataset by tissue/organism/assay, agent fetches it from the public census without a file upload
- [ ] Direct `.h5ad` upload support — standard single-cell format accepted alongside the existing MTX trio
- [ ] Real scGPT cell-type annotation — working inference against a real checkpoint, not the subprocess stub
- [ ] Geneformer perturbation prediction — second perturbation-response model option
- [ ] Session history replay — resuming a session renders the prior conversation thread in the chat UI
- [ ] Result export — CSV download for clusters/DE/annotations; reproducible scanpy script export
- [ ] Docker compose deployment — one command starts the full stack from a clean checkout

### Out of Scope

- Protein-structure models (ESM, AlphaFold, RFdiffusion) — deferred MVP wedge, see CONCEPT.md "Alternative angles considered"
- Raw-sequence genomics models (Evo2, DNA LMs) — ingest (FASTQ alignment/variant-calling) too heavy for MVP
- Formal Virtual Cell Challenge competition entry/leaderboard submission — using it as a benchmark dataset and task format, not committing to compete for the prize in v1
- Multi-tenant / external customer access, billing, full auth (OAuth, per-user accounts, RBAC) — internal tool until validated with Biopunk Labs; v1.1 adds only a shared-password gate, not multi-tenancy
- Chat interface to the bio foundation models directly — these are tool calls, not conversational endpoints
- Public/production DigitalOcean deployment — v1.1 builds and verifies the webapp locally only; going live requires Darren's explicit go-ahead

## Context

- Companion docs already exist in this repo: `README.md` (pitch) and
  `CONCEPT.md` (architecture draft + wedge rationale) — written before this
  PROJECT.md, both already reflect the decisions below.
- Domain ecosystem standard: Python + scanpy/AnnData for single-cell analysis.
  Any ingest/analysis tooling needs to interoperate with `.h5ad`, the de facto
  standard.
- MVP wedge (single-cell transcriptomics) was chosen over protein-structure
  (crowded field — Chai Discovery, EvolutionaryScale, Xaira are funded
  competitors) and genomics/DNA-LM (ingest pipeline alone — raw FASTQ →
  aligned, variant-called data — is a project in itself, too slow for a first
  demo).
- Sister ventures with the same partner (Elliot Roth / Biopunk Labs) already
  exist: [Cardiac Base Editor](https://github.com/tjcrowley/cardiac-base-editor)
  (mRNA design pipeline) and [FDT-BioTech](https://github.com/tjcrowley/fdt-biotech-digital-twins)
  (digital twins, NSF-targeted). BioClaw is a separate, new venture — not an
  extension of either — but overlap on data/validation is worth checking with
  Elliot.
- Compute/hosting for bio foundation models: self-hosted by default
  (scGPT/Geneformer are self-hostable on modest hardware), with a hosted
  inference option kept available in the tool-layer/client-server split for
  cases self-hosted capacity can't cover.
- **Virtual Cell Challenge** (virtualcellchallenge.org): an annual public
  benchmark competition launched 2025 by Arc Institute, sponsored by NVIDIA,
  10x Genomics, and Ultima Genomics ($100K grand prize in 2025; recurring in
  2026). Task: given non-targeting control scRNA-seq profiles, predict how
  cell lines respond to specified CRISPR gene knockdowns; scored against new
  Arc-generated experimental data the model never trained on. Public dataset:
  ~300K scRNA-seq profiles, H1 hESC cells, 300 CRISPRi perturbations, 10x
  Genomics Flex chemistry. This is directly BioClaw's perturbation-prediction
  use case with an existing public dataset, task format, and credible external
  benchmark already built by a major AI-bio institute — strong validation that
  the wedge is real and a strong candidate framing for the pitch to Elliot.

## Constraints

- **Domain interop**: Must consume/produce standard single-cell formats
  (10x Genomics `.mtx`/`.h5`, AnnData `.h5ad`) — the ecosystem researchers
  already use, not a bespoke format.
- **Team**: Darren builds; Elliot Roth / Biopunk Labs is the domain expert,
  wet-lab data source, and first-user validation partner.
- **Deployment**: Internal tool first, no external productization in v1 scope.
- **Compute**: Bio FM tool layer must support self-hosted inference as the
  default, with a hosted-inference option available behind the same
  client/server boundary — not a hard either/or choice.

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| MVP wedge = single-cell transcriptomics, not protein-structure or genomics | Best balance of standardized ingest, self-hostable models, and underserved pain (manual scanpy scripting) — see CONCEPT.md comparison table | Confirmed — matches Biopunk Labs' actual daily pain point |
| First user = internal Biopunk Labs tool, not customer-facing SaaS | Validate real usage before productizing externally — same path OpenClaw took | Confirmed |
| Orchestrator = Claude running an OpenClaw-style agentic loop (sessions, subagents, tool routing, memory) | Reuse a proven orchestration pattern instead of building agent infrastructure from scratch | Confirmed |
| Bio-FM hosting = self-hosted default, hosted-inference option available | Biopunk Labs GPU capacity may not always cover inference load; client/server tool-layer split defers this cleanly either way | Confirmed |
| First dataset = public (e.g. `cellxgene-census`, VCC public dataset) | Don't block the build on in-house wet-lab data availability/timing | Confirmed |
| VCC benchmark scope = public task format + official metrics, not the live 2026 leaderboard | Leaderboard is zero-shot/cross-cell-line — a materially harder, out-of-scope bar; task-format benchmarking is achievable and still credible | Confirmed |

---
*Last updated: 2026-09-15 after starting v1.2 Real Data + Bio FM Integration milestone*
