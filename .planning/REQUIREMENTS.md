# Requirements: BioClaw

**Core Value:** A Biopunk Labs researcher can ask a plain-language question about a single-cell dataset and get back a QC'd, annotated, interpreted answer without writing a scanpy script by hand.

## Milestone v1.1 — Web UI (current)

**Defined:** 2026-09-11
**Goal:** Give the v1.0 Q&A agent a self-contained web front end, styled after OpenClaw's own UX, so a researcher can use bioclaw without a terminal or a pytest invocation.

### Backend API

- [x] **API-01**: FastAPI backend exposes an endpoint that accepts a natural-language question and returns the agent's answer, wrapping `qa/session.py::ask_question()`
- [x] **API-02**: Backend streams tool-call activity to the client as it happens during agent execution (tool name, args summary, status) over a WebSocket, not just the final answer
- [x] **API-03**: Backend exposes endpoints to list existing sessions and to resume a session by ID, backed by the existing `SessionMemory` (SQLite) layer
- [x] **API-04**: Backend exposes an upload endpoint that accepts a `.mtx`/`.h5` dataset and invokes `ingest_10x` as part of the conversation flow
- [x] **API-05**: All backend routes are gated behind a single shared password (one shared secret, not per-user accounts) — unauthenticated requests are rejected

### Frontend Chat UI

- [ ] **UI-01**: Chat-style message thread showing question/answer turns for the active session
- [x] **UI-02**: Live tool-call activity view rendered inline as calls happen (ingest/analyze/annotate/predict_perturbation), sourced from the API-02 stream
- [ ] **UI-03**: Citations in agent answers (`[ref:TOOL_NAME:SHA256_PREFIX]`) render as inspectable elements resolving to the underlying JSONL audit log entry, not raw bracket tags
- [ ] **UI-04**: Session sidebar lists past sessions (from API-03) and lets the researcher resume any of them
- [ ] **UI-05**: Dataset upload control in the composer area (drag-and-drop or file picker) that calls API-04 and surfaces ingest progress/result in the thread
- [x] **UI-06**: Login screen gated by the shared password; no chat UI is reachable before authenticating
- [x] **UI-07**: Visual style modeled on OpenClaw's own web UI (sidebar + main panel layout, dark theme, similar information density) — replicated visually, not by importing OpenClaw code

### Packaging

- [ ] **PKG-01**: Webapp (backend + frontend) ships self-contained inside the `bioclaw` repo in its own directory, with its own dependencies — no runtime or code dependency on the OpenClaw codebase
- [ ] **PKG-02**: Webapp runs locally via a single documented command, sufficient to fully verify the feature before any deployment decision

### v2 (deferred beyond v1.1)

- **DEPLOY-01**: Deploy to a Dead Dog Studios DigitalOcean droplet (Caddy TLS, systemd service) — only on Darren's explicit go-ahead
- **DEPLOY-02**: Public/production hardening (rate limiting, HTTPS enforcement, log rotation) once a real deploy target exists
- **AUTH-01**: Per-user accounts / RBAC if bioclaw ever grows beyond a single shared internal tool

### Out of Scope (v1.1)

| Feature | Reason |
|---------|--------|
| Multi-tenant accounts, billing, OAuth, RBAC | Internal tool until validated with Biopunk Labs — see PROJECT.md |
| Public/production DigitalOcean deployment | This milestone is local build + verification only; deploy requires explicit go-ahead |
| Chat interface directly to bio foundation models | These remain tool calls behind the agent, not conversational endpoints |
| Importing/depending on the actual OpenClaw codebase | Replicate the UX pattern only; webapp must stay self-contained in `bioclaw` |

### Traceability (v1.1)

| Requirement | Phase | Status |
|-------------|-------|--------|
| API-01 | Phase 7 | Complete |
| API-02 | Phase 7 | Complete |
| API-03 | Phase 8 | Complete |
| API-04 | Phase 8 | Complete |
| API-05 | Phase 7 | Complete |
| UI-01 | Phase 9 | Pending |
| UI-02 | Phase 9 | Complete |
| UI-03 | Phase 9 | Pending |
| UI-04 | Phase 9 | Pending |
| UI-05 | Phase 9 | Pending |
| UI-06 | Phase 9 | Complete |
| UI-07 | Phase 9 | Complete |
| PKG-01 | Phase 10 | Pending |
| PKG-02 | Phase 10 | Pending |

**Coverage:** 14 total, 14 mapped (100%) ✓, 0 unmapped ✓

---

## Milestone v1.0 — Agent Core (shipped 2026-09-11)

**Defined:** 2026-09-03

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
- [x] **ANNOT-02**: Every FM-backed annotation call is accompanied by a statistical baseline (marker-gene/`decoupler`-based) result for comparison, so an FM result is never presented as ground truth on its own
- [ ] **ANNOT-03**: Annotation output includes reference/confidence/ontology metadata, not a bare label string

### Perturbation Prediction

- [x] **PERT-01**: System calls a perturbation-response model (GEARS/cell-gears, or a hybrid statistical+neural approach) as a tool, predicting post-knockdown expression from control profiles and a target gene
- [x] **PERT-02**: Perturbation tool output is compared against a naive perturbation-mean baseline by default

### Agent Orchestration

- [x] **AGENT-01**: An OpenClaw-style agentic loop (plan → tool call → observe → continue) orchestrates the ingest/QC/analysis/FM tools via Claude Agent SDK + MCP
- [x] **AGENT-02**: Every tool call is logged with request/response detail sufficient to verify it was actually invoked (not simulated by the LLM)
- [x] **AGENT-03**: Session/memory persists dataset references and prior findings across a multi-turn research conversation

### Natural-Language Q&A (Capstone)

- [x] **QA-01**: A researcher can ask a natural-language question about an ingested dataset and receive an interpreted answer that composes one or more of the above tools automatically
- [x] **QA-02**: Every natural-language answer links back to the specific logged tool-call result(s) it summarizes — no answer ships as prose only
- [x] **QA-03**: Quantitative claims in an answer are accompanied by surfaced confidence/uncertainty, not stated as bare fact

### Virtual Cell Challenge Benchmark

- [x] **VCC-01**: System can ingest the Virtual Cell Challenge's public dataset (10x Flex chemistry, control + perturbed profiles) through the same ingest pipeline
- [x] **VCC-02**: An eval harness calls the perturbation-prediction tool directly (bypassing the agent loop) against the VCC public dataset and computes PDS, DES, and MAE exactly as Arc Institute defines them
- [x] **VCC-03**: Benchmark results report performance against the naive perturbation-mean baseline, not a single cherry-picked metric in isolation

### v2 Requirements (still deferred)

#### Reliability Hardening

- **RELIA-01**: Lightweight self-check/evaluator step on tool outputs (empty-result detection, sanity-range checks)
- **RELIA-02**: Tool-call provenance/audit trail surfaced directly to the researcher (not just in logs)
- **RELIA-03**: Support for a second annotation/embedding model for cross-validation when confidence is ambiguous

#### Data Scale

- **DATA-01**: Batch integration/correction (Harmony or scVI) across multiple samples — as an explicit, logged, conditional pipeline step, never unconditional (see PITFALLS.md batch-correction risk)

### Out of Scope (v1.0)

| Feature | Reason |
|---------|--------|
| Protein-structure models (ESM, AlphaFold, RFdiffusion) | Deferred MVP wedge — crowded, funded competitive field (Chai Discovery, EvolutionaryScale, Xaira) |
| Raw-sequence genomics models (Evo2, DNA LMs) | Ingest (FASTQ alignment/variant-calling) too heavy for MVP |
| Raw FASTQ ingest / alignment pipeline | Doesn't address the actual researcher pain point, which starts post-alignment at `.mtx`/`.h5` |
| Formal Virtual Cell Challenge competition entry/leaderboard submission | Benchmark/validation target only, not a leaderboard chase — winning requires narrow metric-tuning, a different project from the agent harness |
| Full no-code GUI/dashboard | Superseded — v1.1 adds a scoped chat webapp, not a no-code dashboard |
| Training bio foundation models from scratch | Multi-year research program beyond an internal-tool MVP budget; wrap existing open-weight models instead |
| Additional modalities (spatial, ATAC, CITE-seq, multi-omics) | Each has its own QC/format/FM landscape; dilutes the scRNA-seq wedge before it's proven |
| Autonomous open-ended hypothesis generation (CellVoyager-style) | Conflicts with the scoped, question-driven MVP interaction model; expensive and hard to validate for trust |
| Multi-agent planner/executor/evaluator architecture | Added orchestration complexity only justified once single-loop reliability is proven insufficient |
| Multi-tenant / external customer access, billing, auth | Internal tool only until validated with Biopunk Labs |
| Chat interface to the bio foundation models directly | FMs are typed, bounded tool calls the orchestrator invokes and interprets — not conversational endpoints |

### Traceability (v1.0 — final)

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
| ANNOT-02 | Phase 4 | Complete |
| ANNOT-03 | Phase 4 | Pending |
| PERT-01 | Phase 5 | Complete |
| PERT-02 | Phase 5 | Complete |
| AGENT-01 | Phase 3 | Complete |
| AGENT-02 | Phase 3 | Complete |
| AGENT-03 | Phase 3 | Complete |
| QA-01 | Phase 6 | Complete |
| QA-02 | Phase 6 | Complete |
| QA-03 | Phase 6 | Complete |
| VCC-01 | Phase 5 | Complete |
| VCC-02 | Phase 5 | Complete |
| VCC-03 | Phase 5 | Complete |

**Coverage:** 23 total, 23 mapped (100%) ✓, 0 unmapped ✓

---
*Requirements defined: 2026-09-03 (v1.0), 2026-09-11 (v1.1)*
*Last updated: 2026-09-11 after creating v1.1 Web UI roadmap (Phases 7-10)*
