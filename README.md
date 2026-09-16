# BioClaw

**An agentic harness for biological foundation models — OpenClaw's orchestration pattern, retargeted at computational biology.**

Built in collaboration with [Biopunk Labs](https://biopunklab.com/).

## The idea

Biological foundation models (ESM-2, scGPT, Geneformer, AlphaFold, Evo2, etc.) don't reason and don't call tools — they embed sequences, predict structure, or score perturbations. They're specialists, not agents. Meanwhile, the actual bottleneck in a computational biology workflow isn't model quality — it's the hours a researcher spends hand-writing ingest/QC/analysis scripts (scanpy, Seurat, custom pipelines) just to get data into a shape a model can use, then hand-interpreting the output.

BioClaw is an LLM-orchestrated agent (Claude, same agentic-loop pattern as OpenClaw: sessions, subagents, tool routing, persistent memory) that sits on top of a **bioinformatics ingest pipeline** and a set of **bio foundation models wrapped as callable tools**. A researcher describes what they want in plain language; the agent plans the workflow, ingests and QCs the data, calls the right model(s), and reports back — instead of the researcher writing and debugging the pipeline by hand.

## MVP wedge: single-cell transcriptomics

Chosen over protein-structure (crowded — Chai Discovery, EvolutionaryScale, Xaira are well-funded) and genomics/DNA-LM (ingest too heavy for an MVP — raw FASTQ needs alignment/variant-calling before a model ever sees it).

Single-cell wins on:
- **Standardized ingest** — 10x Genomics / AnnData (`.h5ad`) formats, not raw sequencer output
- **Self-hostable models** — scGPT / Geneformer run on modest hardware, no frontier-scale compute needed
- **Real, underserved pain** — cell-type annotation, QC, clustering, and perturbation-response questions are still mostly manual scanpy work; almost no agentic tooling exists here yet

Example target interaction: researcher uploads raw 10x output → agent QCs (mito %, doublet detection), clusters, calls scGPT for cell-type annotation, and answers "which populations show the strongest response to compound X" in conversation — no scanpy script required.

## Status

v1.1 — web UI complete (login, chat, live tool-activity streaming, citation resolution, session sidebar, dataset upload). See [CONCEPT.md](CONCEPT.md) for architecture detail and `.planning/` for the phased build history.

## Web UI (v1.1)

A self-contained local web front end wraps the agent in a chat interface. See
[webapp/README.md](webapp/README.md) for full setup and the exact run command.

Quick start:
```bash
uv sync --extra web
BIOCLAW_WEB_PASSWORD=<your-password> ANTHROPIC_API_KEY=<your-key> \
  uv run --extra web uvicorn webapp.backend.main:app --port 8000
```
Then open http://localhost:8000/app in a browser.

## Target audience

Single-cell biology researchers who spend hours writing and debugging scanpy/Seurat pipelines. The goal is to replace that loop with a plain-language conversation: describe the analysis, get back a QC'd, annotated, interpreted result.
