# Feature Research

**Domain:** Single-cell biology agent — v1.2 real data + bio FM integration
**Researched:** 2026-09-16
**Confidence:** MEDIUM-HIGH overall. cellxgene-census API: HIGH (official CZI docs). scGPT output format: HIGH (official tutorial). Geneformer perturbation pipeline: HIGH (official readthedocs). Linear vs FM perturbation performance: MEDIUM (Nature Methods 2025 paywalled, accessed via search). Session/script UX: MEDIUM (inferred from analogous tools, reproducibility literature).

> **Note:** This file supersedes the v1.0/v1.1 feature research from 2026-09-03. The v1.0 research (table stakes ingest, QC, clustering, DE, FM annotation, perturbation, orchestration, VCC benchmark) is treated as COMPLETE. This document focuses on the seven new v1.2 features and what each actually requires from a researcher-UX and implementation perspective.

---

## Feature Landscape

### Table Stakes for v1.2 (Researchers Will Expect These to Work)

Features that, if absent or broken, make the v1.2 milestone feel incomplete to Biopunk Labs researchers.

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| cellxgene-census query with organism + tissue + assay filter | Researchers know CELLxGENE as the canonical public single-cell data portal; they expect to query it the way they do in a Python notebook (`obs_value_filter`), not hunt for .h5ad download links | MEDIUM | `cellxgene_census.get_anndata()` returns AnnData directly; must include `is_primary_data == True` to avoid duplicate-cell inflation; must probe cell count first before loading |
| Cell count warning before census load | Tissue queries routinely return 100K–500K+ cells; silent OOM is the failure mode; researchers expect "here's how many cells you're about to load" before commit | LOW | Two-step: run `census.get_obs()` for count first; load only if under threshold (~50K safe for in-memory); prompt researcher if larger |
| h5ad upload alongside MTX trio | `.h5ad` is the de-facto interchange format; every tool a Biopunk Labs researcher uses (scanpy, Seurat, CELLxGENE, scVI) produces it; refusing it means refusing every dataset not freshly off a 10x instrument | LOW | AnnData reads it natively; complexity is server-side multipart upload + obs/var shape validation; no new analysis logic |
| Cell type labels output from real scGPT inference | The v1.1 stub claimed to annotate; real inference must produce actual cell type label strings per cell, not "inference skipped" placeholders | MEDIUM | scGPT reference mapping: embed query cells → FAISS k-NN over reference atlas → majority vote label per cell; output lands in `adata.obs["cell_type"]`; no native per-cell probability from the model |
| Perturbation prediction from Geneformer (ranked gene list) | If Geneformer is offered as a second model option, it must produce an interpretable ranked output comparable to the linear model; researchers will immediately ask "which model should I trust?" | HIGH | 4-step pipeline: normalize + set Ensembl IDs → tokenize → InSilicoPerturber → InSilicoPerturberStats; output is ranked genes by cosine shift magnitude; pipeline requires disk I/O between steps |
| Session history visible when resuming | Researchers open sessions across days; seeing "Resuming…" and nothing else is not acceptable for a tool used in daily research; they need to orient in the conversation | LOW | Message rows already exist in SQLite from v1.1; requires `GET /sessions/{id}/messages` endpoint + frontend replay; no new storage needed |
| CSV download for cluster/DE/annotation results | Researchers copy results to papers, R scripts, Excel; a tool whose results cannot be exported is a dead end; this is the minimum "I got something out of this" affordance | LOW | Cluster assignments and DE tables are already DataFrames / AnnData .obs columns; serialize to CSV via a download endpoint |
| Reproducible scanpy script export | Reproducibility is a hard norm in single-cell biology; any researcher who ran an analysis expects to re-run it or share it with a collaborator; the script must be runnable end-to-end with the exact parameters used | MEDIUM | Requires the agent to log actual parameter values (not defaults) from each tool call during the session; generator fills them into a template script with version pins, data source, QC thresholds, clustering resolution, random seeds |
| Docker compose one-command deployment | Without this, Biopunk Labs researchers who are not DevOps cannot run the full stack; install friction kills adoption of an internal tool | MEDIUM | Compose: FastAPI backend + static frontend serving + optional GPU worker service (flagged profile) + volumes for SQLite + model checkpoints |

### Differentiators for v1.2

Features that elevate v1.2 above "we fixed a few things" and deliver researcher-visible value.

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| Vote-fraction confidence alongside scGPT annotation | Most annotation tools give labels without uncertainty; showing which cells have low-confidence calls lets researchers know where to distrust or hand-curate; differentiates from basic reference-mapping tools | LOW | scGPT k-NN vote fraction (8/10 neighbors agree → 0.8) is trivially computable; add to `obs["cell_type_confidence"]`; present in agent response as "8 of 10 reference neighbors agree" |
| Agent-mediated natural-language census query ("fetch lung cancer data from 10x 3' v3") | Researchers should not need to know `obs_value_filter` syntax; the agent translates their description into the correct filter string | LOW | Already within the LLM routing layer; requires well-designed tool schema with organism/tissue/assay/disease parameters; no new infrastructure |
| Geneformer vs. linear model comparison in agent response | Having two perturbation models side-by-side is only useful if the agent explicitly compares their top-ranked genes and notes agreement or disagreement; this is the VCC-differentiating narrative | MEDIUM | Requires both models to return the same output shape (ranked gene list + score); agent synthesis prompt must address the comparison; caveat: Nature Methods 2025 found FM models often do not outperform linear baselines on perturbation tasks — agent should present this context rather than overselling Geneformer |
| Session history replay with timestamps | Timestamps let researchers orient ("I ran this on Monday, the dataset has since been updated") and are standard in every research log; absence feels amateurish | LOW | Add `created_at` timestamp to message rows if not already stored; render inline in thread |

### Anti-Features (Over-Engineering to Avoid in v1.2)

| Feature | Why Requested | Why Problematic | Alternative |
|---------|---------------|-----------------|-------------|
| Full census sync / local mirror | "Faster queries, offline use" | Census is hundreds of GB; CZI docs state bandwidth is the primary bottleneck; syncing is a DevOps project | Stream slices via TileDB-SOMA remote access; recommend AWS us-west-2 deployment for speed-sensitive use |
| Real-time streaming of Geneformer perturbation progress | "Live progress feels responsive" | Geneformer writes results to pickle files in sequential batch phases (tokenize → perturb → stats); there is no streaming API | WebSocket phase-status messages ("tokenizing… inferring… computing statistics…") are sufficient; don't attempt token-level streaming |
| scGPT softmax confidence scores from the model itself | "More principled than vote fraction" | scGPT reference mapping uses FAISS k-NN + majority vote — there is no softmax classifier head on the reference path; extracting true probabilities requires fine-tuning a classifier head | Use k-NN vote fraction as proxy confidence; label it clearly; do not claim it is model-native probability |
| All four Geneformer perturb_type modes (delete/overexpress/inhibit/activate) | "Full model flexibility" | Each mode needs its own fine-tuned classifier configuration; exposing all four adds UX complexity for minimal v1.2 gain | Default to `delete` (matches CRISPRi knockdown, directly comparable to VCC task format); add other modes in v2 if researchers request them |
| Direct head-to-head scGPT vs Geneformer accuracy benchmark for annotation | "Which model is better?" | Standardized evaluation requires curated labeled test sets and controlled conditions — a research project, not a feature | Use models for their distinct strengths: scGPT for annotation, Geneformer for perturbation; note the distinct roles in agent responses |
| Lazy-loading / partial h5ad reads for files >2GB | "Support very large h5ad uploads" | Partial HDF5 reads require chunked access and custom AnnData reader paths; high effort for a rare edge case (Biopunk Labs datasets are expected <1GB for now) | Server-side 2GB upload limit (matching MapMyCells); clear error message; recommend census query for larger datasets |
| LLM-generated session summary on resume instead of full transcript | "Long sessions are too long to read" | LLM summarization adds token cost and latency on every resume; researchers doing reproducible work need the exact prior questions, not a paraphrase | Full transcript replay; show last 50 turns by default; offer "load earlier" affordance for very long sessions |

---

## Feature Dependencies for v1.2

```
[cellxgene-census query tool]
    └──requires──> cellxgene-census library in backend env
    └──requires──> cell-count probe step before load
    └──produces──> AnnData in session memory
                       └──feeds──> existing QC/clustering pipeline (v1.0)
                       └──feeds──> scGPT annotation
                       └──feeds──> Geneformer perturbation (if Ensembl IDs present)
                       └──feeds──> CSV export
                       └──feeds──> scanpy script export

[h5ad upload]
    └──requires──> multipart upload endpoint (extends v1.1 MTX upload)
    └──requires──> obs/var shape validation
    └──produces──> AnnData in session memory
                       └──feeds──> same downstream as census query

[scGPT real inference]
    └──BLOCKS ON──> flash-attn ABI resolution (see dependency note below)
    └──requires──> scGPT checkpoint (self-hosted)
    └──requires──> AnnData with normalized counts in session memory
    └──produces──> adata.obs["cell_type"] label + vote-fraction confidence per cell

[Geneformer perturbation]
    └──requires──> Geneformer checkpoint (HuggingFace ctheodoris/Geneformer)
    └──requires──> AnnData with Ensembl gene IDs in var index + n_counts column
    └──requires──> Ensembl ID normalization step (census data has it; h5ad uploads may not)
    └──requires──> tokenization: TranscriptomeTokenizer → HuggingFace .dataset directory
    └──requires──> InSilicoPerturber (perturb_type=delete for CRISPRi)
    └──requires──> InSilicoPerturberStats for cosine shift ranking
    └──produces──> ranked gene list + cosine shift scores
    └──enhances──> comparison with existing linear perturbation model

[Session history replay]
    └──requires──> v1.1 SQLite message rows (verify schema has message text + timestamps)
    └──requires──> GET /sessions/{id}/messages endpoint
    └──enhances──> session sidebar (v1.1 feature)

[CSV export]
    └──requires──> AnnData with analysis results in session memory
    └──requires──> download endpoint (GET /export/{session_id}/{result_type})

[Scanpy script export]
    └──requires──> agent parameter logging during each tool call into session state
    └──requires──> template script generator (fills in logged params)
    └──requires──> at least QC + clustering having run in session to produce meaningful script

[Docker compose]
    └──requires──> all services containerized (backend, frontend serving)
    └──requires──> optional GPU worker service with --profile gpu flag
    └──requires──> volume definitions: SQLite db + model checkpoints + upload temp
    └──requires──> CPU fallback path for non-GPU machines (scGPT/Geneformer inference stub or warning)
```

### Critical Dependency Notes

**scGPT ABI conflict is the single highest-risk dependency in v1.2.** The v1.1 shim exists because scGPT requires `flash-attn<1.0.5` with CUDA 11.7, while the rest of the stack runs PyTorch 2.x + CUDA 12.x. Options:
1. Dedicated conda env with pinned `flash-attn<1.0.5` — fragile but minimal infrastructure change
2. scGPT in its own Docker service, called via REST from the main backend — cleaner for compose deployment but requires splitting the service

**Geneformer requires Ensembl IDs in `var`.** Census data provides Ensembl IDs natively. h5ad uploads from researchers may not — gene names or other IDs are common. An ID normalization step (HGNC symbol → Ensembl lookup) must be added or clearly documented as a researcher responsibility.

**Scanpy script export depends on parameter logging.** The exporter can only fill in a correct script if the agent has been logging actual parameter values (QC thresholds, HVG count, clustering resolution, census query params) into session state during tool calls. This logging must be added as part of the same work, not deferred.

**Session history replay is low-risk but needs a schema audit.** Verify that v1.1 SQLite message rows store: message text, role (user/agent), timestamp, and tool call metadata. If any of these are missing, the replay will be incomplete.

---

## Complexity Notes by Feature Area

### 1. cellxgene-census query

**What researchers expect from the UX:** They want to say "give me lung tissue, human, 10x 3' v3" and get back a dataset that goes straight into the existing QC pipeline. They do not want to know about `obs_value_filter` syntax or TileDB-SOMA. The agent should handle the translation.

**Critical gotchas:**
- A single tissue without filtering can return millions of cells. Lung alone in CELLxGENE human data is in the hundreds of thousands. `get_anndata()` above ~100K cells risks OOM on most dev machines.
- Always include `is_primary_data == True`. Without it, cells appear multiple times from multi-study aggregations.
- Census is hosted in AWS `us-west-2`. Query latency is bandwidth-dominated. CZI's own FAQ recommends deploying in `us-west-2` for fast access.
- Human and mouse use incompatible gene annotations. Cannot mix organisms in one query.
- Census does not return normalized layers or embeddings — only raw counts. The existing normalization pipeline handles this.

**Recommended implementation pattern:** Two-step tool: (1) probe with `get_obs(column_names=["soma_joinid"], ...)` to get cell count, (2) conditionally load with `get_anndata()` if under 50K cells, or offer researcher a subsampling option above that threshold.

### 2. scGPT real inference

**What the model actually outputs:** Reference mapping adds per-cell label strings to `adata.obs` via k-NN majority vote over FAISS-indexed reference embeddings. The reference atlas from the pretrained checkpoint covers 33M cells. No native probability output from the model — only the winning label from the vote. Vote fraction (e.g. 8/10 neighbors agree) is the only confidence proxy available without retraining a classifier head.

**How to present results to researchers:** Agent response should include: (a) predicted cell type per cluster as a summary table (most common label in each Leiden cluster), (b) vote-fraction confidence where available, (c) a flag on cells or clusters with confidence < 0.6 as "low confidence — manual review recommended." Researchers are used to seeing cell type calls as cluster-level summaries, not per-cell lists.

**ABI resolution strategy:** The subprocess shim must be replaced. Recommended path: separate conda/venv environment with `flash-attn<1.0.5` and CUDA 11.7, invoked via subprocess with JSON I/O, OR a dedicated Docker service. The Docker service path is cleaner for the compose deployment milestone.

### 3. Geneformer perturbation prediction

**How it differs from the existing linear model:**
- Linear model: learns a weight matrix mapping control expression → perturbed expression; fast (~seconds), interpretable, well-calibrated; Nature Methods 2025 found it often beats foundation models on held-out perturbation tasks.
- Geneformer: BERT-style encoder pretrained on 30M cells; perturbation works by deleting a gene's token from the ranked input sequence and measuring cosine shift in the CLS/cell embedding vs. unperturbed baseline; outputs a ranked list of genes by embedding shift magnitude, not an actual expression vector.

The key difference: Geneformer does not predict a post-perturbation expression profile directly. It predicts which genes' expression will shift, ranked by embedding sensitivity. The linear model predicts actual expression deltas. These are complementary, not identical tasks. The agent should present Geneformer output as "predicted high-impact targets" and linear model output as "predicted expression profile," not compare them as if they answer the same question.

**Input pipeline is non-trivial (4 sequential steps):**
1. Normalize AnnData counts; set `var` index to Ensembl IDs (no version suffix); add `n_counts` column
2. `TranscriptomeTokenizer.tokenize_data()` — produces HuggingFace `.dataset` directory
3. `InSilicoPerturber.perturb_data(perturb_type="delete", ...)` — writes batched pickle files
4. `InSilicoPerturberStats` — computes cosine shift statistics; produces ranked gene list

Budget: ~30 min for 10K cells on CPU; GPU required for reasonable throughput on production datasets. Each step has disk I/O. The tool call must be designed as an async job, not a synchronous response.

### 4. Session history replay

**What researchers actually expect:** Full transcript of prior turns, rendered exactly as in the live session. Based on analogous agentic tools (Claude Code session restore, ChatGPT history):
- All prior messages visible on session open
- Tool calls and citations visible inline (same as live rendering)
- Timestamps so they can orient temporally
- For very long sessions (>50 turns): show last 50 by default, offer "load earlier"

**Implementation path:** `GET /sessions/{id}/messages` returns ordered rows from SQLite. Frontend replays them into the chat thread on session open. No new data storage required — this is a read + render feature. The main risk is the v1.1 schema not capturing all necessary fields.

### 5. Scanpy script export

**What a useful reproducible script looks like (researcher expectations, per single-cell reproducibility literature 2026):**

The script must be self-contained and parameter-complete. A researcher sharing it with a collaborator or re-running it 6 months later needs zero undocumented choices. Required sections:

```
# === BioClaw generated analysis script ===
# Session: {session_id}  Generated: {timestamp}
# Data source: [census query params OR upload filename + SHA256]
# Environment: pip install "scanpy[leiden]==1.12.1" anndata==0.10.x cellxgene-census
# Random seeds: 42 throughout

# 1. Data fetch (census query reproduced here with exact filter string)
# 2. QC (exact thresholds: min_genes, min_cells, pct_mito cutoff, doublet params)
# 3. Normalization + HVG (n_top_genes=XXXX)
# 4. PCA + neighbors (n_comps=50, n_pcs=30)
# 5. UMAP (random_state=42)
# 6. Leiden clustering (resolution=X.X, random_state=42)
# 7. Differential expression (method, key_added)
# 8. Annotation call (scGPT checkpoint path or Geneformer config)
```

The agent must log each parameter value at tool-call time into session state (not just "clustering was run"). The script generator is a template fill-in problem, not a script synthesis problem.

**Critical items researchers will notice if missing:**
- Scanpy version pin (current stable: 1.12.x, requires Python 3.12+)
- Random seeds (clustering is not deterministic without them)
- Exact QC thresholds (researchers will have questioned these choices; the script should reflect what was actually used)
- Census query version (CZI versions census by date; same query on a later version may return different cells)

---

## MVP Definition for v1.2

### Ship with v1.2 (All 7 milestone features)

- [ ] cellxgene-census query tool — core value: real public data without file upload
- [ ] h5ad upload — format interop table stakes; blocks real-world usage
- [ ] scGPT real inference — replaces broken stub; annotation tool is currently fake
- [ ] Geneformer perturbation prediction — second model; VCC-differentiating narrative
- [ ] Session history replay — critical UX fix; current behavior is unacceptable for daily research use
- [ ] CSV export — minimum "I got something out of this" affordance; researchers cannot use unexportable results
- [ ] Docker compose deployment — required for Biopunk Labs to actually run this; install friction kills adoption

### Add After v1.2 Validation (v1.3)

- [ ] scGPT annotation confidence display — vote fraction is trivial once annotation works; defer to post-validation polish
- [ ] Session history search by keyword — full transcript replay is v1.2; search is v1.3 when sessions grow
- [ ] Geneformer mode selection (overexpress/inhibit) — add when researchers specifically request beyond delete/CRISPRi
- [ ] Ensembl ID auto-normalization for h5ad uploads — handle symbol→Ensembl mapping server-side

### Future Consideration (v2+)

- [ ] Side-by-side annotation model comparison (scGPT vs Geneformer vs marker-based) — research tooling, not MVP
- [ ] Streaming perturbation results — requires rearchitecting Geneformer's batch-file pipeline
- [ ] Automatic session summarization — LLM cost not justified until sessions routinely exceed 100 turns

---

## Feature Prioritization Matrix

| Feature | User Value | Implementation Cost | Priority |
|---------|------------|---------------------|----------|
| h5ad upload | HIGH | LOW | P1 |
| Session history replay | HIGH | LOW | P1 |
| CSV export | HIGH | LOW | P1 |
| Cell count warning / census probe step | HIGH | LOW | P1 (bundled with census query) |
| cellxgene-census query tool | HIGH | MEDIUM | P1 |
| Docker compose | HIGH | MEDIUM | P1 |
| Scanpy script export | MEDIUM | MEDIUM | P1 |
| scGPT real inference | HIGH | HIGH (ABI blocker) | P1 |
| Geneformer perturbation | MEDIUM | HIGH (4-step pipeline) | P1 |
| scGPT vote-fraction confidence | MEDIUM | LOW | P2 |
| Session history search | MEDIUM | MEDIUM | P2 |
| Ensembl ID auto-normalization | MEDIUM | MEDIUM | P2 |

---

## Sources

- [cellxgene-census Python API — querying and fetching data](https://chanzuckerberg.github.io/cellxgene-census/notebooks/api_demo/census_query_extract.html) — HIGH confidence (official CZI docs)
- [cellxgene-census FAQ — memory and performance](https://chanzuckerberg.github.io/cellxgene-census/cellxgene_census_docsite_FAQ.html) — HIGH confidence
- [cellxgene-census 100K cell threshold recommendation](https://cellxgene-census.readthedocs.io/en/ebezzi-new-docs/notebooks/analysis_demo/comp_bio_query_data_and_metadata.html) — HIGH confidence
- [cellxgene-census Geneformer prediction notebook](https://chanzuckerberg.github.io/cellxgene-census/notebooks/analysis_demo/comp_bio_geneformer_prediction.html) — HIGH confidence; source for Geneformer output format (predicted_cell_subclass + probability)
- [scGPT reference mapping tutorial v0.2.1](https://scgpt.readthedocs.io/en/latest/tutorial_reference_mapping.html) — HIGH confidence; defines output format (label via k-NN vote, FAISS, no native probability)
- [scGPT GitHub README — dependency requirements](https://github.com/bowang-lab/scGPT) — HIGH confidence; flash-attn<1.0.5 + CUDA 11.7 requirements documented
- [Geneformer InSilicoPerturber documentation](https://geneformer.readthedocs.io/en/latest/geneformer.in_silico_perturber.html) — HIGH confidence; input/output format, perturb_type options
- [Geneformer tokenizer documentation](https://geneformer.readthedocs.io/en/latest/geneformer.tokenizer.html) — HIGH confidence; .h5ad and .loom input formats
- [Geneformer InSilicoPerturberStats documentation](https://geneformer.readthedocs.io/en/latest/geneformer.in_silico_perturber_stats.html) — HIGH confidence
- [Deep-learning perturbation prediction vs linear baselines — Nature Methods 2025](https://www.nature.com/articles/s41592-025-02772-6) — MEDIUM confidence (paywalled; accessed via search summary)
- [Zero-shot evaluation of single-cell foundation models — Genome Biology 2025](https://genomebiology.biomedcentral.com/articles/10.1186/s13059-025-03574-x) — MEDIUM confidence
- [Twelve Tips for Reproducible Single-Cell Analysis — ACM 2026](https://dl.acm.org/doi/10.1145/3736731.3746138) — MEDIUM confidence (abstract access)
- [MapMyCells 2GB h5ad file size limit](https://brain-map.org/bkp/analyze/mapmycells/files) — MEDIUM confidence; industry reference for upload size limits
- [Scanpy 1.12.x release notes](https://scanpy.readthedocs.io/en/latest/release-notes/index.html) — HIGH confidence; version pinning reference

---
*Feature research for: bioclaw v1.2 real data + bio FM integration*
*Researched: 2026-09-16*
