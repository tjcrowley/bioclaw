# Requirements: BioClaw

**Defined:** 2026-09-03
**Core Value:** A Biopunk Labs researcher can ask a plain-language question about a single-cell dataset and get back a QC'd, annotated, interpreted answer without writing a scanpy script by hand.

## v1 Requirements

Requirements for initial internal-tool release. Each maps to a roadmap phase.

### Ingest

- [x] **INGEST-01**: System can ingest standard 10x Genomics single-cell output (`.mtx`, `.h5`) and normalize it to canonical AnnData (`.h5ad`)
- [x] **INGEST-02**: Ingest persists raw counts to an immutable `adata.layers['counts']` at load time, before any normalization step, so downstream tools always have an uncorrupted source of truth
- [x] **INGEST-03**: Canonical datasets are stored in a versioned dataset store the agent can reference by name across a session

### QC

- [x] **QC-01**: System computes standard QC metrics on ingested data (mitochondrial %, doublet score, low-count/gene filtering)
- [x] **QC-02**: QC thresholds are explicit and logged per run, not silently hard-coded, so a researcher can see what was filtered and why

### Analysis

- [x] **ANLYS-01**: System normalizes, selects highly variable genes, and computes PCA as a prerequisite pipeline step
- [x] **ANLYS-02**: System clusters cells (Leiden, `flavor="igraph"`) and computes a 2D embedding (UMAP)
- [x] **ANLYS-03**: System computes differential expression between clusters or conditions (Wilcoxon rank-sum)
- [x] **ANLYS-04**: Each analysis tool call returns a bounded, structured summary (not a raw matrix dump) suitable for agent context

### Bio-FM Annotation

- [ ] **ANNOT-01**: System calls a bio foundation model (scGPT or Geneformer) as a tool to annotate cell type from normalized expression
- [ ] **ANNOT-02**: Every FM-backed annotation call is accompanied by a statistical baseline (marker-gene/`decoupler`-based) result for comparison, so an FM result is never presented as ground truth on its own
- [ ] **ANNOT-03**: Annotation output includes reference/confidence/ontology metadata, not a bare label string

### Perturbation Prediction

- [ ] **PERT-01**: System calls a perturbation-response model (GEARS/cell-gears, or a hybrid statistical+neural approach) as a tool, predicting post-knockdown expression from control profiles and a target gene
- [ ] **PERT-02**: Perturbation tool output is compared against a naive perturbation-mean baseline by default

### Agent Orchestration

- [x] **AGENT-01**: An OpenClaw-style agentic loop (plan → tool call → observe → continue) orchestrates the ingest/QC/analysis/FM tools via Claude Agent SDK + MCP
- [x] **AGENT-02**: Every tool call is logged with request/response detail sufficient to verify it was actually invoked (not simulated by the LLM)
- [x] **AGENT-03**: Session/memory persists dataset references and prior findings across a multi-turn research conversation

### Natural-Language Q&A (Capstone)

- [ ] **QA-01**: A researcher can ask a natural-language question about an ingested dataset and receive an interpreted answer that composes one or more of the above tools automatically
- [ ] **QA-02**: Every natural-language answer links back to the specific logged tool-call result(s) it summarizes — no answer ships as prose only
- [ ] **QA-03**: Quantitative claims in an answer are accompanied by surfaced confidence/uncertainty, not stated as bare fact

### Virtual Cell Challenge Benchmark

- [ ] **VCC-01**: System can ingest the Virtual Cell Challenge's public dataset (10x Flex chemistry, control + perturbed profiles) through the same ingest pipeline
- [ ] **VCC-02**: An eval harness calls the perturbation-prediction tool directly (bypassing the agent loop) against the VCC public dataset and computes PDS, DES, and MAE exactly as Arc Institute defines them
- [ ] **VCC-03**: Benchmark results report performance against the naive perturbation-mean baseline, not a single cherry-picked metric in isolation

## v2 Requirements

Deferred to future release. Tracked but not in current roadmap.

### Reliability Hardening

- **RELIA-01**: Lightweight self-check/evaluator step on tool outputs (empty-result detection, sanity-range checks)
- **RELIA-02**: Tool-call provenance/audit trail surfaced directly to the researcher (not just in logs)
- **RELIA-03**: Support for a second annotation/embedding model for cross-validation when confidence is ambiguous

### Data Scale

- **DATA-01**: Batch integration/correction (Harmony or scVI) across multiple samples — as an explicit, logged, conditional pipeline step, never unconditional (see PITFALLS.md batch-correction risk)

## Out of Scope

Explicitly excluded. Documented to prevent scope creep.

| Feature | Reason |
|---------|--------|
| Protein-structure models (ESM, AlphaFold, RFdiffusion) | Deferred MVP wedge — crowded, funded competitive field (Chai Discovery, EvolutionaryScale, Xaira) |
| Raw-sequence genomics models (Evo2, DNA LMs) | Ingest (FASTQ alignment/variant-calling) too heavy for MVP |
| Raw FASTQ ingest / alignment pipeline | Doesn't address the actual researcher pain point, which starts post-alignment at `.mtx`/`.h5` |
| Formal Virtual Cell Challenge competition entry/leaderboard submission | Benchmark/validation target only, not a leaderboard chase — winning requires narrow metric-tuning, a different project from the agent harness |
| Full no-code GUI/dashboard | Competing on GUI polish abandons the actual differentiator (conversational agent); multi-year investment matching funded commercial tools |
| Training bio foundation models from scratch | Multi-year research program beyond an internal-tool MVP budget; wrap existing open-weight models instead |
| Additional modalities (spatial, ATAC, CITE-seq, multi-omics) | Each has its own QC/format/FM landscape; dilutes the scRNA-seq wedge before it's proven |
| Autonomous open-ended hypothesis generation (CellVoyager-style) | Conflicts with the scoped, question-driven MVP interaction model; expensive and hard to validate for trust |
| Multi-agent planner/executor/evaluator architecture | Added orchestration complexity only justified once single-loop reliability is proven insufficient |
| Multi-tenant / external customer access, billing, auth | Internal tool only until validated with Biopunk Labs |
| Chat interface to the bio foundation models directly | FMs are typed, bounded tool calls the orchestrator invokes and interprets — not conversational endpoints |

## Traceability

Populated during roadmap creation (2026-09-03).

| Requirement | Phase | Status |
|-------------|-------|--------|
| INGEST-01 | Phase 1 | Complete |
| INGEST-02 | Phase 1 | Complete |
| INGEST-03 | Phase 1 | Complete |
| QC-01 | Phase 1 | Complete |
| QC-02 | Phase 1 | Complete |
| ANLYS-01 | Phase 2 | Complete |
| ANLYS-02 | Phase 2 | Complete |
| ANLYS-03 | Phase 2 | Complete |
| ANLYS-04 | Phase 2 | Complete |
| ANNOT-01 | Phase 4 | Pending |
| ANNOT-02 | Phase 4 | Pending |
| ANNOT-03 | Phase 4 | Pending |
| PERT-01 | Phase 5 | Pending |
| PERT-02 | Phase 5 | Pending |
| AGENT-01 | Phase 3 | Complete |
| AGENT-02 | Phase 3 | Complete |
| AGENT-03 | Phase 3 | Complete |
| QA-01 | Phase 6 | Pending |
| QA-02 | Phase 6 | Pending |
| QA-03 | Phase 6 | Pending |
| VCC-01 | Phase 5 | Pending |
| VCC-02 | Phase 5 | Pending |
| VCC-03 | Phase 5 | Pending |

**Coverage:**
- v1 requirements: 23 total
- Mapped to phases: 23 (100%) ✓
- Unmapped: 0 ✓

---
*Requirements defined: 2026-09-03*
*Last updated: 2026-09-03 after roadmap creation*
