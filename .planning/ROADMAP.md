# Roadmap: BioClaw

## Overview

BioClaw goes from raw 10x Genomics files to a Claude-based agent that answers plain-language questions about single-cell data, built bottom-up in dependency order. The deterministic, agent-independent pieces (ingest, QC, clustering, differential expression) are built and validated first as plain CPU-only Python, since every other component depends on trustworthy canonical data existing. The agentic loop is then wired to those cheap, deterministic tools before any GPU or bio foundation model complexity is introduced, proving the tool-calling and session/memory contract on the lowest-risk pieces first. Bio-FM-backed cell-type annotation and perturbation prediction — the two strongest differentiators and the two highest-infrastructure-risk items — are layered on last, each shipped with a mandatory statistical baseline so no foundation-model output is ever presented as ground truth on its own. The Virtual Cell Challenge benchmark harness rides on the perturbation tool to provide an external, Arc Institute-credible validation signal. The natural-language Q&A capstone closes the loop: composing every tool built in prior phases into an interpreted, traceable, uncertainty-aware answer — the actual Core Value this project exists to prove.

## Phases

**Phase Numbering:**
- Integer phases (1, 2, 3): Planned milestone work
- Decimal phases (2.1, 2.2): Urgent insertions (marked with INSERTED)

Decimal phases appear between their surrounding integers in numeric order.

- [x] **Phase 1: Ingest + QC Pipeline** - Raw 10x output becomes canonical, versioned, trustworthy `.h5ad` with an immutable raw-counts contract (completed 2026-09-04)
- [x] **Phase 2: Analysis Tool Layer** - Deterministic clustering and differential-expression tools work standalone on canonical data, agent-ready (completed 2026-09-05)
- [x] **Phase 3: Agent Orchestration Wiring** - A Claude-based agent plans, calls, and logs tool invocations against the Phase 1-2 tools with persistent session memory (completed 2026-09-05)
- [ ] **Phase 4: Bio-FM Tool Layer — Cell-Type Annotation** - The agent calls a bio foundation model as a tool for cell-type annotation, always paired with a statistical baseline
- [ ] **Phase 5: Perturbation-Response Tool + VCC Benchmark** - The agent predicts perturbation response as a tool call, independently validated against Arc Institute's public benchmark
- [ ] **Phase 6: Natural-Language Q&A Capstone** - A researcher asks a plain-language question and gets a traceable, uncertainty-aware, interpreted answer

## Phase Details

### Phase 1: Ingest + QC Pipeline
**Goal**: Raw 10x Genomics single-cell output becomes canonical, versioned `.h5ad` data with an immutable raw-counts contract and logged, explicit QC — the trustworthy foundation every later phase depends on.
**Depends on**: Nothing (first phase)
**Requirements**: INGEST-01, INGEST-02, INGEST-03, QC-01, QC-02
**Success Criteria** (what must be TRUE):
  1. A researcher can point the ingest pipeline at a 10x `.mtx`/`.h5` directory and get back a valid canonical `.h5ad` file.
  2. The resulting `.h5ad` has an immutable `adata.layers['counts']` set at load time, before any normalization, that stays unchanged through later pipeline steps.
  3. Standard QC metrics (mitochondrial %, doublet score, low-count/gene filtering) are computed for any ingested dataset.
  4. The QC thresholds used for a given run are explicit and logged, so a researcher can see exactly what was filtered and why.
  5. A named, versioned dataset persists in a store that later phases (agent, analysis) can reference by name.
**Plans**: 5/5 plans executed

Plans:
- [x] 01-01-PLAN.md — Test infrastructure: pytest env + synthetic 10x fixtures (Wave 0)
- [x] 01-02-PLAN.md — 10x loader + raw-counts immutability contract (INGEST-01, INGEST-02)
- [x] 01-03-PLAN.md — QC metrics, config, and audit logging (QC-01, QC-02)
- [x] 01-04-PLAN.md — Versioned dataset store (INGEST-03)
- [x] 01-05-PLAN.md — ingest_10x() pipeline entrypoint + end-to-end verification

### Phase 2: Analysis Tool Layer
**Goal**: Standard scanpy-backed analyses (clustering, differential expression) work as deterministic, typed, agent-callable tools on canonical Phase 1 data — validated standalone, before any agent or GPU dependency exists.
**Depends on**: Phase 1
**Requirements**: ANLYS-01, ANLYS-02, ANLYS-03, ANLYS-04
**Success Criteria** (what must be TRUE):
  1. Given a QC'd `.h5ad`, normalization, highly-variable-gene selection, and PCA run as a deterministic prerequisite pipeline step.
  2. Cells cluster via Leiden (`flavor="igraph"`) and a 2D UMAP embedding is produced for any clustered dataset.
  3. Differential expression (Wilcoxon rank-sum) between two clusters or conditions returns a ranked gene result.
  4. Each analysis tool call returns a bounded, structured summary — not a raw matrix dump — sized for later agent context.
**Plans**: 5/5 plans executed

Plans:
- [x] 02-01-PLAN.md — Wave 0: igraph dependency, structured_adata fixture, bounded-summary dataclass contracts
- [x] 02-02-PLAN.md — preprocess() normalize/HVG/PCA (ANLYS-01)
- [x] 02-03-PLAN.md — cluster() Leiden (igraph) + UMAP (ANLYS-02)
- [x] 02-04-PLAN.md — differential_expression() Wilcoxon rank-sum DE (ANLYS-03)
- [x] 02-05-PLAN.md — analyze() pipeline integration: store load/save + counts-integrity checks (ANLYS-01..04)

### Phase 3: Agent Orchestration Wiring
**Goal**: A Claude-based agent, running an OpenClaw-style agentic loop via Claude Agent SDK + MCP, plans and calls the Phase 1-2 tools with verifiable execution logging and persistent multi-turn memory — proving the tool-calling contract on cheap, deterministic tools before GPU/bio-FM complexity is introduced.
**Depends on**: Phase 2
**Requirements**: AGENT-01, AGENT-02, AGENT-03
**Success Criteria** (what must be TRUE):
  1. A researcher can issue a request that drives a plan → tool call → observe → continue loop, invoking ingest/QC/analysis tools through the Claude Agent SDK + MCP.
  2. Every tool call is logged with request/response detail sufficient to verify it was actually invoked, not simulated by the LLM.
  3. The agent recalls dataset references and prior findings across multiple turns within the same session.
**Plans**: 5/5 plans complete

Plans:
- [x] 03-01-PLAN.md — Wave 0: uv add claude-agent-sdk, live_llm pytest marker, agent/ package skeleton
- [x] 03-02-PLAN.md — agent/tools.py + agent/server.py: ingest_10x_tool/analyze_dataset_tool + in-process MCP server (AGENT-01)
- [x] 03-03-PLAN.md — agent/logging.py: PostToolUse JSON-lines execution log (AGENT-02)
- [x] 03-04-PLAN.md — agent/memory.py: SQLite-backed SessionMemory dataset-reference store (AGENT-03)
- [x] 03-05-PLAN.md — agent/session.py: ClaudeSDKClient wiring + live_llm integration smoke test (AGENT-01/02/03)

### Phase 4: Bio-FM Tool Layer — Cell-Type Annotation
**Goal**: The agent can call a bio foundation model (scGPT or Geneformer) as a tool to annotate cell type, with every FM result accompanied by a statistical baseline and full confidence/reference metadata — never presented as ground truth alone.
**Depends on**: Phase 3
**Requirements**: ANNOT-01, ANNOT-02, ANNOT-03
**Success Criteria** (what must be TRUE):
  1. The agent can invoke a bio-FM-backed cell-type annotation tool on normalized expression and receive a cell-type call.
  2. Every FM-backed annotation call automatically returns a marker-gene/`decoupler`-based statistical baseline result alongside it, for comparison.
  3. Annotation output includes reference dataset, confidence score, and ontology metadata — not a bare label string.
**Plans**: 1/5 plans executed

Plans:
- [x] 04-01-PLAN.md — Wave 0: annotation/ package skeleton + AnnotationCall/AnnotationSummary contracts, decoupler install, bio_fm_smoke marker
- [ ] 04-02-PLAN.md — decoupler ORA marker-gene statistical baseline (ANNOT-02)
- [ ] 04-03-PLAN.md — Isolated scGPT environment (bio_fm_worker/) + subprocess fm_client, mocked-FM unit tests (ANNOT-01)
- [ ] 04-04-PLAN.md — annotate() pipeline composition + annotate_cell_type_tool agent wiring (ANNOT-01, ANNOT-03)
- [ ] 04-05-PLAN.md — cellxgene-census reference index + real scGPT checkpoint acquisition + bio_fm_smoke phase-gate verification

### Phase 5: Perturbation-Response Tool + VCC Benchmark Harness
**Goal**: The agent predicts perturbation response as a typed tool call, benchmarked against a naive baseline by default, and independently validated against the Virtual Cell Challenge's public dataset and official metrics as an external, credible evidence source for the wedge.
**Depends on**: Phase 4
**Requirements**: PERT-01, PERT-02, VCC-01, VCC-02, VCC-03
**Success Criteria** (what must be TRUE):
  1. Given control profiles and a target gene, the perturbation tool returns predicted post-knockdown expression.
  2. Every perturbation prediction is automatically compared against a naive perturbation-mean baseline.
  3. The VCC public dataset ingests through the same Phase 1 pipeline, with no bespoke ingest path required.
  4. An eval harness calls the perturbation tool directly, bypassing the agent loop, and computes PDS, DES, and MAE exactly as Arc Institute defines them.
  5. Benchmark results report all three official metrics plus the naive-baseline comparison — never a single cherry-picked metric in isolation.
**Plans**: TBD

Plans:
- [ ] 05-01: TBD

### Phase 6: Natural-Language Q&A Capstone
**Goal**: A Biopunk Labs researcher asks a plain-language question about an ingested dataset and receives an interpreted answer that composes the tools from every prior phase automatically, with every claim traceable to a logged tool-call result and every quantitative claim carrying surfaced confidence/uncertainty — proving the project's Core Value end to end.
**Depends on**: Phase 5
**Requirements**: QA-01, QA-02, QA-03
**Success Criteria** (what must be TRUE):
  1. A researcher can ask a natural-language question about an ingested dataset and receive an interpreted answer, not raw tool output, that automatically composes one or more prior tools.
  2. Every claim in a natural-language answer links back to the specific logged tool-call result(s) it summarizes.
  3. Quantitative claims in an answer are accompanied by surfaced confidence/uncertainty, never stated as bare fact.
**Plans**: TBD

Plans:
- [ ] 06-01: TBD

## Progress

**Execution Order:**
Phases execute in numeric order: 1 → 2 → 3 → 4 → 5 → 6

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. Ingest + QC Pipeline | 5/5 | Complete   | 2026-09-04 |
| 2. Analysis Tool Layer | 5/5 | Complete   | 2026-09-05 |
| 3. Agent Orchestration Wiring | 5/5 | Complete    | 2026-09-05 |
| 4. Bio-FM Tool Layer — Cell-Type Annotation | 1/5 | In Progress|  |
| 5. Perturbation-Response Tool + VCC Benchmark | 0/TBD | Not started | - |
| 6. Natural-Language Q&A Capstone | 0/TBD | Not started | - |
