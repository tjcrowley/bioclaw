# Concept Draft — BioClaw

Status: **DRAFT v0.1** — starting point for discussion with Elliot, not a final proposal.

## The angle

OpenClaw's core insight is orchestration, not model quality: a general-purpose LLM
runs an agentic loop (plan → call tools → observe → continue) with persistent
sessions and memory, and the tools are what make it useful for a specific domain.

Biological foundation models (ESM-2, scGPT, Geneformer, AlphaFold, Evo2, ...) are
not agents — they're specialists that embed a sequence, predict a structure, or
score a perturbation, and stop. There is no "chat with a bio foundation model."
The opportunity isn't porting OpenClaw's chat UI to biology — it's applying its
orchestration pattern (agent + tool layer + ingest pipeline + memory) to a domain
where the tools are bio FMs and the ingest step is a real bioinformatics pipeline,
not a file upload.

The actual bottleneck in computational biology work today isn't model access —
it's the researcher-hours spent hand-writing ingest/QC/analysis scripts (scanpy,
Seurat, custom pipelines) to get raw data into a shape a model can consume, then
hand-interpreting the output. That's the wedge: replace the manual scripting layer
with an agent that plans and executes the workflow.

## Working thesis

> Build an agent (Claude, OpenClaw's session/tool/memory pattern) that sits on top
> of (1) a bioinformatics ingest pipeline normalizing raw lab data into canonical
> formats, and (2) a tool layer wrapping bio foundation models — so a researcher
> can describe an analysis in plain language and get back a QC'd, annotated,
> interpreted result instead of writing and debugging a pipeline by hand.

## Why single-cell transcriptomics as the MVP wedge

Considered three domains, picked single-cell:

| Domain | Ingest | Hosting | Field | Verdict |
|---|---|---|---|---|
| Protein structure (ESM, AlphaFold, RFdiffusion) | Low — FASTA in | Moderate, single GPU | Crowded (Chai Discovery, EvolutionaryScale, Xaira funded) | Fast to demo, hard to differentiate |
| Genomics/sequence (Evo2, DNA LMs) | High — raw FASTQ needs alignment/variant-calling first | Heavy (Evo2 ~40B params) | Thin | Most defensible long-term, too slow for an MVP |
| **Single-cell/transcriptomics (scGPT, Geneformer)** | Low-moderate — standardized `.h5ad`/10x formats | Light, self-hostable | Thin — mostly manual scanpy work today | **Chosen** |

Single-cell wins because the ingest format is already standardized (no bespoke
alignment pipeline needed for the MVP), the models are small enough to self-host
for an internal tool, and the actual daily pain (manual QC/clustering/annotation
scripting) is real and largely unaddressed by agentic tooling.

## Architecture (draft)

1. **Orchestrator** — Claude, running OpenClaw's agentic-loop pattern: sessions,
   subagents for parallel analysis steps, persistent memory across a research
   conversation (so the agent remembers "the dataset we've been discussing" across
   turns).
2. **Bioinformatics ingest pipeline** — normalizes raw single-cell data (10x
   Genomics `.mtx`/`.h5`, eventually raw FASTQ) into canonical AnnData (`.h5ad`),
   runs standard QC (mitochondrial %, doublet detection, low-count filtering), and
   stores versioned canonical datasets the agent can reference by name.
3. **Bio FM tool layer** — wraps scGPT / Geneformer as callable tools: embed
   cells, infer cell type, predict perturbation response. Each tool call is a
   bounded, typed operation the agent invokes — not a chat interface to the model.
4. **Analysis tool layer** — scanpy-backed tools (cluster, differential
   expression, trajectory inference) the agent composes alongside FM calls.
5. **Memory/session layer** — reuse of OpenClaw's session and memory primitives so
   a multi-turn research conversation keeps dataset and finding context without
   the researcher re-stating it.

## Open questions to resolve with Elliot

- [ ] What does Biopunk Labs' team actually spend the most manual bioinformatics
      hours on today? (This should override the single-cell wedge choice if it
      points somewhere else — see README.)
- [ ] Does Biopunk Labs generate single-cell data in-house, or would the first
      real dataset come from a public source (e.g., a GEO/CELLxGENE dataset) for
      the initial internal-tool validation?
- [ ] Hosting/compute: does Biopunk Labs have GPU capacity for self-hosting
      scGPT/Geneformer, or does the MVP need to lean on hosted inference?
- [ ] Any overlap with [Cardiac Base Editor](https://github.com/tjcrowley/cardiac-base-editor)
      or [FDT-BioTech](https://github.com/tjcrowley/fdt-biotech-digital-twins) —
      e.g., could single-cell cardiomyocyte data from either project double as an
      early real-world test dataset?

## Alternative angles considered (not pursued yet)

- Protein structure/design as the wedge — faster demo, but competing directly
  with funded labs (Chai Discovery, EvolutionaryScale, Xaira) with no differentiation
  beyond "another structure predictor with a chat wrapper."
- Genomics/DNA-LM (Evo2) as the wedge — most defensible moat long-term, but the
  ingest pipeline alone (raw FASTQ → aligned, variant-called data) is a project in
  itself; too slow for a first internal-tool demo.

## Next steps

1. Confirm with Elliot: actual daily bioinformatics pain point, to validate or
   override the single-cell wedge.
2. Identify a first real (or public) dataset for the internal-tool pilot.
3. See `.planning/` for the phased build roadmap.
