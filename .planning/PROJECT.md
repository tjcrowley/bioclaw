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

## Requirements

### Validated

(None yet — ship to validate)

### Active

- [ ] Ingest raw 10x Genomics single-cell output (`.mtx`/`.h5`) and normalize to canonical AnnData `.h5ad`
- [ ] Run standard QC on ingested data (mitochondrial %, doublet detection, low-count filtering)
- [ ] Cluster cells and compute standard analyses (differential expression) via scanpy-backed tools
- [ ] Call a bio foundation model (scGPT or Geneformer) as a tool for cell-type annotation
- [ ] Orchestrate the above via a Claude-based agent using an OpenClaw-style agentic loop (plan → tool call → observe → continue)
- [ ] Persist dataset and finding context across a multi-turn research conversation (session/memory layer)
- [ ] Researcher can ask a natural-language question and receive an interpreted answer (not raw model output) — the end-to-end demo

### Out of Scope

- Protein-structure models (ESM, AlphaFold, RFdiffusion) — deferred MVP wedge, see CONCEPT.md "Alternative angles considered"
- Raw-sequence genomics models (Evo2, DNA LMs) — ingest (FASTQ alignment/variant-calling) too heavy for MVP
- Perturbation-response prediction — plausible v2 once cell-type annotation works, not core to first demo
- Multi-tenant / external customer access, billing, auth — internal tool only until validated with Biopunk Labs
- Chat interface to the bio foundation models directly — these are tool calls, not conversational endpoints

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
- Compute/hosting for bio foundation models is an open question — self-host
  (scGPT/Geneformer are self-hostable on modest hardware) vs. hosted inference
  depends on Biopunk Labs' available GPU capacity.

## Constraints

- **Domain interop**: Must consume/produce standard single-cell formats
  (10x Genomics `.mtx`/`.h5`, AnnData `.h5ad`) — the ecosystem researchers
  already use, not a bespoke format.
- **Team**: Darren builds; Elliot Roth / Biopunk Labs is the domain expert,
  wet-lab data source, and first-user validation partner — not yet confirmed
  on scope (this roadmap hasn't been presented to him yet).
- **Deployment**: Internal tool first, no external productization in v1 scope.
- **Compute**: Bio FM hosting approach (self-host vs. hosted) unresolved
  pending Biopunk Labs' hardware — affects Phase design for the tool layer.

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| MVP wedge = single-cell transcriptomics, not protein-structure or genomics | Best balance of standardized ingest, self-hostable models, and underserved pain (manual scanpy scripting) — see CONCEPT.md comparison table | — Pending Elliot's validation |
| First user = internal Biopunk Labs tool, not customer-facing SaaS | Validate real usage before productizing externally — same path OpenClaw took | — Pending |
| Orchestrator = Claude running an OpenClaw-style agentic loop (sessions, subagents, tool routing, memory) | Reuse a proven orchestration pattern instead of building agent infrastructure from scratch | — Pending |

---
*Last updated: 2026-09-03 after initialization*
