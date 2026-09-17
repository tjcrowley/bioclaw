# Roadmap: BioClaw

## Overview

BioClaw goes from raw 10x Genomics files to a Claude-based agent that answers plain-language questions about single-cell data, built bottom-up in dependency order. The deterministic, agent-independent pieces (ingest, QC, clustering, differential expression) are built and validated first as plain CPU-only Python, since every other component depends on trustworthy canonical data existing. The agentic loop is then wired to those cheap, deterministic tools before any GPU or bio foundation model complexity is introduced, proving the tool-calling and session/memory contract on the lowest-risk pieces first. Bio-FM-backed cell-type annotation and perturbation prediction — the two strongest differentiators and the two highest-infrastructure-risk items — are layered on last, each shipped with a mandatory statistical baseline so no foundation-model output is ever presented as ground truth on its own. The Virtual Cell Challenge benchmark harness rides on the perturbation tool to provide an external, Arc Institute-credible validation signal. The natural-language Q&A capstone closes the loop: composing every tool built in prior phases into an interpreted, traceable, uncertainty-aware answer — the actual Core Value this project exists to prove.

**Milestone v1.1 (Phases 7-10)** takes the shipped v1.0 agent core and wraps it in a self-contained local web front end, styled after OpenClaw's own UX. The backend is built before the frontend (API-first): first the authenticated HTTP/WebSocket foundation that wraps `ask_question()` and streams tool-call activity, then the session-history and dataset-upload endpoints that depend on that foundation. Only once the full API surface exists is the frontend built against it — chat thread, live activity view, citation rendering, session sidebar, upload control, login screen, and OpenClaw-styled visuals — followed by a final packaging and local-verification pass. Deployment to any production/public environment is explicitly out of scope for this milestone; every phase's success criteria are verifiable on a local machine only.

**Milestone v1.2 (Phases 11-14)** replaces synthetic demo data with real public single-cell datasets, wires real bio foundation model inference (replacing stubs), surfaces session conversation history in the chat UI, adds result export (CSV and scanpy script), and ships a Docker compose that lets any researcher run the full stack with one command. Phases are sequenced by dependency: quick wins that are independent of FM and network come first (Phase 11), agent data-access capability second (Phase 12), FM inference in dependency order third (Phase 13), and Docker deployment last once all features are stable (Phase 14).

## Phases

**Phase Numbering:**
- Integer phases (1, 2, 3): Planned milestone work
- Decimal phases (2.1, 2.2): Urgent insertions (marked with INSERTED)

Decimal phases appear between their surrounding integers in numeric order.

- [x] **Phase 1: Ingest + QC Pipeline** - Raw 10x output becomes canonical, versioned, trustworthy `.h5ad` with an immutable raw-counts contract (completed 2026-09-04)
- [x] **Phase 2: Analysis Tool Layer** - Deterministic clustering and differential-expression tools work standalone on canonical data, agent-ready (completed 2026-09-05)
- [x] **Phase 3: Agent Orchestration Wiring** - A Claude-based agent plans, calls, and logs tool invocations against the Phase 1-2 tools with persistent session memory (completed 2026-09-05)
- [x] **Phase 4: Bio-FM Tool Layer — Cell-Type Annotation** - The agent calls a bio foundation model as a tool for cell-type annotation, always paired with a statistical baseline (completed 2026-09-08)
- [x] **Phase 5: Perturbation-Response Tool + VCC Benchmark** - The agent predicts perturbation response as a tool call, independently validated against Arc Institute's public benchmark (completed 2026-09-10)
- [x] **Phase 6: Natural-Language Q&A Capstone** - A researcher asks a plain-language question and gets a traceable, uncertainty-aware, interpreted answer (completed 2026-09-11)
- [x] **Phase 7: Backend API + Streaming Foundation** - A password-gated FastAPI backend wraps `ask_question()` over HTTP and streams live tool-call activity over WebSocket (completed 2026-09-11)
- [x] **Phase 8: Session & Dataset Endpoints** - Backend endpoints expose session list/resume and dataset upload, built on the authenticated Phase 7 foundation (completed 2026-09-12)
- [x] **Phase 9: Frontend Chat UI** - An OpenClaw-styled chat frontend delivers login, message thread, live tool activity, citation rendering, session sidebar, and dataset upload (completed 2026-09-14)
- [x] **Phase 10: Packaging & Local Verification** - The webapp ships self-contained, runs via one documented command, and is manually verified end-to-end locally (completed 2026-09-15)
- [x] **Phase 11: Quick Wins — History, h5ad Upload, CSV Export** - Session history replays in the UI, .h5ad files upload directly, and CSV export works — all independent of FM and network (completed 2026-09-17)
- [x] **Phase 12: Agent Data Access + Script Export** - The agent fetches real public datasets from cellxgene-census, and researchers can export a reproducible scanpy script from any session (completed 2026-09-17)
- [ ] **Phase 13: Real FM Inference — scGPT then Geneformer** - Real scGPT inference replaces the subprocess stub, then Geneformer adds a second perturbation model using the validated subprocess pattern
- [ ] **Phase 14: Docker Compose Deployment** - The full stack starts with a single `docker compose up` from a clean checkout, hard-coded to single-worker to preserve the in-memory queue registry

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
**Plans**: 5/5 plans executed

Plans:
- [x] 04-01-PLAN.md — Wave 0: annotation/ package skeleton + AnnotationCall/AnnotationSummary contracts, decoupler install, bio_fm_smoke marker
- [x] 04-02-PLAN.md — decoupler ORA marker-gene statistical baseline (ANNOT-02)
- [x] 04-03-PLAN.md — Isolated scGPT environment (bio_fm_worker/) + subprocess fm_client, mocked-FM unit tests (ANNOT-01)
- [x] 04-04-PLAN.md — annotate() pipeline composition + annotate_cell_type_tool agent wiring (ANNOT-01, ANNOT-03)
- [x] 04-05-PLAN.md — cellxgene-census reference index + real scGPT checkpoint acquisition + bio_fm_smoke phase-gate verification

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
**Plans**: 6 plans

Plans:
- [ ] 05-01-PLAN.md — Wave 0: cell-eval dependency, vcc_data marker, perturbation/+benchmark/ skeletons + PerturbationCall/PerturbationSummary contracts, perturbation_adata fixture, .h5ad ingest branch (VCC-01)
- [ ] 05-02-PLAN.md — LinearAdditivePerturbationModel fit/predict + fit_from_adata (PERT-01 core)
- [ ] 05-03-PLAN.md — naive_baseline_predict (cell-eval baseline) + pipeline.predict() composition + predict_perturbation_tool agent wiring (PERT-02, PERT-01)
- [ ] 05-04-PLAN.md — compute_vcc_metrics/run_vcc_eval: cell-eval MetricsEvaluator harness, direct-call bypassing agent loop (VCC-02)
- [ ] 05-05-PLAN.md — build_benchmark_report/run_full_benchmark: baseline-enforced VCC report generator (VCC-03)
- [ ] 05-06-PLAN.md — Phase gate: real VCC dataset download + vcc_data smoke test (blocking human-verify checkpoint)

### Phase 6: Natural-Language Q&A Capstone
**Goal**: A Biopunk Labs researcher asks a plain-language question about an ingested dataset and receives an interpreted answer that composes the tools from every prior phase automatically, with every claim traceable to a logged tool-call result and every quantitative claim carrying surfaced confidence/uncertainty — proving the project's Core Value end to end.
**Depends on**: Phase 5
**Requirements**: QA-01, QA-02, QA-03
**Success Criteria** (what must be TRUE):
  1. A researcher can ask a natural-language question about an ingested dataset and receive an interpreted answer, not raw tool output, that automatically composes one or more prior tools.
  2. Every claim in a natural-language answer links back to the specific logged tool-call result(s) it summarizes.
  3. Quantitative claims in an answer are accompanied by surfaced confidence/uncertainty, never stated as bare fact.
**Plans**: 3 plans

Plans:
- [x] 06-01-PLAN.md — Wave 0: agent/session.py system_prompt kwarg, qa/ skeleton (citations.py + session.py stub), test scaffolds
- [x] 06-02-PLAN.md — ask_question() + QA_SYSTEM_PROMPT implementation
- [x] 06-03-PLAN.md — live_llm integration test (QA-01/02/03) + human-verify checkpoint

### Phase 7: Backend API + Streaming Foundation
**Goal**: A password-gated FastAPI backend wraps the existing `qa/session.py::ask_question()` agent entrypoint as an HTTP endpoint and streams live tool-call activity over WebSocket during execution — the authenticated API surface every later v1.1 phase builds on.
**Depends on**: Phase 6
**Requirements**: API-01, API-02, API-05
**Success Criteria** (what must be TRUE):
  1. A client can POST a natural-language question to a FastAPI endpoint and receive back the agent's answer, sourced from `ask_question()`.
  2. A client connected over WebSocket during that same request receives tool-call activity events (tool name, args summary, status) as they happen, not only the final answer.
  3. Any request to any backend route without the correct shared-password credential is rejected (unauthenticated).
  4. A request presenting the correct shared password succeeds against the same routes.
  5. The backend runs and is verifiable entirely on localhost — no deployment to any external or production environment.
**Plans**: 3 plans complete

Plans:
- [x] 07-01-PLAN.md — Wave 1: additive extra_hooks on build_options/run_session/ask_question + webapp/backend schemas.py/auth.py contracts + fastapi[standard] install (API-05, API-02)
- [x] 07-02-PLAN.md — Wave 2: streaming.py queue registry + deps.py + main.py (POST /api/ask, WS /ws/{stream_id}) with fast-tier tests (API-01, API-02, API-05)
- [x] 07-03-PLAN.md — Wave 3: live_llm end-to-end integration test + human-verify checkpoint (API-01, API-02) (completed 2026-09-12)

### Phase 8: Session & Dataset Endpoints
**Goal**: The password-gated backend exposes session history (list/resume, backed by `SessionMemory`) and dataset upload (invoking `ingest_10x`), completing the API surface the frontend will consume.
**Depends on**: Phase 7
**Requirements**: API-03, API-04
**Success Criteria** (what must be TRUE):
  1. A client can call an endpoint to list existing sessions and see session IDs/metadata sourced from `SessionMemory`.
  2. A client can call an endpoint to resume a specific prior session by ID and continue that session's conversation with its prior context intact.
  3. A client can upload a `.mtx`/`.h5` dataset file to an endpoint that invokes `ingest_10x` and returns the ingest result/status as part of the conversation flow.
  4. The session and upload endpoints are gated behind the same shared-password check as Phase 7 — no unauthenticated access.
**Plans**: 3/3 plans complete

Plans:
- [x] 08-01-PLAN.md — Wave 1: session_id plumbing fix + SessionMemory sessions table + GET /api/sessions[/{id}] (API-03) (completed 2026-09-12)
- [x] 08-02-PLAN.md — Wave 2: POST /api/upload multipart staging (.h5/.mtx trio) + ingest_10x wiring + conversation-flow recall (API-04) (completed 2026-09-12)
- [x] 08-03-PLAN.md — Wave 3: live_llm end-to-end integration test (real upload + real resume) + human-verify checkpoint (API-03, API-04) (completed 2026-09-12)

### Phase 9: Frontend Chat UI
**Goal**: A researcher-facing, OpenClaw-styled web frontend delivers the full local chat experience — password login, message thread, live tool-call activity, resolvable citations, session sidebar, and dataset upload — consuming the Phase 7-8 API, with no import or runtime dependency on the OpenClaw codebase itself.
**Depends on**: Phase 8
**Requirements**: UI-01, UI-02, UI-03, UI-04, UI-05, UI-06, UI-07
**Success Criteria** (what must be TRUE):
  1. An unauthenticated visitor sees a password-gated login screen and cannot reach any chat UI before authenticating successfully against API-05.
  2. After login, a researcher sees a chat-style message thread of question/answer turns for the active session.
  3. While the agent is working on a question, tool calls appear live in an activity view as they happen, sourced from the Phase 7 WebSocket stream.
  4. Citation tags (`[ref:TOOL_NAME:SHA256_PREFIX]`) in an answer render as inspectable elements that resolve to the underlying JSONL audit log entry, never as raw bracket text.
  5. A sidebar lists past sessions (from API-03) and lets the researcher resume any of them, restoring that session's thread.
  6. A dataset upload control in the composer (drag-and-drop or file picker) calls API-04 and surfaces ingest progress/result inline in the thread.
  7. The overall visual design (sidebar + main panel layout, dark theme, information density) is modeled on OpenClaw's own web UI, achieved by visual replication in bioclaw's own frontend code only — no OpenClaw code is imported or depended on.
**Plans**: 5 plans

Plans:
- [ ] 09-01-PLAN.md — Wave 1: Frontend scaffold (index.html, style.css, main.js) + POST /api/login + StaticFiles mount (UI-06, UI-07)
- [ ] 09-02-PLAN.md — Wave 2: JS API client module (api.js): fetch wrapper, WebSocket manager, all endpoint functions (UI-02)
- [ ] 09-03-PLAN.md — Wave 2: Chat thread + live activity view components (chat.js): message thread, activity events, composer wiring (UI-01, UI-02)
- [ ] 09-04-PLAN.md — Wave 3: Citation rendering + session sidebar + upload control + full app wiring (citations.js, sessions.js, main.js update) (UI-03, UI-04, UI-05)
- [ ] 09-05-PLAN.md — Wave 4: Fast-tier suite verification + human-verify browser checkpoint (UI-01..07)

### Phase 10: Packaging & Local Verification
**Goal**: The webapp (backend + frontend) ships self-contained in its own directory inside the `bioclaw` repo with its own dependencies, runs locally via a single documented command, and the full v1.1 feature set is manually verified end-to-end on that local run — with no deployment to any production/public environment performed or required.
**Depends on**: Phase 9
**Requirements**: PKG-01, PKG-02
**Success Criteria** (what must be TRUE):
  1. All webapp backend and frontend code and dependencies live inside their own directory in the `bioclaw` repo, with no import or runtime dependency on the OpenClaw codebase.
  2. A single documented command starts the full webapp (backend + frontend) locally, from a clean checkout, without additional undocumented setup steps.
  3. Running that command and exercising the app manually confirms every v1.1 capability works together end to end: login gate, chat Q&A, live tool-call activity streaming, citation resolution, session list/resume, and dataset upload triggering ingest.
  4. No step in this phase deploys, or requires deploying, the webapp to DigitalOcean or any other production/public environment.
**Plans**: 2 plans

Plans:
- [ ] 10-01-PLAN.md — Wave 1: automated no-OpenClaw-dependency test, demo dataset generator script, README + webapp/README.md documentation (PKG-01, PKG-02)
- [ ] 10-02-PLAN.md — Wave 2: clean-checkout dry run + human-verify checkpoint — combined end-to-end browser walkthrough of all v1.1 capabilities (PKG-02)

---

## Milestone v1.2: Real Data + Bio FM Integration (Phases 11-14)

### Phase 11: Quick Wins — History Replay, h5ad Upload, CSV Export
**Goal**: Researchers can resume any session and see the full prior conversation, upload `.h5ad` files directly, and download cluster/DE/annotation results as CSV — three capabilities that are independent of each other and independent of FM and network, delivering immediate value with no new infrastructure risk.
**Depends on**: Phase 10
**Requirements**: HIST-01, DATA-02, EXPORT-01
**Success Criteria** (what must be TRUE):
  1. A researcher who resumes a session via the sidebar sees the complete prior conversation thread (all turns, inline tool activity, citations) — not a "Resuming session..." placeholder — with SQLite WAL mode enabled and per-message stored content capped at 64 KB to prevent database blowup.
  2. The upload endpoint accepts a single `.h5ad` file (in addition to the existing MTX trio) and routes it through the same ingest pipeline, returning the same ingest result shape.
  3. A researcher can click a download control for the active dataset and receive a CSV file containing cluster assignments, the DE table, and annotation results from the current session.
**Plans**: 3 plans

Plans:
- [ ] 11-01-PLAN.md — HIST-01: messages table + WAL mode in SessionMemory, API enrichment, JS history replay
- [ ] 11-02-PLAN.md — DATA-02: tiny_h5ad_file fixture + h5ad upload integration test
- [ ] 11-03-PLAN.md — EXPORT-01: GET /api/export/csv endpoint + exportCsv() frontend + download button

### Phase 12: Agent Data Access + Script Export
**Goal**: The agent can fetch real public single-cell datasets from cellxgene-census on demand without a file upload, and researchers can export any session's analysis as a self-contained scanpy script that reproduces the exact analysis run.
**Depends on**: Phase 11
**Requirements**: DATA-01, EXPORT-02
**Success Criteria** (what must be TRUE):
  1. A researcher can ask the agent for a dataset by tissue, organism, or assay and receive back an ingested, analysis-ready dataset handle — fetched from cellxgene-census, not from an uploaded file — with the census fetch running in `asyncio.to_thread()` so the event loop is not blocked.
  2. A researcher can request a scanpy script export from any session and receive a `.py` file that, when run from scratch, reproduces every QC threshold, analysis parameter, dataset source reference, and random seed that the session used.
**Plans**: 3 plans

Plans:
- [ ] 12-01-PLAN.md — Wave 0: census_data marker + ingest/census.py (ingest_from_anndata + census source format) + DATA-01/EXPORT-02 test scaffolds (DATA-01, EXPORT-02)
- [ ] 12-02-PLAN.md — DATA-01: fetch_census_dataset tool (asyncio.to_thread census fetch) + bioclaw_server registration
- [ ] 12-03-PLAN.md — EXPORT-02: generate_analysis_script + GET /api/export/script + frontend Export Script button

### Phase 13: Real FM Inference — scGPT then Geneformer
**Goal**: Real scGPT inference replaces the subprocess stub for cell-type annotation, and Geneformer is added as a second perturbation-response model option — sequenced so the validated subprocess pattern from scGPT is reused for Geneformer's more complex four-step pipeline.
**Depends on**: Phase 12
**Requirements**: FM-01, FM-02
**Success Criteria** (what must be TRUE):
  1. The agent invokes real scGPT inference (not a stub) for cell-type annotation, returning per-cell-type predictions with a k-NN vote-fraction confidence proxy, with the `scgpt.tasks.embed_data()` API shape verified against the actual bio_fm_worker before the worker script is written.
  2. The agent can invoke Geneformer as an alternative perturbation-response model, returning a ranked gene list by cosine shift that is explicitly distinct from the linear model's expression-vector output — with Ensembl IDs validated in `adata.var` before inference runs, since gene symbols produce silent zero-length tokens.
  3. Both FM inference paths run in isolated Python 3.10 venvs reached via subprocess, reusing the same client pattern established for scGPT in this phase.
**Plans**: 4 plans

Plans:
- [ ] 13-01-PLAN.md — FM-01: k-NN vote-fraction confidence in run_scgpt_embed.py::_match_and_aggregate(), real bio_fm_smoke re-verification checkpoint
- [ ] 13-02-PLAN.md — FM-02: Geneformer output dataclasses, perturbation/ensembl.py validator, geneformer_smoke marker, isolated geneformer_worker/ venv setup
- [ ] 13-03-PLAN.md — FM-02: geneformer_worker/run_geneformer_perturb.py four-step pipeline CLI + perturbation/geneformer_client.py subprocess shim
- [ ] 13-04-PLAN.md — FM-02: predict_geneformer() composition + predict_perturbation_geneformer_tool + real end-to-end smoke test checkpoint

### Phase 14: Docker Compose Deployment
**Goal**: The full stack — backend, frontend, and optional GPU worker for bio FM inference — starts from a clean checkout with a single `docker compose up` command, requiring only environment variable configuration, with the single-worker constraint hard-coded to preserve the in-memory queue registry.
**Depends on**: Phase 13
**Requirements**: DOCK-01
**Success Criteria** (what must be TRUE):
  1. Running `docker compose up` from a clean checkout of the repo, with only environment variables configured, starts a working backend, frontend, and optional GPU worker — no manual setup steps required beyond env vars.
  2. The compose configuration hard-codes `--workers 1` for the backend service; multi-worker is explicitly blocked since the in-memory queue registry does not survive across workers.
  3. A researcher can perform the complete workflow (upload or census-fetch a dataset, run analysis, call FM inference, download CSV export, export scanpy script) against the compose stack without any locally-installed Python dependencies.
**Plans**: TBD

## Progress

**Execution Order:**
Phases execute in numeric order: 1 → 2 → 3 → 4 → 5 → 6 → 7 → 8 → 9 → 10 → 11 → 12 → 13 → 14

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. Ingest + QC Pipeline | 5/5 | Complete   | 2026-09-04 |
| 2. Analysis Tool Layer | 5/5 | Complete   | 2026-09-05 |
| 3. Agent Orchestration Wiring | 5/5 | Complete    | 2026-09-05 |
| 4. Bio-FM Tool Layer — Cell-Type Annotation | 5/5 | Complete   | 2026-09-08 |
| 5. Perturbation-Response Tool + VCC Benchmark | 6/6 | Complete   | 2026-09-10 |
| 6. Natural-Language Q&A Capstone | 3/3 | Complete   | 2026-09-11 |
| 7. Backend API + Streaming Foundation | 3/3 | Complete   | 2026-09-12 |
| 8. Session & Dataset Endpoints | 3/3 | Complete   | 2026-09-12 |
| 9. Frontend Chat UI | 5/5 | Complete   | 2026-09-14 |
| 10. Packaging & Local Verification | 2/2 | Complete   | 2026-09-15 |
| 11. Quick Wins — History Replay, h5ad Upload, CSV Export | 3/4 | Complete    | 2026-09-17 |
| 12. Agent Data Access + Script Export | 3/3 | Complete    | 2026-09-17 |
| 13. Real FM Inference — scGPT then Geneformer | 1/4 | In Progress|  |
| 14. Docker Compose Deployment | 0/TBD | Not started | - |
