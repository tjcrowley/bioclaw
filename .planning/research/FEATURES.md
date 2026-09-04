# Feature Research

**Domain:** Single-cell transcriptomics analysis tools + emerging agentic bioinformatics assistants
**Researched:** 2026-09-03
**Confidence:** MEDIUM-HIGH (VCC specifics HIGH — official Arc sources; competitor feature claims MEDIUM — cross-referenced vendor/academic sources; agentic-tool capability claims MEDIUM-LOW — fast-moving preprint space, verify before committing to specific baselines)

## Feature Landscape

### Table Stakes (Users Expect These)

These are the floor. A researcher moving from scanpy/Seurat or a commercial single-cell SaaS to BioClaw will consider it broken if these are missing — even though BioClaw's whole pitch is "you shouldn't need a script or a GUI for this."

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| Ingest standard 10x Genomics output (`.mtx`, `.h5`) → canonical `.h5ad` | Every scanpy/Seurat pipeline, CELLxGENE, Loupe Browser, BioTuring, and Cellenics all start here; `.h5ad`/AnnData is the de facto interchange format across the ecosystem | LOW-MEDIUM | Already in PROJECT.md scope. scanpy's `read_10x_mtx`/`read_10x_h5` do the heavy lifting |
| Standard QC (mito %, doublet detection, low-count/gene filtering) | Universal first step in every scRNA-seq tutorial and every commercial tool (Partek Flow, BBrowserX, Cellenics, Trailmaker); skipping this produces garbage downstream results | LOW-MEDIUM | scanpy `pp.calculate_qc_metrics` + `scrublet`/`scDblFinder`-equivalent for doublets |
| Normalization + dimensionality reduction (log-norm, HVG selection, PCA) | Prerequisite for every downstream step (clustering, DE, annotation); absent from no tool surveyed | LOW | Standard scanpy `pp.normalize_total`, `pp.log1p`, `pp.highly_variable_genes`, `pp.pca` |
| Clustering (Leiden/Louvain) + 2D embedding (UMAP) | Every tool surveyed (CELLxGENE Explorer, Loupe Browser, BBrowserX, Partek Flow, ScarfWeb) leads with cluster + UMAP as the primary exploratory view | LOW-MEDIUM | scanpy `tl.leiden`, `tl.umap` — commodity at this point |
| Differential expression between clusters/conditions | Baseline analytical output every tool provides (Wilcoxon rank-sum is the field standard, notably also the exact test VCC itself uses for its DES metric) | LOW-MEDIUM | scanpy `tl.rank_genes_groups` |
| Cell-type annotation (some form — marker-based or reference-based) | CELLxGENE mandates Cell Ontology labels on every submitted dataset; BBrowserX, Trailmaker (ScType/CellTypist/Decoupler), ScarfWeb (CyteType) all ship auto-annotation; researchers expect a cell-type call, not just a cluster number | MEDIUM | BioClaw's differentiator is *how* (FM-driven, see below) but *having* an annotation is table stakes |
| Export/interop back to standard formats (`.h5ad`, plots, gene lists) | Researchers still need to hand results to collaborators using scanpy/Seurat, or drop a UMAP into a paper figure; a tool that traps data is a non-starter | LOW | Round-trip `.h5ad` + static plot export (PNG/SVG) covers most needs |
| Reproducibility / provenance of an analysis run | Standard expectation in wet-lab-adjacent tooling (Pluto Bio and ROSALIND both advertise versioning/audit trails); researchers need to answer "how was this UMAP made" for lab notebooks and papers | LOW-MEDIUM | Log parameters + tool-call trace per session; doesn't need to be a full workflow-versioning system for MVP |
| Batch integration / batch correction across samples | Table stakes once >1 sample is involved (Harmony/scVI are standard in scanpy/scverse; BBrowserX and Partek Flow both ship it) | MEDIUM-HIGH | Deferrable to v1.x if MVP demo is single-sample, but flag: multi-sample is the realistic Biopunk Labs case, not a toy single dataset |

### Differentiators (Competitive Advantage)

These are where BioClaw earns its wedge — none of the commercial no-code tools (Cellenics, Loupe Browser, Partek Flow, BBrowserX) offer them, and the emerging agentic tools (CellAgent, CellVoyager, Biomni) are academic prototypes, not production internal tools tied to a specific lab's workflow.

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| Natural-language question → interpreted answer (not raw plot/table) | This *is* the Core Value in PROJECT.md — replaces both hand-written scanpy scripts and no-code GUI clicking. No commercial SaaS tool does this; academic agents (CellAgent, CellVoyager) do but aren't productized for a specific lab | MEDIUM-HIGH | The orchestration loop (plan → tool call → observe → continue) is the whole product; scanpy/FM calls are "just" tools underneath |
| Foundation-model-backed cell-type annotation (scGPT/Geneformer as a tool call) | Marker-gene/reference-based annotation (BBrowserX MetaReference, ScType, CellTypist) is pattern-matching against known references; FM embeddings can generalize to novel/ambiguous populations and give confidence-scored calls | MEDIUM-HIGH | Requires hosting/serving scGPT or Geneformer (open question per PROJECT.md — self-host vs. hosted) |
| Perturbation-response prediction as a tool call (given control profiles + a target gene knockdown, predict resulting expression) | This is the single-cell field's genuinely hard, valuable, and current-research-frontier problem (see VCC section below) — essentially zero commercial no-code tools offer this at all; it's the differentiator with the most external validation (Arc Institute built an entire competition around it) | HIGH | Directly maps to the VCC task format — see below. This is BioClaw's strongest, most defensible differentiator because it has an external, credible benchmark already |
| Persistent multi-turn session/memory (agent remembers "the dataset we've been discussing") | No single-cell tool surveyed — commercial or academic — has conversational memory across a research session; closest analog is CellVoyager's paper-context retrieval, which is a different mechanism (RAG over literature, not session memory of an ongoing analysis) | MEDIUM | Reuse of OpenClaw's session/memory primitives per CONCEPT.md — this is inherited infrastructure, not built from scratch |
| Agent composes multiple tools/models per question without the researcher specifying the pipeline | CellAgent (planner/executor/evaluator) and Biomni (105 packages/59 databases as an agentic environment) prove this pattern works academically; no production internal-lab tool does it yet | HIGH | Real differentiator, but also real risk — see PITFALLS-adjacent note: scBench (arXiv 2602.09063) found frontier LLM agents score only 29-53% accuracy on real-world scRNA-seq analysis tasks, with 40+ point accuracy swings by platform/documentation quality. This is not a solved problem — budget for it |
| External, credible benchmark positioning (Virtual Cell Challenge task format as validation, not just "trust the demo") | Nearly every competitor (commercial SaaS, academic agent) demos on toy/curated data; being able to say "we validated the perturbation-prediction tool against Arc Institute's published task format and public dataset" is a credibility differentiator worth more than the raw score | MEDIUM | Requires building the eval harness, not necessarily competing — PROJECT.md already scopes this correctly as benchmark-not-competition |
| Auditable reasoning/tool-call trace attached to every answer | Researchers (esp. a wet-lab partner validating a new tool) will not trust a black-box "the answer is X" — showing which tools were called, in what order, on what data, builds trust that no chat-only or GUI-only competitor provides | LOW-MEDIUM | Cheap to build if the agentic loop already logs tool calls (it should, for debugging) — repurpose logs as user-facing provenance |

### Anti-Features (Commonly Requested, Often Problematic)

| Feature | Why Requested | Why Problematic | Alternative |
|---------|---------------|------------------|-------------|
| Full no-code GUI/dashboard (à la Cellenics/Partek Flow/BBrowserX) | "Researchers who don't want to talk to an agent might want to click around" | Building and maintaining a competitive GUI is a multi-year, multi-engineer investment (that's Partek's/BioTuring's whole product); competing on GUI polish abandons the actual differentiator (conversational agent) and turns BioClaw into an inferior clone of funded, mature commercial tools | Expose the same underlying tool layer (QC, clustering, annotation, perturbation) purely via the agent conversation; if a visual view is needed, render a plot inline in the chat response, not a standalone app |
| Building/training bio foundation models from scratch | "We could have a proprietary edge if we train our own model" | Training a competitive scGPT/Geneformer-class model requires compute and single-cell corpora far beyond an internal-tool MVP budget; this is a multi-year research program, not a wedge feature | Wrap existing open-weight models (scGPT, Geneformer) as tools; differentiate on orchestration, not on FM quality — this is explicitly the CONCEPT.md thesis |
| Supporting every single-cell modality (spatial, ATAC-seq, CITE-seq, multi-omics, TCR/BCR) day one | Commercial tools (BBrowserX, Pluto Bio, Trailmaker) all advertise multi-modal breadth as a checkbox feature | Each modality has its own QC conventions, formats, and FM landscape; chasing breadth before depth dilutes the MVP and delays the one demo that proves the wedge (scRNA-seq + perturbation prediction) | Ship scRNA-seq (10x Chromium/Flex) only for v1; explicitly out of scope per PROJECT.md (spatial/multi-omics not mentioned, keep it that way) |
| Raw FASTQ ingest (alignment, variant calling) | "A truly end-to-end tool should start from sequencer output" | Already explicitly out of scope in PROJECT.md — alignment/variant-calling pipelines are a project unto themselves and don't change the researcher's actual daily pain point (which starts after alignment, at the `.mtx`/`.h5` stage) | Ingest starts at 10x Genomics processed output (`.mtx`/`.h5`/`.h5ad`) — matches CONCEPT.md's stated ingest boundary |
| Autonomous open-ended hypothesis generation (CellVoyager-style "explore this dataset and tell me something interesting") | Sounds like the ultimate agentic capability — "just let the agent find insights" | CellVoyager reportedly takes up to an hour and significant API cost per exploratory run, and open-ended exploration is hard to validate/trust for a first internal-tool demo; also directly conflicts with PROJECT.md's scoped, question-driven interaction model | Keep v1 strictly question-driven (researcher asks, agent answers) — defer open-ended autonomous discovery to v2+, if ever |
| Multi-tenant SaaS (billing, auth, external customers) | Natural "make it a product" instinct once the internal tool works | Already explicitly out of scope in PROJECT.md; premature productization before internal validation risks building auth/billing/tenancy infrastructure nobody outside Biopunk Labs has asked for yet | Internal tool for Biopunk Labs researchers only, per PROJECT.md — revisit after validated internal usage |
| Direct chat interface to the bio foundation model itself (e.g., "talk to scGPT") | Feels like it would let researchers "interrogate the model directly" for more nuance | Bio FMs are not conversational — they embed/predict/score and stop (CONCEPT.md's own framing); exposing them as chat endpoints breaks the tool-call abstraction and reintroduces the "hand-interpret raw model output" problem BioClaw exists to solve | Bio FMs remain typed, bounded tool calls the orchestrator invokes and interprets — already correctly scoped as an anti-feature in PROJECT.md |
| Formal Virtual Cell Challenge competition entry/leaderboard submission in v1 | The challenge is public, has prize money, and "why not just submit and see how we rank" is tempting once the eval harness exists | Competing requires tuning specifically to win against ML specialists optimizing narrow metrics (2025 wrap-up: top teams engineered features specifically for PDS/DES after MAE became uncompetitive) — that's a different project (model research) from building an agent harness; also the 2026 format is zero-shot cross-cell-line generalization, a much harder bar than internal validation needs | Use VCC's public dataset, task format, and metrics as an internal validation/benchmark target only — exactly as PROJECT.md already scopes it |

## Feature Dependencies

```
Ingest (10x .mtx/.h5 → .h5ad)
    └──requires──> (nothing upstream — MVP entry point)

Standard QC (mito %, doublets, low-count filter)
    └──requires──> Ingest

Normalization + PCA/UMAP + Clustering
    └──requires──> Standard QC

Differential expression
    └──requires──> Clustering

FM-backed cell-type annotation (scGPT/Geneformer tool)
    └──requires──> Normalization (FMs consume normalized/HVG-selected expression)
    └──requires──> FM hosting/serving decision (self-host vs. hosted — open per PROJECT.md)

Perturbation-response prediction (tool call)
    └──requires──> Ingest of control (non-targeting) profiles
    └──requires──> FM hosting/serving decision
    └──enhances──> VCC benchmark validation

VCC benchmark harness (PDS, DES, MAE + eval scoring)
    └──requires──> Perturbation-response prediction tool
    └──requires──> Ability to ingest VCC's public dataset format (10x Flex, ~220K cells, control + perturbed)

Natural-language Q&A (agent loop: plan → tool call → observe → continue)
    └──requires──> All of the above as callable tools (ingest, QC, clustering, DE, annotation, perturbation)
    └──requires──> Orchestrator (Claude + OpenClaw-style loop)

Persistent session/memory across multi-turn conversation
    └──enhances──> Natural-language Q&A (not blocking — a single-turn demo works without it)

Auditable tool-call trace / provenance
    └──enhances──> Natural-language Q&A (builds trust; cheap if tool-call logging already exists for debugging)

Batch integration/correction (Harmony/scVI)
    └──requires──> Normalization + PCA
    └──enhances──> Clustering, DE (only matters once >1 sample is combined)

Multi-agent self-critique/evaluator loop (CellAgent-style planner/executor/evaluator)
    └──enhances──> Natural-language Q&A reliability (scBench shows frontier agents ~29-53% accuracy on real analysis tasks — a critique loop is the mitigation)
    └──conflicts──> MVP simplicity (adds orchestration complexity; defer past first demo)

Autonomous open-ended hypothesis generation (CellVoyager-style)
    └──conflicts──> Question-driven MVP interaction model (PROJECT.md anti-feature)
```

### Dependency Notes

- **FM-backed annotation and perturbation prediction both gate on the FM hosting decision.** PROJECT.md flags this as unresolved (self-host vs. hosted, pending Biopunk Labs' GPU capacity). This is the single biggest phase-ordering risk: both of BioClaw's strongest differentiators depend on an infrastructure decision that hasn't been made.
- **VCC benchmark harness requires the perturbation tool to exist first**, but is otherwise independent of the rest of the pipeline — it could be built and validated somewhat in parallel with the ingest/QC/clustering work, using VCC's own published dataset instead of a Biopunk Labs dataset, derisking the "do we even have real perturbation data" question early.
- **Natural-language Q&A is the capstone** — it requires every other analytical tool to exist as a callable primitive first. Roadmap phases should build tools bottom-up (ingest → QC → clustering/DE → annotation → perturbation) and only wire the conversational orchestrator on top once enough tools exist to make a demo interesting.
- **Multi-agent self-critique conflicts with MVP simplicity** but scBench's finding (29-53% accuracy, large platform-dependent swings) is a real warning: a single-pass agentic loop without any verification step is likely to produce confidently wrong answers on real (non-toy) data. Recommend flagging this as a phase-specific research/design topic rather than ignoring it — even a lightweight "did this tool call error or return an empty result" self-check is cheaper than full multi-agent evaluator architecture and reduces the biggest known failure mode.

## MVP Definition

### Launch With (v1)

Minimum viable product — matches PROJECT.md's "Active" requirements list; validates the wedge.

- [ ] Ingest 10x `.mtx`/`.h5` → canonical `.h5ad` — table stakes, everything else depends on it
- [ ] Standard QC (mito %, doublet detection, low-count filtering) — table stakes, required before any analysis is trustworthy
- [ ] Clustering + differential expression via scanpy-backed tools — table stakes, the baseline analytical capability
- [ ] Cell-type annotation via scGPT or Geneformer tool call — differentiator (FM-backed, not just marker matching)
- [ ] Perturbation-response prediction tool call (control profiles → predicted knockdown response) — the strongest differentiator, and the one with an external validation target
- [ ] Agent orchestration (plan → tool call → observe → continue) — the product itself, not optional
- [ ] Session/memory persistence across a multi-turn conversation — needed for the "dataset we've been discussing" UX described in CONCEPT.md
- [ ] Natural-language question → interpreted answer (the end-to-end demo) — the proof of Core Value
- [ ] VCC-format benchmark harness for the perturbation tool (ingest VCC's public control+perturbed dataset, compute PDS/DES/MAE-equivalent scores) — validation target, not a competition entry

### Add After Validation (v1.x)

- [ ] Batch integration/correction (Harmony or scVI) — trigger: first real Biopunk Labs dataset involves more than one sample/batch (likely immediately, given wet-lab data is rarely single-batch)
- [ ] Tool-call provenance/audit trail surfaced to the researcher — trigger: Elliot or a researcher asks "how did you get this answer" and the answer is currently only in logs
- [ ] Lightweight self-check/evaluator step on tool outputs (empty result detection, sanity-range checks) — trigger: any observed case of a confidently wrong or nonsensical agent answer during internal use (scBench suggests this will happen)
- [ ] Support for additional FM tool options (e.g., adding a second annotation or embedding model for cross-validation) — trigger: single-model annotation confidence is repeatedly ambiguous on real data

### Future Consideration (v2+)

- [ ] Multi-agent planner/executor/evaluator architecture (CellAgent-style) — defer: adds real orchestration complexity; only justified once single-loop reliability is proven insufficient in practice
- [ ] Autonomous open-ended hypothesis generation (CellVoyager-style) — defer: conflicts with the scoped, question-driven MVP interaction model; expensive (up to an hour/run in CellVoyager's own reporting) and hard to validate for trust
- [ ] Raw FASTQ ingest / alignment pipeline — defer: explicitly out of scope, doesn't address the actual researcher pain point (which starts post-alignment)
- [ ] Additional modalities (spatial, ATAC, CITE-seq, multi-omics) — defer: each is its own ingest/QC/FM landscape; dilutes the scRNA-seq wedge before it's proven
- [ ] Formal Virtual Cell Challenge competition submission — defer: a model-research project distinct from the agent-harness product; only pursue if the validated benchmark harness reveals BioClaw's underlying models are independently competitive
- [ ] Multi-tenant productization (billing, auth, external customers) — defer: explicitly out of scope until internal Biopunk Labs validation succeeds

## Feature Prioritization Matrix

| Feature | User Value | Implementation Cost | Priority |
|---------|------------|---------------------|----------|
| Ingest 10x → `.h5ad` | HIGH | LOW | P1 |
| Standard QC | HIGH | LOW | P1 |
| Clustering + DE | HIGH | LOW | P1 |
| FM-backed cell-type annotation | HIGH | MEDIUM-HIGH | P1 |
| Perturbation-response prediction tool | HIGH | HIGH | P1 |
| Agent orchestration loop | HIGH | MEDIUM | P1 |
| Session/memory persistence | MEDIUM | LOW (inherited from OpenClaw) | P1 |
| NL question → interpreted answer | HIGH | MEDIUM (capstone, integrates above) | P1 |
| VCC benchmark harness | HIGH (credibility) | MEDIUM | P1 |
| Batch integration/correction | MEDIUM-HIGH | MEDIUM | P2 |
| Tool-call provenance/audit UI | MEDIUM | LOW | P2 |
| Self-check/evaluator step | MEDIUM-HIGH (reliability) | LOW-MEDIUM | P2 |
| Multi-agent planner/executor/evaluator | LOW-MEDIUM (marginal over single loop for MVP scale) | HIGH | P3 |
| Autonomous hypothesis generation | MEDIUM (interesting, unvalidated) | HIGH | P3 |
| Additional modalities (spatial/ATAC/etc.) | LOW (for this wedge) | HIGH | P3 |
| Raw FASTQ ingest | LOW (for this wedge) | HIGH | P3 |
| Formal VCC competition entry | LOW (product value; possible marketing value) | HIGH | P3 |

**Priority key:**
- P1: Must have for launch
- P2: Should have, add when possible
- P3: Nice to have, future consideration

## Competitor Feature Analysis

| Feature | Commercial no-code SaaS (Cellenics / BBrowserX / Partek Flow) | Academic agentic tools (CellAgent / CellVoyager / Biomni) | Our Approach (BioClaw) |
|---------|---|---|---|
| Ingest & QC | Yes — polished, GUI-driven, multi-format | Yes — via scanpy/Seurat tool wrapping | Yes — same ecosystem tools (scanpy), wrapped as agent-callable |
| Clustering / DE / annotation | Yes — no-code, reference-database-driven (BBrowserX MetaReference, ScType) | Yes — agent invokes scanpy equivalents, some self-reflective refinement (CellAgent) | Yes — but annotation is FM-backed (scGPT/Geneformer), not purely reference-matching |
| Interaction model | Point-and-click GUI, no natural language | Natural language (research prototypes, not tied to one lab's workflow) | Natural language, purpose-built for Biopunk Labs' actual workflow and data |
| Perturbation-response prediction | Not offered by any surveyed no-code SaaS | Not a core focus of CellAgent/CellVoyager/Biomni (general-purpose analysis agents, not perturbation-modeling specialists) | Core differentiator — direct tool wrapping a perturbation-prediction model, validated against VCC's public task |
| External validation / benchmark | None surveyed publish results against an independent field-wide benchmark | Some evaluated on scBench (general task accuracy), not perturbation-specific | Validated against Arc Institute's Virtual Cell Challenge dataset/metrics — a field-recognized, third-party benchmark |
| Session memory across conversation | No — stateless GUI sessions | Limited — CellVoyager uses paper/context retrieval, not ongoing-analysis memory | Yes — inherited from OpenClaw's session/memory layer |
| Deployment model | Cloud SaaS (multi-tenant, often enterprise-priced) | Research prototypes / open-source repos, not deployed as internal lab tools | Internal tool, tied to one partner lab (Biopunk Labs), no multi-tenant overhead |
| Demonstrated reliability on messy real-world data | Generally solid (mature, purpose-built pipelines) | Mixed — scBench found frontier-model agents score only 29-53% accuracy on real-world scRNA-seq tasks | Unproven — this is the real execution risk BioClaw must budget for (self-check/evaluator mechanisms in v1.x) |

## Virtual Cell Challenge — Task Format, Requirements, and What BioClaw Needs to Benchmark

**Confidence: HIGH** (Arc Institute official pages, Hugging Face primer written with Arc's cooperation, Cell journal paper).

### Task format

- **Core task ("context generalization"):** given the unperturbed (control/non-targeting) transcriptome of a cell population and a specified gene to knock down via CRISPR interference (CRISPRi), predict the resulting perturbed transcriptome.
- **2025 (inaugural) format:** training data provided (~220K cells: ~38K unperturbed controls + ~182K perturbed across multiple targets/cell types in H1 hESC, 300 CRISPRi perturbations, 10x Genomics Flex chemistry); final test set released ~1 week before the submission deadline; scored against new Arc-generated experimental data the model never trained on.
- **2026 format (current/active challenge, timeline below):** **zero-shot** — no training set provided at all. Participants must predict CRISPRi knockdown responses in six cell lines never seen perturbed, using only (a) the unperturbed baseline expression of those cell lines and (b) a list of target genes. This is a materially harder bar (cross-cell-line generalization, not just held-out perturbations within a known cell type) — Arc's own framing: address "practical biological scenarios where experimentation is expensive or infeasible."
- Data generation: Perturb-seq across six cell lines from different tissues, CRISPRi, 10x Flex profiling, Ultima UG100 sequencing. Three cell lines support a public validation/leaderboard; three are held out for final scoring.

### Inputs / outputs

- **Input:** sparse transcriptome count matrix for control (non-targeting guide) cells; one-hot/list encoding of which gene(s) to knock down; optionally covariate-matched basal profiles.
- **Output:** predicted post-perturbation transcriptome (full gene expression profile per virtual perturbed cell/pseudo-bulk).

### Submission requirements

- Any modeling strategy is permitted; participants may train on any data (public perturbation datasets, proprietary data, or none at all for zero-shot approaches).
- Individuals, academic labs, companies, and independent organizations are all eligible.
- 2025 reference implementation integrated with Hugging Face `transformers`; Arc published a baseline model (**STATE**: a State Embedding model using ESM2-derived gene embeddings + a State Transition Llama-backbone transformer trained with Maximum Mean Discrepancy loss) and a Colab notebook walking through training/inference — a strong reference for what a credible submission pipeline looks like end-to-end.
- 2026 timeline: validation data/submissions open Aug 20; final (held-out) test set released Oct 22; submission deadline Nov 5, 11:59pm UTC; winners announced mid-late November.

### Evaluation metrics ("what good looks like")

Three original metrics (2025), now expanded to a six-metric aggregate panel for 2026 because no single metric captured overall quality:

1. **Perturbation Discrimination Score (PDS)** — measures whether predicted perturbation effects remain *distinguishable from each other* (relative ranking accuracy across different perturbations), not just individually accurate.
2. **Differential Expression Score (DES)** — recovers the correct set of DE genes: Wilcoxon rank-sum test between perturbed/control on both predicted and ground-truth data, genes called significant at FDR ≤ 0.05 (Benjamini-Hochberg), then compares overlap/ranking by log-fold-change. Notably, this is the *same statistical test* (Wilcoxon rank-sum) already table-stakes in any scanpy-based DE tool — meaning BioClaw's own DE tool layer is directly reusable as part of the eval harness.
3. **Mean Absolute Error (MAE)** — direct gene-level numeric prediction accuracy across the transcriptome.
4-6. Additional metrics from Arc's STATE model methodology, added for the expanded 2025 "Generalist" category and formalized into the 2026 six-metric panel.

Scoring: each metric normalized against a perturbation-mean naive baseline (to measure gain over "predict the average perturbed profile"); composite score = mean of normalized metrics; minimum thresholds per metric prevent gaming one metric at the expense of others.

**What "good" looked like in 2025:** the field-wide finding (worth internalizing) was that *purely AI/deep-learning approaches did not consistently beat statistical baselines*, and "almost all models performed worse than baseline on MAE." Winning teams (BioMap's xTrimoSCPerturb, XLearning Lab, TransPert, and Generalist-prize winner Altos Labs) succeeded with **hybrid strategies**: combining deep learning with classical statistical features, ESM-2 protein embeddings, pseudo-bulk (not noisy single-cell-level) representations, and multi-metric-aware loss design — not with pure end-to-end neural prediction. This is a directly actionable finding for BioClaw's own perturbation tool design: a naive "just call a neural FM and take its output" tool is likely to underperform a hybrid statistical+FM approach on this specific benchmark.

### What BioClaw needs to build to credibly benchmark against it

1. **Perturbation-prediction tool** that accepts control profiles + target gene(s) and outputs a predicted transcriptome — already scoped in PROJECT.md.
2. **VCC dataset ingest path** — the public dataset uses 10x Flex chemistry; confirm BioClaw's ingest pipeline (currently scoped around standard 10x `.mtx`/`.h5`) handles Flex output without a separate ingest branch.
3. **Eval harness implementing the three core metrics** (PDS, DES, MAE) exactly as Arc defines them — DES is directly reusable from BioClaw's own DE tool (same Wilcoxon test), so this is lower-cost than it first appears; PDS and MAE need standalone scoring code, straightforward to implement from the published formulas.
4. **A naive perturbation-mean baseline** to normalize against — required for the composite score to be meaningful, and useful independently as a sanity floor ("is our tool at least beating 'predict the average'?").
5. **Awareness that the 2026 task is zero-shot/cross-cell-line** — if BioClaw's perturbation tool is validated only within a single known cell type (the likely first Biopunk Labs use case), it should not be expected to perform well against the current VCC's cross-context generalization bar without explicit work toward that. This is worth flagging explicitly to Elliot/roadmap as a scope decision: benchmark against the *task format and metrics* (achievable, valuable) vs. benchmark competitively against the *current leaderboard* (a much higher, possibly out-of-scope bar per PROJECT.md's own "not a competition entry" framing).
6. Do **not** need: Hugging Face `transformers` packaging, competition-grade submission tooling, or optimization against the composite leaderboard score — those are only required for an actual competition entry, which PROJECT.md explicitly excludes from v1 scope.

## Sources

**Virtual Cell Challenge (HIGH confidence — official/primary sources):**
- [The 2026 Virtual Cell Challenge — Arc Institute](https://arcinstitute.org/news/virtual-cell-challenge-2026)
- [Arc Institute launches its inaugural "virtual cell" competition — Arc Institute](https://arcinstitute.org/news/virtual-cell-challenge-2025)
- [Virtual Cell Challenge 2025 Wrap-Up: Winners and Reflections — Arc Institute](https://arcinstitute.org/news/virtual-cell-challenge-2025-wrap-up)
- [Virtual Cell Challenge: Toward a Turing test for the virtual cell — Cell](https://www.cell.com/cell/fulltext/S0092-8674(25)00675-0)
- [Arc Virtual Cell Challenge: A Primer — Hugging Face](https://huggingface.co/blog/virtual-cell-challenge)
- [Behind the Data of the Virtual Cell Challenge — Arc Institute](https://arcinstitute.org/news/behind-the-data-virtual-cell-challenge)
- [NeurIPS 2025: Altos Labs Wins Generalist Prize — GEN Engineering News](https://www.genengnews.com/topics/artificial-intelligence/neurips-2025-altos-labs-wins-generalist-prize-at-arcs-virtual-cell-challenge/)

**Commercial single-cell platforms (MEDIUM confidence — vendor pages, cross-referenced comparison posts):**
- [CZ CELLxGENE Discover — Nucleic Acids Research / NCBI](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC11701654/)
- [Best scRNA-seq Analysis Tools in 2026: Compared — nygen.io](https://www.nygen.io/resources/blog/single-cell-scrna-seq-multi-omics-data-analysis-tools)
- [GUI commercial software for 10x single cell gene expression analysis — Biostars](https://www.biostars.org/p/9615355/)
- [Best single-cell RNA-sequencing data analysis tools — Biomage/Cellenics](https://www.biomage.net/blog/best-single-cell-rna-sequencing-data-analysis-tools-in-2024)

**Emerging agentic bioinformatics tools (MEDIUM-LOW confidence — active preprint literature, verify before locking architecture decisions):**
- [LLM4Cell: A Survey of Large Language and Agentic Models for Single-Cell Biology — arXiv](https://arxiv.org/html/2510.07793v2)
- [CellAgent: LLM-Driven Multi-Agent Framework for Natural Language-Based Single-Cell Analysis — bioRxiv](https://www.biorxiv.org/content/10.1101/2024.05.13.593861v4)
- [CellVoyager: AI CompBio agent generates new insights by autonomously analyzing biological data — Nature Methods](https://www.nature.com/articles/s41592-026-03029-6)
- [An Agentic AI Framework for Ingestion and Standardization of Single-Cell RNA-seq Data Analysis — bioRxiv](https://www.biorxiv.org/content/10.1101/2025.07.31.667880v1.full)
- [scBench: Evaluating AI Agents on Single-Cell RNA-seq Analysis — arXiv](https://arxiv.org/abs/2602.09063) / [GitHub](https://github.com/latchbio/scbench) / [blog summary](https://blog.latch.bio/p/scbench-can-ai-agents-analyze-real)
- [Empowering AI data scientists using a multi-agent LLM framework — Nature Biomedical Engineering](https://www.nature.com/articles/s41551-026-01634-6) (Biomni)

---
*Feature research for: single-cell transcriptomics agentic analysis tools*
*Researched: 2026-09-03*
