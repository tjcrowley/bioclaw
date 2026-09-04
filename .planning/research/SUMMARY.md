# Project Research Summary

**Project:** BioClaw
**Domain:** Agentic harness for biological foundation models (single-cell transcriptomics MVP)
**Researched:** 2026-09-03
**Confidence:** MEDIUM-HIGH

## Executive Summary

BioClaw is an agent-orchestrated bioinformatics tool: a Claude-based, OpenClaw-style agentic loop sitting on top of the scverse ecosystem (scanpy/AnnData) and two categories of bio foundation models (cell-type-annotation FMs — scGPT/Geneformer — and a perturbation-response model, GEARS/cell-gears). Experts building systems like this in 2025-2026 converge on one architecture regardless of source (CellAgent, CellAtria/CellExpress, OmicVerse, Biomni): a clean separation between an agent orchestrator that never touches raw data, a layer of deterministic, typed tool calls wrapping scanpy pipelines, and a GPU-resident model-serving layer reached only through a thin client/server boundary. This is not a novel architecture to invent — it's a converged pattern that should be adopted directly, which de-risks the harness/orchestration side of the project considerably.

The recommended approach: build bottom-up. Ingest (10x `.mtx`/`.h5` → canonical `.h5ad`) and QC first as CPU-only, agent-independent deterministic pipelines; validate the tool-calling contract with cheap scanpy-backed analysis tools (clustering, DE) before introducing any GPU dependency; only then add the bio-FM tool layer (self-hosted or Modal-hosted, behind an identical client interface either way) for cell-type annotation and perturbation prediction; and build the Virtual Cell Challenge benchmark harness last, as an independent, agent-bypassing validator. Stack choices are largely non-controversial and high-confidence (Python 3.12, scanpy 1.12, anndata, Claude Agent SDK + MCP, PyTorch for the FM layer) — the genuinely open questions are infrastructural (self-host vs. hosted GPU inference) rather than architectural.

The dominant risk is not "can we build the harness" but "will the harness produce trustworthy answers." Two independent bodies of evidence say no by default: peer-reviewed benchmarks show scGPT/Geneformer used zero-shot frequently underperform trivial statistical baselines, and scBench found frontier LLM agents score only 29-53% accuracy on real-world scRNA-seq tasks, with large platform-dependent swings. Compounding this, several silent-corruption failure modes are specific to the scverse stack (the `.raw` reference-semantics footgun, naive global QC thresholds, over-aggressive batch correction erasing real perturbation signal) that an agent composing tool calls automatically is more likely to trigger than a human running one script at a time. Mitigation is consistent across all four research files: every FM tool call must ship with a statistical baseline for comparison, every deterministic tool must validate its input layer/contract and fail loudly rather than silently proceeding, and no natural-language answer should ship without a traceable link back to the specific logged tool-call output it summarizes. These guardrails should be built into the MVP from day one, not retrofitted — they are cheap now and expensive to add after the fact.

## Key Findings

### Recommended Stack

The stack splits into three isolated Python environments bridged by MCP tool calls: an orchestrator env (Claude Agent SDK + MCP, Python 3.12+), a scanpy pipeline env (Python 3.12+, scanpy 1.12.4 + anndata 0.13.x — the ecosystem's mandated `.h5ad` substrate), and one or more isolated bio-FM envs (Python 3.10, conda/pixi-managed) for scGPT and GEARS, which pin older Python/CUDA/PyTorch-Geometric versions incompatible with the scanpy env. This three-environment split is not optional — it's forced by real, documented version conflicts (scanpy requires Python ≥3.12; scGPT requires <3.11; GEARS pins an older PyTorch Geometric stack) and is exactly what the MCP tool-call boundary is designed to bridge.

**Core technologies:**
- Python 3.12+ / scanpy 1.12.4 / anndata 0.13.x — the de facto scverse standard for ingest, QC, clustering, DE; `.h5ad` is PROJECT.md's own mandated canonical format
- Claude Agent SDK (Python, `claude-agent-sdk`) + MCP — reuses the proven OpenClaw orchestration pattern (sessions, subagents, tool routing, permissions) instead of building an agent loop from scratch
- PyTorch 2.x — universal substrate for scGPT, Geneformer, and GEARS (all PyTorch-native)
- `cell-gears` (GEARS) — the most directly-applicable existing perturbation-response model, GNN-based, pairs naturally with the Virtual Cell Challenge dataset/task format
- `cellxgene-census` — sources a public pilot/validation dataset before Biopunk Labs' own wet-lab data is available
- Modal (or self-hosted GPU) — elastic, per-second-billed GPU serving for the bio-FM inference layer; fits an internal, low-frequency-call tool better than an always-on GPU box, and the client/server boundary is identical whether self-hosted or Modal-hosted

Notable "what NOT to use": don't force all dependencies into one shared environment (version conflicts are unresolvable); don't build a custom agent loop (duplicates the SDK); don't reach for a vector database for memory yet (SQLite/DuckDB is sufficient at this scale); `scanpy.tl.louvain` is deprecated — use `leiden(flavor="igraph")`.

### Expected Features

**Must have (table stakes):**
- Ingest 10x `.mtx`/`.h5` → canonical `.h5ad`
- Standard QC (mito %, doublet detection, low-count filtering)
- Normalization + PCA/UMAP + Leiden clustering
- Differential expression between clusters/conditions
- Some form of cell-type annotation
- Export/interop back to standard formats
- Basic reproducibility/provenance of an analysis run

**Should have (differentiators — this is BioClaw's actual wedge):**
- Natural-language question → interpreted answer (no commercial SaaS tool does this; academic agents aren't productized for one lab's workflow) — this *is* the Core Value from PROJECT.md
- FM-backed cell-type annotation (scGPT/Geneformer) as a differentiator over marker-gene pattern matching
- Perturbation-response prediction as a tool call — the strongest, most externally-validated differentiator (zero commercial no-code tools offer this; Arc Institute built an entire competition, the VCC, around exactly this task)
- Persistent multi-turn session/memory — no surveyed single-cell tool, commercial or academic, has this
- Agent composing multiple tools per question without the researcher specifying the pipeline — real differentiator, but scBench's 29-53% accuracy finding means this needs a reliability mitigation, not blind trust
- Auditable tool-call trace/provenance attached to every answer

**Defer (v2+):**
- Full no-code GUI/dashboard — competing on GUI polish abandons the actual differentiator
- Training bio FMs from scratch — wrap existing open-weight models instead
- Additional modalities (spatial, ATAC, CITE-seq, multi-omics) — dilutes the scRNA-seq wedge
- Autonomous open-ended hypothesis generation (CellVoyager-style) — conflicts with the scoped, question-driven MVP interaction model
- Formal Virtual Cell Challenge competition entry — use VCC as a benchmark/validation target only, not a leaderboard chase
- Multi-agent planner/executor/evaluator architecture — only justified once single-loop reliability is proven insufficient

### Architecture Approach

The converged pattern across every source (CellAgent, CellAtria/CellExpress, OmicVerse, Biomni, scBench): an agent orchestrator that plans/interprets but never touches raw data directly, a tool layer of small, coarse-grained, typed calls wrapping deterministic scanpy pipelines and thin bio-FM clients, a GPU-resident model-serving layer that is always a separate process reachable only via network/RPC (never imported into the agent process), and an eval harness that calls the same tool contract directly, bypassing the agent loop, for repeatable benchmark scoring. Large artifacts (AnnData matrices, embeddings) never enter agent context — tools write to a canonical, versioned dataset store and return small structured JSON summaries.

**Major components:**
1. **Agent Orchestrator** — multi-turn session loop, planning (plan → tool call → observe → continue), tool routing, persistent dataset/finding memory; zero GPU dependency
2. **Ingest + Analysis Tool Layer** — deterministic scanpy-backed pipelines (ingest, QC, clustering, DE) exposed as a small number of coarse-grained typed tool calls; no LLM involvement inside the tool itself
3. **Bio-FM Tool Layer + Model Serving Layer** — thin, stateless client (agent-facing) calling a separate long-running, GPU-resident inference service (scGPT/Geneformer/GEARS); this client/server split is exactly what defers the self-host-vs-hosted decision without rework
4. **Data/State Layer** — canonical versioned `.h5ad` store + session/memory store (dataset refs, findings, conversation state)
5. **Benchmark/Eval Harness** — offline, out-of-band; drives the perturbation tool directly against the VCC public dataset for deterministic, agent-loop-independent scoring

Suggested build order (dependency-driven, per ARCHITECTURE.md): ingest pipeline → analysis tool layer (validate as plain Python before wrapping) → agent orchestrator wiring against CPU-only tools first → model serving + bio-FM tool layer (GPU decision resolved here) → perturbation-prediction tool → VCC benchmark harness last.

### Critical Pitfalls

1. **Silent raw-count corruption via `.raw`** — `adata.raw = adata` is a reference, not a copy; a later normalization call silently corrupts what looks like a "safe" backup, feeding log-normalized floats to tools (scanpy DE, bio-FM tokenizers) that expect raw integer counts, with no error thrown. Avoid by persisting `adata.layers['counts'] = adata.X.copy()` at ingest time, before any normalization, and having every downstream tool validate its expected input layer and fail loudly on mismatch.
2. **Batch correction silently erasing real biological signal** — peer-reviewed 2025 benchmarks show popular methods (Harmony, scVI, MNN, LIGER) are poorly calibrated and can suppress genuine perturbation effects while "fixing" the UMAP visually. Directly dangerous for the perturbation-prediction wedge. Avoid by never hard-coding batch correction as an unconditional pipeline step — make it an explicit, logged, conditional decision.
3. **Bio foundation models underperforming trivial baselines, undetected** — multiple 2025 peer-reviewed papers (Nature Methods, Genome Biology) found scGPT/Geneformer used zero-shot frequently lose to simple linear/mean baselines; VCC's own 2025 organizers confirmed the same at competition scale. An agentic harness that treats "FM says X" as ground truth without a baseline comparison will confidently report a worse-than-trivial answer. Avoid by building a cheap statistical baseline as a first-class tool alongside every FM tool from day one, and comparing before presenting any FM-derived result.
4. **LLM hallucinating/overclaiming when interpreting quantitative output** — this is the single highest-risk failure mode because it sits directly on top of BioClaw's core value proposition ("interpreted answer, not raw output"). Avoid by requiring every scientific tool to return structured confidence/uncertainty alongside point estimates, requiring the agent to cite specific numeric outputs it summarizes, and never letting a natural-language answer be the only artifact — always link the underlying structured result.
5. **Tool-call hallucination ("tool bypass")** — under uncertainty or when a real tool call is slow/expensive (bio-FM inference), agents can generate a plausible-looking simulated result instead of actually invoking the tool. Avoid with strict tool-call validation, execution logging with request/response hashes, and a pre-answer check that every claimed tool output corresponds to a real logged invocation.

## Implications for Roadmap

Based on combined research, suggested phase structure:

### Phase 1: Ingest + QC Pipeline
**Rationale:** Foundational — every other component (analysis, FM tools, agent, benchmark) depends on canonical, trustworthy `.h5ad` data existing. Build and test standalone against a public dataset (cellxgene-census), no agent, no GPU.
**Delivers:** `ingest_10x()` and `run_qc()` as deterministic, agent-independent Python functions/pipelines; a canonical, versioned `.h5ad` store with an explicit, immutable `adata.layers['counts']` contract.
**Addresses:** "Ingest raw 10x Genomics output → canonical AnnData" and "Run standard QC" (both PROJECT.md Active requirements; both FEATURES.md table stakes).
**Avoids:** Pitfall 1 (silent raw-count corruption via `.raw`) and Pitfall 3 (naive global QC thresholds silently biasing which cell types survive) — both must be designed out at this phase, before any tool is built on top of this data contract.

### Phase 2: Analysis Tool Layer (Clustering + DE)
**Rationale:** Depends only on Phase 1's canonical AnnData; validates the "coarse-grained deterministic tool" contract cheaply (CPU-only, no GPU complexity) before the agent or any bio-FM is introduced.
**Delivers:** `cluster()` (Leiden via `flavor="igraph"`, not deprecated Louvain) and `diff_expr()` (Wilcoxon rank-sum, matching VCC's own DES metric) as typed, agent-callable tools; each returns a bounded structured summary, not raw matrices.
**Uses:** scanpy 1.12.4 (`tl.leiden`, `tl.rank_genes_groups`), anndata.
**Implements:** Analysis Tool Layer component from ARCHITECTURE.md.

### Phase 3: Agent Orchestration Wiring
**Rationale:** Wire the OpenClaw-style agentic loop (session/memory/tool routing) to call the Phase 1-2 tools first, since they're CPU-only and deterministic — this validates tool-calling and session/memory behavior before adding GPU/model-serving complexity, exactly as ARCHITECTURE.md's suggested build order recommends.
**Delivers:** Claude Agent SDK + MCP orchestrator with sessions, persistent dataset/finding memory, and tool routing to the ingest/QC/analysis tools; execution-trace logging built in from the start (not bolted on later).
**Addresses:** "Orchestrate via a Claude-based agent using an OpenClaw-style agentic loop" and "Persist dataset and finding context across a multi-turn conversation" (PROJECT.md Active requirements).
**Avoids:** Pitfall 6 (tool-call hallucination/"tool bypass") — execution-trace validation must be a structural part of the tool-calling loop from this phase forward, since it's far more expensive to retrofit once GPU-bound bio-FM tools (slower, more tempting to "simulate") are added in Phase 4.

### Phase 4: Bio-FM Tool Layer — Cell-Type Annotation
**Rationale:** Add only once the tool-calling contract is proven end-to-end on cheap CPU-only tools (Phase 3). This is where the open self-host-vs-hosted GPU infrastructure decision must be resolved — the client/server split (thin client in the tool layer, model weights in a separate serving process) defers this decision cleanly regardless of which way it's resolved.
**Delivers:** `annotate_celltype()` tool wrapping scGPT or Geneformer behind a stable HTTP/gRPC client, backed by a separate GPU-resident model-serving process (local subprocess or Modal-hosted); a mandatory statistical baseline tool (marker-gene/`decoupler`-based) alongside it for comparison.
**Addresses:** "Call a bio foundation model (scGPT or Geneformer) as a tool for cell-type annotation" (PROJECT.md Active requirement).
**Avoids:** Pitfall 4 (FM underperforming a trivial baseline, undetected) and Pitfall 8 (cell-type label mismatch across reference atlases/ontologies) — annotation output must include reference/confidence/ontology metadata, not a bare label string.

### Phase 5: Perturbation-Response Tool + VCC Benchmark Harness
**Rationale:** Builds directly on Phase 4's model-serving infra. The VCC benchmark harness requires this tool to exist first, but is otherwise structurally independent of everything else and validates the wedge with the strongest, most externally credible evidence available (Arc Institute's own public dataset/task/metrics).
**Delivers:** `predict_perturbation()` tool (GEARS/cell-gears-backed, or a hybrid statistical+neural approach per VCC 2025's own finding that pure deep learning underperformed hybrids); an eval harness that calls this tool directly (bypassing the agent loop) against VCC's public dataset, reporting all three official metrics (PDS, DES, MAE) plus a naive-baseline comparison — not a single cherry-picked metric.
**Addresses:** "Call a perturbation-response model as a tool" and "evaluate against the Virtual Cell Challenge's public dataset/task format" (both PROJECT.md Active requirements).
**Avoids:** Pitfall 2 (batch correction erasing perturbation signal), Pitfall 4 (again — pure FM output vs. baseline), and Pitfall 7 (VCC metrics gamed/misread if used naively — MAE alone is documented as unreliable per Arc's own 2025 wrap-up).

### Phase 6: Natural-Language Q&A (Capstone Demo)
**Rationale:** This is the capstone — it requires every other tool (Phases 1-5) to exist as a callable primitive first, and is explicitly the proof of Core Value from PROJECT.md. Should not ship without the verification/traceability mechanisms below, per PITFALLS.md's assessment that this is "the highest-risk phase in the whole roadmap."
**Delivers:** End-to-end natural-language question → interpreted answer, with every claim traceable back to a specific logged tool-call result; uncertainty/confidence surfaced alongside point estimates; a linked structured artifact (plot/table/DE list) attached to every answer, not just prose.
**Addresses:** "Researcher can ask a natural-language question and receive an interpreted answer" (PROJECT.md's explicit end-to-end demo requirement); this is also where FEATURES.md's differentiators (auditable tool-call trace, agent composing multiple tools per question) land.
**Avoids:** Pitfall 5 (LLM hallucinating/overclaiming when interpreting quantitative output) — the single highest-risk pitfall identified across all four research files, concentrated exactly at this phase.

### Phase Ordering Rationale

- **Dependency-driven, bottom-up:** every research file independently converges on the same order — deterministic, CPU-only, agent-independent pieces (ingest, QC, analysis) must exist and be validated before the agent loop is wired up, and the agent loop must be proven on cheap tools before GPU/bio-FM complexity is introduced. This is explicit in ARCHITECTURE.md's "Suggested Build Order" and implicitly required by FEATURES.md's dependency graph (FM-backed annotation and perturbation prediction both gate on the unresolved FM-hosting decision — pushing them later reduces the blast radius of that open question).
- **The two strongest differentiators (FM annotation, perturbation prediction) are also the two highest-infrastructure-risk items** (GPU hosting decision, isolated Python environments for scGPT/GEARS) — sequencing them after the orchestration pattern is proven means a hosting/infra delay doesn't block validating the rest of the harness.
- **The VCC benchmark harness is structurally last but was flagged by FEATURES.md as buildable in parallel** using VCC's own public dataset (independent of Biopunk Labs' wet-lab data) — worth revisiting during roadmap planning whether to pull it earlier to de-risk "do we even have real perturbation data" sooner, at the cost of some resequencing.
- **Guardrails against the identified pitfalls (baseline comparisons, execution-trace logging, layer-contract validation, uncertainty surfacing) are woven into each phase's own deliverables above, not deferred to a separate "hardening" phase** — PITFALLS.md is explicit that these are cheap to build now and expensive to retrofit (LOW-MEDIUM recovery cost for raw-count corruption vs. MEDIUM-HIGH recovery cost for retrofitting execution-trace logging after hallucinated claims have shipped).

### Research Flags

Phases likely needing deeper research during planning:
- **Phase 4 (Bio-FM Tool Layer — Cell-Type Annotation):** exact VRAM/hardware requirements for scGPT and Geneformer are explicitly flagged LOW confidence across STACK.md and ARCHITECTURE.md — verify against current model cards before implementation; also the self-host-vs-Modal decision needs Biopunk Labs' actual hardware constraints, which aren't yet known.
- **Phase 5 (Perturbation-Response Tool + VCC Benchmark Harness):** GEARS/cell-gears environment setup (pinned older PyTorch Geometric stack) is flagged MEDIUM confidence and isolation-sensitive; the 2026 VCC task format is zero-shot/cross-cell-line (a materially harder bar than the likely first Biopunk Labs single-cell-type use case) — needs explicit scope confirmation with Elliot before committing to "benchmark against the current leaderboard" vs. "benchmark against the task format/metrics only."
- **Phase 6 (Natural-Language Q&A):** no established reference implementation exists for the hallucination-mitigation mechanisms (confidence-surfacing, claim traceability) at this specific combination of agent + scientific-tool-output; scBench's 29-53% accuracy finding suggests this needs deliberate design attention, not a standard pattern to copy.

Phases with standard patterns (skip research-phase):
- **Phase 1 (Ingest + QC):** scanpy/anndata ingest and QC are extremely well-documented, HIGH-confidence, standard scverse patterns.
- **Phase 2 (Analysis Tool Layer):** clustering/DE via scanpy is commodity, HIGH confidence, no novel design needed.
- **Phase 3 (Agent Orchestration Wiring):** Claude Agent SDK + MCP integration is officially documented (HIGH confidence) and is explicitly the "reuse a proven pattern" path PROJECT.md already chose.

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | MEDIUM-HIGH | Core Python/scverse/Claude Agent SDK stack verified against current PyPI/official docs (HIGH); bio-FM hardware/VRAM specifics thinner in public docs (LOW, flagged explicitly) |
| Features | MEDIUM-HIGH | Virtual Cell Challenge specifics HIGH (official Arc Institute sources); competitor feature claims MEDIUM (vendor/academic cross-referenced); emerging agentic-tool capability claims MEDIUM-LOW (fast-moving preprint space) |
| Architecture | MEDIUM | Component boundaries HIGH confidence (converge across every independent source: CellAgent, CellAtria/CellExpress, OmicVerse, Biomni, scBench); specific infra choices (serving frameworks, GPU sizing) MEDIUM/LOW, re-verify before Phase 4 |
| Pitfalls | MEDIUM-HIGH | Mix of peer-reviewed sources (batch correction, FM-vs-baseline benchmarks, scverse GitHub issues) at HIGH confidence, and preprint-sourced agent-specific failure modes (tool bypass, hallucination taxonomy) at MEDIUM confidence |

**Overall confidence:** MEDIUM-HIGH

### Gaps to Address

- **Bio-FM hosting decision (self-host vs. Modal/hosted)** — explicitly unresolved in PROJECT.md, pending Biopunk Labs' actual GPU capacity. Architecture (client/server split) defers this cleanly, but Phase 4 planning needs a real answer before implementation, not just before design.
- **Exact scGPT/Geneformer inference VRAM requirements** — not independently confirmed in any research file (LOW confidence); verify against current model cards before sizing Phase 4 infrastructure.
- **2026 VCC zero-shot/cross-cell-line task format vs. Biopunk Labs' likely single-cell-type first use case** — a scope decision needs to be made explicit with Elliot Roth: benchmark against VCC's task format/metrics (achievable) vs. benchmark competitively against the live 2026 leaderboard (a much higher, likely out-of-scope bar).
- **First real dataset source** — CONCEPT.md/PROJECT.md flags this as open; STACK.md recommends `cellxgene-census` as a public pilot/validation dataset bridge until Biopunk Labs' own wet-lab data is available, but this hasn't been confirmed with Elliot.
- **Agent reliability on real (non-toy) data** — scBench's 29-53% accuracy finding is a field-wide, not BioClaw-specific, result; there is no established reference architecture yet for a lightweight self-check/evaluator step that fits this MVP's scope (flagged as P2, add-after-validation in FEATURES.md, but the underlying failure mode needs the guardrails from Phase 6 above from day one regardless).

## Sources

### Primary (HIGH confidence)
- https://scanpy.readthedocs.io/en/stable/release-notes/index.html — scanpy 1.12.x release notes
- https://pypi.org/project/scanpy/, https://pypi.org/project/anndata/ — current package versions/dependency pins
- https://code.claude.com/docs/en/agent-sdk/mcp — Claude Agent SDK MCP integration (official docs)
- https://arcinstitute.org/news/virtual-cell-challenge-2026, https://arcinstitute.org/news/virtual-cell-challenge-2025-wrap-up — official VCC task format, metrics, 2025 post-mortem
- https://www.cell.com/cell/fulltext/S0092-8674(25)00675-0 — VCC framing paper (peer-reviewed)
- https://www.nature.com/articles/s41592-025-02772-6 (Nature Methods 2025) and https://link.springer.com/article/10.1186/s13059-025-03574-x (Genome Biology 2025) — scGPT/Geneformer underperforming baselines
- https://pmc.ncbi.nlm.nih.gov/articles/PMC12315870/ — batch correction miscalibration (peer-reviewed, 2025)
- https://github.com/scverse/scanpy/issues/3073 — `.raw` reference-semantics footgun (official repo issue)
- https://www.10xgenomics.com/analysis-guides/common-considerations-for-quality-control-filters-for-single-cell-rna-seq-data — official QC guidance

### Secondary (MEDIUM confidence)
- https://github.com/bowang-lab/scGPT, https://github.com/snap-stanford/GEARS — model requirements, environment isolation
- https://www.nature.com/articles/s44387-025-00064-0 (CellAtria/CellExpress), https://purl.stanford.edu/cv694yk7414 (OmicVerse), https://github.com/snap-stanford/biomni — architecture pattern convergence
- https://scverse.org/blog/2025-core-expansion/ — pertpy/decoupler as scverse core (official announcement)
- Modal pricing/architecture — aggregator-sourced, cross-checked but not fetched directly from modal.com

### Tertiary (LOW confidence)
- https://arxiv.org/abs/2602.09063 (scBench) — 29-53% agent accuracy finding; single benchmark, fast-moving preprint space, worth re-verifying
- scGPT/Geneformer exact VRAM figures — not independently confirmed this session, flagged for re-verification before Phase 4
- https://arxiv.org/pdf/2506.21967 — tool-call hallucination/"tool bypass" preprint finding

---
*Research completed: 2026-09-03*
*Ready for roadmap: yes*
