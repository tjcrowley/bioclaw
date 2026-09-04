# Pitfalls Research

**Domain:** Agentic LLM harness over single-cell bioinformatics + bio foundation models (BioClaw)
**Researched:** 2026-09-03
**Confidence:** MEDIUM-HIGH (mix of peer-reviewed/official sources and verified WebSearch findings; see per-pitfall notes)

## Critical Pitfalls

### Pitfall 1: Silent raw-count corruption (`.X` vs `.raw` vs `.layers`)

**What goes wrong:**
Downstream tools (scanpy differential expression, most bio FM tokenizers including scGPT/Geneformer) require raw integer counts, but a normalization step overwrites `adata.X` in place with log-normalized floats and there is no raw data left to recover. Worse, the common "safety" pattern `adata.raw = adata` does **not** protect the data — `.raw` stores a reference, not a copy, so a later `sc.pp.normalize_total()` / `sc.pp.log1p()` call silently mutates `adata.raw` too. An agent that runs a normalization tool and then later calls a bio FM tool expecting raw counts will get counts that look valid (positive floats) but are actually log-normalized, producing plausible-looking but wrong embeddings/predictions with no error thrown.

**Why it happens:**
AnnData's `.raw` attribute is a reference-semantics footgun, not a copy-on-write snapshot; this is a known scverse gotcha, not a scanpy bug (confirmed via scverse GitHub issue #3073 and scverse Discourse). It's especially dangerous in an agentic system because the agent composes tool calls in an order a human wouldn't necessarily think to double-check — e.g., normalize → cluster → call scGPT tool, where step 3 silently receives corrupted input.

**How to avoid:**
- Canonical ingest tool must persist raw counts to an explicit, immutable `adata.layers['counts']` (a real copy) at load time, before any normalization ever touches `.X`.
- Every downstream tool (FM wrapper, DE tool) must declare and validate which layer it consumes (e.g., assert non-negative integers before treating input as counts) and fail loudly, not silently proceed, if the wrong layer is passed.
- Never rely on `adata.raw` as the source of truth in the ingest pipeline design.

**Warning signs:**
- Bio FM tool calls succeed but downstream cell-type annotations are noisy/inconsistent across seemingly similar runs.
- QC/DE reports show non-integer values where counts were expected, or negative values slip through unflagged.

**Phase to address:**
Phase covering the ingest/QC pipeline (canonical `.h5ad` normalization) — must define the layer contract before any FM tool wrapper phase is built on top of it.

---

### Pitfall 2: Batch-correction methods "fix" the plot but corrupt the biology

**What goes wrong:**
Popular batch-correction methods (MNN, scVI, LIGER, Harmony, etc.) are frequently applied by default whenever multiple samples/batches are combined, because uncorrected UMAPs look messy and batch-separated. But a 2025 peer-reviewed benchmark (PMC) found several widely used batch-correction methods are "poorly calibrated" — they alter the data considerably and can suppress or fabricate biological signal (including removing genuine perturbation effects) in the name of visual batch mixing. This is directly dangerous for BioClaw's perturbation-response use case: over-correcting batch effects between control and perturbed samples can erase the very signal the agent is trying to predict/report on.

**Why it happens:**
Batch correction is usually treated as a mandatory, automatic preprocessing checkbox rather than a modeling choice with a bias-variance tradeoff. An agent that "just runs the standard pipeline" without surfacing this choice to the researcher inherits this default-application trap at scale, silently, across every dataset it touches.

**How to avoid:**
- Do not hard-code batch correction as an unconditional step in the ingest pipeline. Make it an explicit, logged decision the agent takes (and reports) only when batches are actually present and confounded with the biological variable of interest.
- When correction is applied, the agent's interpretation layer should flag that correction occurred and which method, so a researcher can audit whether real signal (e.g., perturbation response) was suppressed.
- For the perturbation-prediction wedge specifically, prefer methods/workflows validated against the Virtual Cell Challenge task design (control vs. perturbed within the same batch/plate) over generic batch-correction defaults.

**Warning signs:**
- Perturbation effect sizes shrink or disappear after adding a "standard" preprocessing step.
- UMAP looks well-mixed by batch but DE results between control/perturbed groups become weaker than in per-batch analysis.

**Phase to address:**
Ingest/QC pipeline phase (decision must be explicit and logged) and the perturbation-model tool phase (validate that correction choices don't erase the signal being predicted).

---

### Pitfall 3: Doublet/QC filtering thresholds applied as fixed global defaults

**What goes wrong:**
QC steps (mito %, doublet score, min-count filtering) are listed as simple boxes to check, but there is no universal threshold — doublet scores are relative and dataset-dependent, and naive global thresholds ("kill everything above X% mito", "drop anything scoring above Y as doublet") systematically remove real biology. Documented failure modes: cell types with legitimately high mito fraction (e.g., cardiomyocytes) get wrongly excluded; cell types with naturally low transcript counts (e.g., microglia) get wrongly excluded as "low quality"; doublet detectors specifically struggle with continuous/transitional cell states and misclassify them as doublets.

**Why it happens:**
QC is treated as a fixed numeric-threshold problem because that's easy to encode as a tool parameter default. An agent that always applies "the standard thresholds" (e.g., mito < 20%, min genes > 200) without adapting to the tissue/cell-type context in the actual dataset will quietly bias every analysis toward whatever cell types survive those defaults.

**How to avoid:**
- QC tool should compute and surface per-cluster/per-cell-type distributions of QC metrics before hard filtering, not apply a single global cutoff blind to what's being thrown away.
- Best practice from the field (10x Genomics QC guidance, OSCA book): treat high doublet score as "suspect, inspect with cluster context" rather than an automatic drop; recommend the agent flag cells for review rather than silently deleting them in a fully automated agentic run, at least in early phases.
- Log exactly what fraction of cells / which clusters were removed at each QC step, so the researcher (and later, the agent's own interpretation step) can audit for over-filtering.

**Warning signs:**
- A specific cell type is systematically absent from an annotated dataset compared to what's biologically expected for the tissue.
- QC step removes >30-40% of cells with no per-cluster breakdown available to explain why.

**Phase to address:**
Ingest/QC pipeline phase — QC tool design should expose thresholds as inspectable/adjustable parameters with default warnings, not silent hard-coded cutoffs.

---

### Pitfall 4: Bio foundation models underperform trivial baselines — and the agent won't know it

**What goes wrong:**
Multiple 2024-2025 peer-reviewed benchmarks found scGPT and Geneformer, used zero-shot (no fine-tuning), frequently **underperform simple baselines** — e.g., a Nature Methods 2025 paper ("Deep-learning-based gene perturbation effect prediction does not yet outperform simple linear baselines") and a Genome Biology 2025 zero-shot evaluation both found scGPT does not beat mean/averaged-bin prediction, and simple models using biological prior knowledge outperform scGPT by a large margin on several tasks. This directly undercuts BioClaw's core premise (call scGPT/Geneformer as a tool and trust the output) if the agent has no mechanism to detect or communicate that, for a given task, the FM is worse than a trivial statistical baseline.

**Why it happens:**
Bio FMs are marketed and often used as universal embeddings/predictors; teams wire them in as a black-box tool call without running a baseline comparison, because baselines aren't "the interesting model." An agentic harness makes this worse — the agent will confidently report FM output as *the* answer unless explicitly instructed to sanity-check against a baseline.

**How to avoid:**
- Build a cheap statistical baseline (e.g., mean-of-controls prediction for perturbation response, marker-gene correlation for cell typing) as a first-class tool alongside every FM tool, and have the agent's interpretation step compare FM output to baseline before presenting a result as reliable.
- Treat "FM says X" as a hypothesis, not ground truth, in the interpretation/reporting layer — explicitly surface disagreement between FM and baseline to the researcher rather than picking one silently.
- This is directly relevant to the Virtual Cell Challenge evaluation itself (see Pitfall 7) — VCC 2025 organizers confirmed the same finding at competition scale.

**Warning signs:**
- FM tool output is presented without any comparison metric or confidence indicator.
- No baseline/control tool exists in the tool layer at all.

**Phase to address:**
Bio FM tool-wrapper phase (build baseline alongside FM tool from day one) and the interpretation/reporting phase (comparison must be part of the answer, not an afterthought).

---

### Pitfall 5: LLM hallucinates or overclaims when interpreting quantitative model output

**What goes wrong:**
The core BioClaw value prop — "researcher gets an interpreted answer, not raw model output" — is exactly where hallucination risk concentrates. LLMs generate fluent, plausible-sounding scientific narrative even when the underlying data is noisy, borderline, or genuinely ambiguous, and 2025 surveys of LLM agent hallucination note these errors can occur at any pipeline stage (perception, reasoning, tool-result summarization) and compound across multi-step agent chains. In a biology context this means: the agent may state a cell population "shows the strongest response to compound X" when the underlying effect size is within noise, may misattribute a differentially expressed gene list to the wrong perturbation, or may round an uncertain FM prediction into a confident causal claim.

**Why it happens:**
LLMs are optimized to produce coherent natural-language answers; they have no built-in mechanism to represent "I'm not sure" proportional to actual statistical uncertainty in the upstream tool output unless explicitly forced to carry and surface that uncertainty through the pipeline.

**How to avoid:**
- Every scientific tool in the chain (QC, DE, FM call) must return structured, machine-readable confidence/uncertainty alongside point estimates (e.g., DE p-values/FDR, FM prediction variance where available, baseline-vs-FM agreement from Pitfall 4) — not just a summary number for the LLM to narrate.
- The interpretation layer's system prompt/tool contract should require the agent to cite specific numeric outputs (gene names, p-values, effect sizes) it is summarizing, and explicitly flag when evidence is weak/borderline rather than smoothing it into a confident sentence.
- Never let the agent's final answer be the only artifact — always attach or link the underlying structured result (plot, table, DE gene list) so a researcher can verify the claim, not just trust the sentence.

**Warning signs:**
- Agent answers read confidently even for genuinely ambiguous/underpowered analyses.
- No traceability from a natural-language claim in the final answer back to specific numeric tool output.

**Phase to address:**
The natural-language interpretation/reporting phase (the "researcher gets an interpreted answer" milestone) — this is the highest-risk phase in the whole roadmap and should not ship without a verification/traceability mechanism.

---

### Pitfall 6: Tool-call hallucination — agent selects wrong tool, malforms params, or "simulates" instead of calling

**What goes wrong:**
2025 research on tool-integrated LLM agents documents a specific failure mode called "tool bypass": under uncertainty or when a tool call is expensive/slow (e.g., a bio FM inference call), the agent generates a plausible-looking simulated result instead of actually invoking the tool — producing fabricated numbers that look like real model output. Separately, agents commonly hallucinate wrong tool selection, empty/malformed parameters, or wrong parameter values when the tool surface is large or ambiguous (e.g., multiple similarly-named scanpy-wrapped analysis tools).

**Why it happens:**
LLMs pattern-match on what a tool call and its output "usually look like" from training data; when a real bio FM call is slow, resource-constrained, or the tool schema is underspecified, the model can produce a syntactically valid-looking response without a genuine dependency on the actual tool execution, especially if tool call/response formatting isn't strictly enforced and validated.

**How to avoid:**
- Strict tool-call validation: reject and retry on malformed parameters; log every actual tool invocation with request/response hashes so a "simulated" answer with no corresponding execution log is detectable.
- Keep the bio FM/analysis tool surface small, typed, and unambiguous in this MVP (per PROJECT.md's already-scoped tool list) rather than exposing many overlapping variants that increase tool-selection error.
- Add an execution-trace check in the agent loop: before presenting results, verify that a claimed tool output corresponds to a real, logged tool call with matching output hash/id — not just text in the model's context.

**Warning signs:**
- Reported numeric results that don't match any entry in the tool-call execution log.
- Tool call failures silently followed by an agent answer that proceeds as if the call succeeded.

**Phase to address:**
Agent orchestration/tool-routing phase — build execution logging and result-provenance checks into the tool-calling loop itself, not bolted on later.

---

### Pitfall 7: Virtual Cell Challenge metrics are easy to game/misread if used naively as a validation target

**What goes wrong:**
Arc Institute's own 2025 wrap-up (official post-mortem) identified concrete metric gotchas directly relevant to using VCC as BioClaw's validation benchmark:
- **MAE is unreliable**: "almost all models performed worse than baseline on MAE" because of technical noise sensitivity — a naive reading of MAE as "the accuracy score" is misleading; competitors effectively had to ignore it.
- **PDS (Perturbation Discrimination Score) is scale-sensitive**: it's L1-based and asymptotically behaves like sign-based cosine similarity as prediction magnitude grows — meaning getting the *direction* of an effect right matters more than exact magnitude, which is counterintuitive if you assume a distance-based metric rewards precise quantitative accuracy.
- **Pure deep-learning approaches did not consistently beat statistical baselines** on DES and MAE — winning teams used hybrid statistical+neural approaches, reinforcing Pitfall 4.
- **The task deliberately uses a distributional shift** (H1 hESCs, a cell context absent from common pretraining corpora like K562/A375/Tahoe-100M) specifically to penalize memorization — a model/tool that looks good on more "typical" cell lines may fail on the actual VCC-style held-out evaluation.

**Why it happens:**
Teams (and any project citing VCC as a benchmark, including BioClaw per PROJECT.md) risk treating "we ran the VCC task format" as sufficient validation without accounting for these known metric quirks, or optimizing for one metric (e.g., raw MAE minimization) at the expense of the metrics that actually mattered in the competition (PDS, DES).

**How to avoid:**
- When BioClaw evaluates its perturbation-prediction tool against the VCC public dataset/task format, report all three official metrics (PDS, DES, MAE) with the known caveat that MAE alone is not a reliable success signal, per Arc's own findings.
- Build the statistical baseline comparison (Pitfall 4) directly into this validation step — compare BioClaw's agent-orchestrated prediction against both a naive baseline and, if feasible, publicly reported 2025 competition baseline numbers, not just an absolute score in isolation.
- Do not evaluate only on cell lines/perturbations similar to training data; explicitly test on the kind of distributional shift the VCC's H1 hESC design intended, to know if the pipeline is memorizing or generalizing.

**Warning signs:**
- Validation report cites only MAE as "the accuracy number."
- No baseline-vs-model comparison in the benchmark write-up.
- Testing only in-distribution cell types/perturbations rather than a held-out shift.

**Phase to address:**
The VCC benchmark-validation phase (explicit "Active" requirement in PROJECT.md) — design the evaluation harness around all three metrics and a baseline comparison from the start, not as an afterthought after the pipeline exists.

---

### Pitfall 8: Cell-type annotation label mismatch across reference atlases/ontologies

**What goes wrong:**
Automated cell-type annotation (via FM embeddings or marker-gene reference mapping) depends on a reference atlas whose cell-type vocabulary may not match the researcher's expected labels — different atlases use different granularity (e.g., "T cell" vs. "CD8+ effector memory T cell"), different platforms/technologies between query and reference data prevent accurate mapping, and clustering-based reference mapping often fails to separate closely related subtypes (e.g., immune cell subsets). If BioClaw's agent reports a cell-type label without surfacing which reference/ontology it came from or its confidence, the researcher may unknowingly get an annotation that's technically "a match" but biologically the wrong resolution or wrong tissue context for Biopunk Labs' actual samples.

**Why it happens:**
Off-the-shelf FM cell-typing tools (scGPT annotation head, reference-mapping tools like SingleR/popV) ship with a default reference; wiring the tool in without exposing reference choice/provenance to the agent's output makes annotation look more authoritative than it is.

**How to avoid:**
- Cell-type annotation tool output must include the reference atlas/ontology used, the confidence/similarity score, and ideally the Cell Ontology ID, not just a free-text label string.
- Interpretation layer should flag low-confidence annotations distinctly rather than presenting them with the same tone as high-confidence ones.
- Given Biopunk Labs is the first real user, validate the annotation tool against a known ground-truth or manually-curated small dataset from their own wet lab work before trusting it on novel data.

**Warning signs:**
- Cell-type labels reported with no reference/version metadata.
- Same cell population gets different labels across re-runs of the same tool without explanation.

**Phase to address:**
Bio FM tool-wrapper phase (cell-type annotation tool design) and interpretation/reporting phase (confidence must be visible in the final answer).

---

## Technical Debt Patterns

| Shortcut | Immediate Benefit | Long-term Cost | When Acceptable |
|----------|-------------------|-----------------|-----------------|
| Hard-code batch correction and QC thresholds as pipeline defaults instead of exposing/logging them | Faster first working demo | Silently biases every dataset the same way; hard to retrofit auditability | MVP demo on one known dataset only, never for Biopunk Labs' real ongoing use |
| Skip building a statistical baseline tool alongside the FM tool | Less to build for MVP | No way to tell if the FM is even better than a trivial predictor (Pitfall 4) | Never — this is cheap to build and central to credibility |
| Let the agent's natural-language answer be the only output artifact (no linked structured data) | Simpler UX for the demo | Impossible to audit hallucinated claims; researcher can't verify | Only for a first internal throwaway prototype, never past that |
| Self-host scGPT/Geneformer on whatever GPU is available without capacity planning | Skip infra decision now | OOM failures or silent truncation on larger datasets once real Biopunk Labs data arrives | Acceptable only while testing on small public datasets (<50k cells) |
| Treat VCC benchmark validation as a one-time check instead of a repeatable regression test | Faster to claim "validated against VCC" | No way to detect regressions as the pipeline/tools evolve | Never for anything beyond a single demo screenshot |

## Integration Gotchas

| Integration | Common Mistake | Correct Approach |
|-------------|-----------------|-------------------|
| scGPT / Geneformer (HuggingFace-hosted or self-hosted checkpoints) | Assuming zero-shot output is reliable without task-specific fine-tuning or baseline comparison | Always pair FM tool calls with a baseline comparison (Pitfall 4); treat zero-shot output as a hypothesis |
| AnnData `.raw` attribute | Using `adata.raw = adata` assuming it snapshots counts | Use `adata.layers['counts'] = adata.X.copy()` for a real, independent copy |
| 10x Genomics `.mtx`/`.h5` ingest | Assuming all uploaded files are already filtered/cell-called correctly by upstream instrument software | Re-run/verify cell calling and basic sanity checks (barcode counts, gene counts) rather than trusting the raw vendor output blindly |
| Virtual Cell Challenge public dataset | Using only the metric(s) that make the pipeline look best (e.g., reporting only DES) | Report all three official metrics (PDS, DES, MAE) with documented caveats per Arc's own findings |
| Claude/agentic tool-calling loop | Not logging/validating that a claimed tool call actually executed | Execution-trace validation before presenting any tool-derived result (Pitfall 6) |

## Performance Traps

| Trap | Symptoms | Prevention | When It Breaks |
|------|----------|------------|-----------------|
| Loading full `.h5ad` into memory per agent tool call | Slow/failing tool calls as dataset size grows | Use backed mode / chunked access (`anndata` backed=`r`) for large datasets; don't reload full object per tool invocation | Datasets above a few hundred thousand cells or when running on modest self-hosted hardware |
| Re-running FM inference from scratch on every conversational turn | Slow, expensive repeated GPU calls for the "same" dataset the researcher already asked about | Cache FM embeddings/predictions keyed to dataset version + params in the session/memory layer | As soon as a multi-turn conversation revisits the same dataset — which is the explicit MVP requirement |
| No dataset versioning across a multi-turn session | Agent gives different answers to the same question because the "current dataset" silently changed (re-QC'd, re-filtered) mid-conversation | Version every canonical dataset artifact (content hash or explicit version tag) and have session memory reference the exact version, not just a dataset name | As soon as more than one processing run of the same source data exists |

## Security Mistakes

| Mistake | Risk | Prevention |
|---------|------|------------|
| Agent has unrestricted code-execution/filesystem access while processing wet-lab data | Prompt injection or a malformed tool call could exfiltrate or corrupt proprietary Biopunk Labs research data; container escape via crafted inputs (documented CVE pattern in agent sandboxes, e.g., CVE-2024-21626-style Dockerfile/WORKDIR escapes) | Run all code-execution tool calls in a resource-limited (cgroup-enforced, not just app-level) sandbox with no default network egress and read-only mounts except for scoped dataset directories |
| Treating internal-tool status as "no security needed yet" | Even though PROJECT.md scopes this as internal-only with no auth/multi-tenant work, unrestricted agent tool access to a researcher's real data is still a risk within a single-user context | Apply the same tool-execution sandboxing discipline even for a single internal user — the risk is agent error/hallucination, not just external attackers |
| No provenance/audit trail for what data an FM tool call sent externally (if using hosted inference rather than self-hosted) | Wet-lab data (potentially pre-publication, IP-sensitive to Biopunk Labs) could leave the local environment without anyone noticing | If hosted inference is used, explicitly log and disclose every external API call boundary in the tool contract; default to self-hosting for anything not yet cleared for external transfer |

## UX Pitfalls

| Pitfall | User Impact | Better Approach |
|---------|-------------|-------------------|
| Presenting FM/agent output as a single confident sentence with no uncertainty indicator | Researcher over-trusts a borderline or wrong result (Pitfall 5) | Always surface effect size + confidence/uncertainty alongside any interpreted claim |
| No link from a natural-language answer back to the underlying data/plot/table | Researcher can't independently verify or reuse the analysis, defeating the point of replacing manual scripting | Every answer includes or links the structured artifact (DE table, UMAP, prediction matrix) it's summarizing |
| Silent QC filtering with no visibility into what was removed | Researcher unknowingly loses a cell population relevant to their question (Pitfall 3) | QC step always reports what/how much was filtered and why, even in an automated agent run |
| Agent picks a default reference/model version without asking or disclosing it | Results aren't reproducible across sessions if defaults change later | Every tool call output should record and display which model/reference version was used |

## "Looks Done But Isn't" Checklist

- [ ] **Ingest pipeline:** Often missing an immutable raw-counts layer — verify `adata.layers['counts']` exists and is never touched by normalization steps.
- [ ] **QC step:** Often missing per-cluster/per-cell-type breakdown of what was filtered — verify a filtering report exists, not just a final filtered object.
- [ ] **Bio FM tool wrapper:** Often missing a baseline comparison — verify a non-FM baseline tool exists and its output is compared in every FM-derived answer.
- [ ] **Agent interpretation layer:** Often missing traceability from natural-language claims to underlying numeric tool output — verify every claim in a final answer can be traced to a logged tool call result.
- [ ] **Tool-calling loop:** Often missing execution-trace validation — verify there's no path for the agent to present a result without a corresponding logged tool invocation.
- [ ] **Session/memory layer:** Often missing dataset versioning — verify "the dataset we're discussing" resolves to a specific immutable version, not a mutable name.
- [ ] **VCC benchmark validation:** Often missing multi-metric reporting — verify PDS, DES, and MAE are all reported with baseline comparison, not a single cherry-picked metric.

## Recovery Strategies

| Pitfall | Recovery Cost | Recovery Steps |
|---------|-----------------|------------------|
| Raw counts silently corrupted (Pitfall 1) | LOW-MEDIUM | Re-ingest from original `.mtx`/`.h5` source files if retained; add layer-contract validation going forward |
| Over-aggressive batch correction erased real signal (Pitfall 2) | MEDIUM | Re-run analysis without correction or with a milder method on the same raw-count layer; compare effect sizes before/after |
| Agent presented a hallucinated/unverifiable claim (Pitfall 5/6) | MEDIUM-HIGH | Retrofit execution-trace logging and require re-verification of any prior "final answers" given without a traceable tool-call log |
| VCC validation only reported misleading metric (Pitfall 7) | LOW | Re-run evaluation harness reporting all three metrics plus baseline comparison; no data reprocessing needed if raw predictions were saved |
| Wrong/low-confidence cell-type labels shipped without disclosure (Pitfall 8) | MEDIUM | Re-run annotation tool with confidence/reference metadata surfaced; flag prior outputs as needing review |

## Pitfall-to-Phase Mapping

| Pitfall | Prevention Phase | Verification |
|---------|-------------------|----------------|
| Silent raw-count corruption (#1) | Ingest/QC pipeline phase | Automated test: normalize a dataset, confirm `layers['counts']` unchanged |
| Batch correction erasing signal (#2) | Ingest/QC pipeline + perturbation-model tool phase | Compare DE effect sizes pre/post correction on a known perturbation dataset |
| QC over-filtering (#3) | Ingest/QC pipeline phase | QC report includes per-cluster filtering breakdown reviewed before shipping |
| FM underperforming baseline undetected (#4) | Bio FM tool-wrapper phase | Baseline tool exists and its output appears in every FM tool test/demo |
| LLM hallucinated interpretation (#5) | Interpretation/reporting phase | Every demo answer traces to a specific logged tool-call result; spot-check with adversarial ambiguous queries |
| Tool-call hallucination / bypass (#6) | Agent orchestration/tool-routing phase | Execution-trace audit: no presented result lacks a matching tool-call log entry |
| VCC metric misuse (#7) | VCC benchmark-validation phase | Validation report includes PDS, DES, MAE, and baseline comparison — checked against Arc's 2025 wrap-up caveats |
| Cell-type/ontology mismatch (#8) | Bio FM tool-wrapper phase | Annotation tool output includes reference/version/confidence fields, tested against a known-label dataset |

## Sources

- [Batch correction methods used in single-cell RNA sequencing analyses are often poorly calibrated (PMC, 2025)](https://pmc.ncbi.nlm.nih.gov/articles/PMC12315870/) — HIGH confidence, peer-reviewed
- [Performance Assessment and Selection of Normalization Procedures for Single-Cell RNA-Seq (PMC/ScienceDirect)](https://pmc.ncbi.nlm.nih.gov/articles/PMC6544759/) — HIGH confidence, peer-reviewed
- [Normalized data found instead of raw counts (scverse Discourse)](https://discourse.scverse.org/t/normalized-data-found-instead-of-raw-counts/2163) — MEDIUM confidence, official community forum
- [Adata.raw gets modified upon log normalization of adata · Issue #3073 (scverse/scanpy GitHub)](https://github.com/scverse/scanpy/issues/3073) — HIGH confidence, official repo issue
- [Chapter 8 Doublet detection — Advanced Single-Cell Analysis with Bioconductor](https://bioconductor.org/books/3.15/OSCA.advanced/doublet-detection.html) — HIGH confidence, official reference text
- [Common Considerations for Quality Control Filters for Single Cell RNA-seq Data (10x Genomics)](https://www.10xgenomics.com/analysis-guides/common-considerations-for-quality-control-filters-for-single-cell-rna-seq-data) — HIGH confidence, official vendor guidance
- [Deep-learning-based gene perturbation effect prediction does not yet outperform simple linear baselines (Nature Methods, 2025)](https://www.nature.com/articles/s41592-025-02772-6) — HIGH confidence, peer-reviewed
- [Zero-shot evaluation reveals limitations of single-cell foundation models (Genome Biology, 2025)](https://link.springer.com/article/10.1186/s13059-025-03574-x) — HIGH confidence, peer-reviewed
- [Virtual Cell Challenge 2025 Wrap-Up: Winners and Reflections (Arc Institute)](https://arcinstitute.org/news/virtual-cell-challenge-2025-wrap-up) — HIGH confidence, official organizer post-mortem
- [Virtual Cell Challenge: Toward a Turing test for the virtual cell (Cell, 2025)](https://www.cell.com/cell/fulltext/S0092-8674(25)00675-0) — HIGH confidence, peer-reviewed
- [Behind the Data of the Virtual Cell Challenge (Arc Institute)](https://arcinstitute.org/news/behind-the-data-virtual-cell-challenge) — HIGH confidence, official
- [The 2026 Virtual Cell Challenge (Arc Institute)](https://arcinstitute.org/news/virtual-cell-challenge-2026) — HIGH confidence, official
- [More Vulnerable than You Think: On the Stability of Tool-Integrated LLM Agents (arXiv, 2025)](https://arxiv.org/pdf/2506.21967) — MEDIUM confidence, preprint
- [LLM-based Agents Suffer from Hallucinations: A Survey of Taxonomy, Methods, and Directions (arXiv, 2025)](https://arxiv.org/pdf/2509.18970) — MEDIUM confidence, preprint survey
- [Large language model agents for biological intelligence across genomics, proteomics, spatial biology, and biomedicine (Briefings in Bioinformatics, Oxford)](https://academic.oup.com/bib/article/27/2/bbag110/8540361) — HIGH confidence, peer-reviewed
- [The Balkanization of Execution-Security Research for AI Coding Agents (arXiv, 2025)](https://arxiv.org/html/2607.05743v1) — MEDIUM confidence, preprint
- [Mapping single-cell data to reference atlases by transfer learning (Nature Biotechnology, 2021)](https://www.nature.com/articles/s41587-021-01001-7) — HIGH confidence, peer-reviewed
- [Consensus prediction of cell type labels in single-cell data with popV (PMC)](https://pmc.ncbi.nlm.nih.gov/articles/PMC11631762/) — HIGH confidence, peer-reviewed

---
*Pitfalls research for: BioClaw (agentic harness for bio foundation models, single-cell MVP)*
*Researched: 2026-09-03*
