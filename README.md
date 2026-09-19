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

v1.2 — **real foundation-model inference is live.** Both models run for real against their own checkpoints, each isolated in its own Python environment behind a subprocess boundary:

- **scGPT** (whole-human checkpoint) for cell-type annotation, with confidence reported as a k-NN vote fraction (k=15) over reference embeddings rather than a top-1 cosine similarity
- **Geneformer** (V1-10M) for perturbation response, running the full four-step pipeline (tokenize → embed → in-silico perturb → stats) and returning a ranked gene list

Also in v1.2: chat history replay, `.h5ad` upload, CSV + scanpy-script export, and `cellxgene-census` dataset fetch.

Remaining for v1.2: Phase 14, a single-service Docker Compose deployment. The image
builds and the stack comes up — final end-to-end verification is still pending.

Earlier — v1.1: web UI complete (login, chat, live tool-activity streaming, citation resolution, session sidebar, dataset upload).

See [CONCEPT.md](CONCEPT.md) for architecture detail and `.planning/` for the phased build history.

## Roadmap

Built bottom-up in dependency order: the deterministic, agent-independent pieces
first (so there is trustworthy data to reason about), then the agentic loop on
cheap tools, then the foundation models — each shipped with a statistical
baseline so no FM output is ever presented as ground truth on its own.

| Milestone | Phases | What it delivers | Status |
|---|---|---|---|
| **v1.0** | 1–6 | Ingest + QC → analysis tools → agent loop → scGPT annotation → perturbation + VCC benchmark → natural-language Q&A capstone | Shipped |
| **v1.1** | 7–10 | Local web UI: password-gated FastAPI backend, WebSocket tool-activity streaming, chat frontend, session sidebar, upload | Shipped |
| **v1.2** | 11–14 | Real data and real inference: history replay, `.h5ad` upload, CSV + scanpy-script export, cellxgene-census fetch, live scGPT + Geneformer, Docker Compose | Phases 11–13 shipped; 14 in progress |
| **v1.3** | 15–16 | Edge appliance: native arm64 + iGPU on a Jetson Orin Nano 8GB, then appliance hardening (headless provisioning, LAN TLS, power-loss tolerance, headless updates) | Roadmap only — not planned, not built |

Phase-by-phase detail, success criteria, and the per-plan build log live in
[`.planning/ROADMAP.md`](.planning/ROADMAP.md).

### Future capabilities (unscheduled)

Not on the roadmap — no phases, no dates. Recorded because the architecture was
shaped with them in mind.

**Protein structure & function.** Passed over for the MVP for a different reason
than genomics below — not that it is hard, but that it is crowded. Chai
Discovery, EvolutionaryScale, and Xaira are well-funded and already there, and
structure prediction is the one corner of bio-FM tooling where the ingest
problem is largely solved: a sequence is a string, and ESM-2 embeddings or an
AlphaFold/Boltz structure call need no alignment pipeline to get started. The
technical lift here is the smallest of the three wedges. The positioning
question is the largest.

So the precondition is not an engineering one. It is having an answer to *why
this agent rather than the incumbents' own tooling* — most plausibly that the
value is in composition rather than prediction: a researcher who wants
"annotate these cells, then pull structures for the top differentially expressed
surface receptors, then tell me which are druggable" is describing a workflow no
single-purpose structure tool spans. That is the same interpretive, multi-tool
loop Phase 6 already proves on single-cell data. It is a real hypothesis, not a
validated one.

Mechanically it would be the cheapest worker to add — a sequence-in/structure-out
subprocess needs no new canonical-data contract, so most of Phase 1's machinery
is simply not required. The statistical-baseline rule still applies: pLDDT and
PAE are the model's own confidence, not an independent check, so a structure
call would need something external — a homology hit, a known-fold comparison —
to satisfy the ANNOT-02 pattern rather than quietly exempting itself from it.

**Genomics / DNA language models.** Deliberately passed over for the MVP (see
[MVP wedge](#mvp-wedge-single-cell-transcriptomics) above): the blocker was never
model availability — Evo2, Nucleotide Transformer, and DNABERT-2 are all
self-hostable — it was that raw FASTQ needs alignment and variant-calling before
a model ever sees a token. That is a second ingest pipeline with its own
reference genomes, its own compute profile, and its own correctness burden,
which is a poor thing to take on before the agentic loop has earned trust.

What would have to be true to revisit it:

- A genomics ingest layer producing a canonical, versioned artifact the way
  Phase 1 does for `.h5ad` — the agent's contract is with canonical data, not
  with file formats, so this is the real work
- A statistical baseline for whatever the DNA-LM claims, matching the
  ANNOT-02 / PERT-02 pattern where every FM call ships with a comparison
- Enough hardware headroom that long-context DNA models are not competing with
  the single-cell stack for the same GPU

Common to both: the tool-routing, session-memory, citation, and
subprocess-isolation layers are model-agnostic and carry over unchanged. The
three-interpreter pattern in the Dockerfile exists precisely because bio FMs
each bring a mutually incompatible dependency set, so either of these would
arrive the same way the existing two did — its own pinned interpreter, its own
venv, reached over a subprocess boundary the main app never imports across.

### Self-extension: BioClaw builds its own tools

The domain wedges above each assume someone hand-writes the pipeline. The
alternative is that a researcher *describes* the pipeline they need — "add a
cardiac subtype panel," "add tumor/normal deconvolution" — and BioClaw
orchestrates a coding model to build it, test it, and open a pull request
against this repo for human review.

Structurally this is a short reach. BioClaw already runs on the Claude Agent
SDK, and a new analysis capability is already just a `@tool`-decorated async
handler in `agent/tools.py` registered in `agent/server.py` — a well-bounded
contract for generated code to target. The tool-call audit log already records
every action in a form a PR description can cite.

**Most of the demand does not need code generation at all.** A cardiac or cancer
pipeline is usually a marker-gene panel, an ontology subset, and a prompt —
domain knowledge, not new algorithms, composed from Phase 1–2 primitives that
already exist. So the honest sequencing is three tiers, cheapest first:

| Tier | What a researcher adds | Risk surface |
|---|---|---|
| **1. Declarative** | Marker panels, tool specs, prompts — as *data* | None new. No code execution, no repo access |
| **2. Ephemeral** | Generated analysis code, run once, never merged | Roughly what scanpy-script export already does |
| **3. Self-extension** | Generated tools, tested, submitted as PRs | Large — a write credential and an agent that writes code |

Tier 1 probably covers the cardiac/cancer case outright, and it is worth
building first regardless, because it is also the thing Tier 3 would generate.

Tier 3 is the interesting one, and it is a real privilege escalation: today the
agent calls read-only analysis tools against local data, and this makes it an
agent that writes code and holds a repository credential. That is a defensible
thing to build — "propose a change for a human to review" is the same bounded
pattern coding agents already use — but only with the boundaries stated up
front, not discovered later:

- **Pull requests only.** Never a push to `main`, never an auto-merge. Human
  review is not a nicety here; it *is* the safety model, and nothing else in
  the design substitutes for it.
- **A credential scoped to a fork or a branch**, never write access to `main`.
- **CI as a hard gate.** The existing test suite has to run on every generated
  PR — the Phase 1 raw-counts immutability contract in particular is exactly
  the invariant a plausible-looking generated tool would quietly break.
- **The statistical-baseline rule still applies.** A generated tool that
  reports results without the ANNOT-02 / PERT-02 style comparison is not a
  valid BioClaw tool, however well it runs.
- **Build and test in a throwaway container**, not on the host serving the app.
- **Provenance on every PR** — originating session ID, the prompt that produced
  it, and a link to the tool-call log entries, so a reviewer can see what was
  asked and what the agent actually did.

One interaction worth flagging now: this **conflicts with the Phase 16
appliance threat model**. A benchtop box that can be carried out of a lab
should not hold a credential that can write to the project repository. On an
appliance, self-extension should default to off, or the credential should live
somewhere the appliance can reach but an attacker holding the hardware cannot.

Unscheduled, like everything else in this section — but unlike the domain
wedges, this one is mostly an access-control and review-workflow design
problem, not a bioinformatics one.

## Docker

CPU-only (always works, no GPU required):
```bash
docker compose up
```

GPU-enabled (adds NVIDIA device passthrough to the same backend service):
```bash
docker compose -f docker-compose.yml -f docker-compose.gpu.yml up
```

Configure `.env` from `.env.example` first (`ANTHROPIC_API_KEY`, `BIOCLAW_WEB_PASSWORD`).
The backend serves both the API and the built frontend at http://localhost:8000.

Both foundation-model checkpoints and the `cellxgene-census` reference index are
baked into the image at build time — there is no first-run download step. See
[docker/README.md](docker/README.md) for what the build automates, why the image
carries three isolated Python interpreters, and the manual fallback if an
upstream artifact fetch fails.

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
