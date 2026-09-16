# Pitfalls Research

**Domain:** Agentic LLM harness over single-cell bioinformatics + bio foundation models (BioClaw)
**Researched:** 2026-09-16 (v1.2 update appended to original 2026-09-03 research)
**Confidence:** MEDIUM-HIGH (mix of peer-reviewed/official sources and verified WebSearch findings; see per-pitfall notes)

---

## v1.0 / v1.1 Pitfalls (Carried Forward)

> These were researched for v1.0/v1.1. They remain valid and are preserved here for
> reference. The v1.2 team MUST NOT repeat the hard-learned lessons already listed in
> PROJECT.md (scGPT ABI mismatch deferral, Scrublet n_prin_comps, re-freeze counts,
> in-process MCP exception dispatch, WebSocket-before-POST ordering, bypassPermissions,
> SessionMemory touch() ordering, 3-file MTX name-set validation).

---

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

---

## v1.2 Pitfalls — New Features Added to Existing System

> These pitfalls are specific to the v1.2 feature set being added to an already-shipped
> v1.0/v1.1 codebase. Each addresses a concrete failure mode introduced by the new
> features or by how those features interact with existing code.

---

### Pitfall 9: cellxgene-census query blocks the asyncio event loop

**What goes wrong:**
`cellxgene_census.open_soma()` and the subsequent TileDB-SOMA query (`.get_anndata()` or `.X().tables()`) are fully synchronous, CPU-bound, and I/O-bound operations that can run for 30–300 seconds on a large tissue slice (e.g., 100k+ lung cells). When called directly inside a FastAPI `async def` route handler or an MCP tool function without an executor, they block the entire uvicorn event loop. While the census query is running: WebSocket heartbeats stop, other in-progress streaming tool calls freeze mid-stream, and the frontend's activity view appears hung. The researcher sees the UI freeze and may assume the server crashed. This is worsened if the query is triggered from inside the agent's synchronous tool-calling path where `asyncio.to_thread` is not used.

**Why it happens:**
TileDB-SOMA has no async API; it is a C extension that issues blocking network I/O and CPU-heavy decompression. Developers assume "the library is fast" because the Census API documentation advertises efficient slicing, but "efficient" means fewer bytes transferred, not non-blocking. The existing v1.1 upload/ingest path uses `BackgroundTasks` or a subprocess for heavy work; cellxgene-census requires the same treatment but is easy to call inline because it looks like a simple Python function call.

Additionally, the Census documentation is clear that unfiltered queries will timeout at the server side. A query without at least one `obs_value_filter` will return an error rather than data — a silent mismatch that produces a confusing error message rather than a guard-rail.

**How to avoid:**
- **Mandatory**: wrap every `cellxgene_census` call in `asyncio.to_thread()` (Python 3.9+) or `loop.run_in_executor(None, ...)`. This moves blocking I/O to a thread pool and keeps the event loop free.
- Set an explicit timeout (e.g., 120s) on the thread via `asyncio.wait_for()`. Return a structured error to the agent if exceeded, not a silent hang.
- Require at least one filter in the query tool schema — validate before calling the census, not after. Mandatory filters: `organism` + at least one of `tissue_general`, `disease`, or `assay`. Return a tool error immediately if the filter set is empty.
- Use `get_anndata()` only when the expected cell count is confirmed below ~100k (check `len(obs_df)` first with a metadata-only query). For larger expected results, use `axis_query()` + incremental `.X().tables()` iteration to avoid materializing a >4GB AnnData in memory at once.
- Stream progress back to the frontend via WebSocket as the query runs (e.g., "Fetching 87,000 cells from CELLxGENE Census...") so the researcher knows it is working.

**Warning signs:**
- WebSocket ping-pong latency exceeds 5 seconds during a census query.
- Other concurrent sessions experience tool call timeouts while a census query is in-flight.
- `asyncio.get_event_loop()` debug mode shows a coroutine running for >100ms on the event loop (not in a thread).

**Phase to address:**
cellxgene-census query tool phase (first phase of v1.2). Must be addressed before any integration testing.

**Integration risk with existing code:**
The v1.1 streaming WebSocket implementation (`WebSocket-before-POST` fix) and the `bio_fm_worker` subprocess pattern both assume the event loop stays live. A blocking census query will silently break both, producing symptoms that look like network errors rather than Python blocking.

---

### Pitfall 10: scGPT ABI mismatch — torchtext is archived, the fix is not "upgrade torchtext"

**What goes wrong:**
The v1.0/v1.1 system deferred the `bio_fm_worker/.venv` ABI mismatch (torch/torchtext `dlopen` symbol-not-found on macOS arm64). The root cause: torchtext's PyPI repository was **archived by its owner on September 10, 2025**. The last release is `0.18.0`, which was paired with `torch==2.3.x`. Torch 2.4+ dropped torchtext entirely from coordinated releases. On macOS arm64 (Darwin 25.5.0 as shown in env), `torch==2.4+` with any `torchtext` produces a `dlopen` symbol-not-found because the C extension ABI changed and torchtext's `.so` was compiled against torch 2.3's internal symbols.

The mistake is treating this as "install the right torchtext version" — there is no correct torchtext version for torch 2.4+. The fix is to **remove the torchtext dependency from scGPT's inference path entirely**.

scGPT uses torchtext only for `torchtext.vocab.Vocab` in its `gene_tokenizer.py`. The `GeneVocab` class serializes to/from JSON and uses `Vocab` as a thin wrapper. A minimal replacement (plain `dict` + `__len__`/`__getitem__`/`get_itos()` methods) can substitute with no change to scGPT's inference logic.

**Why it happens:**
scGPT's upstream repo (`bowang-lab/scGPT`) is research code that has not been updated to track torchtext's deprecation. The PyPI package (`scgpt`) pins old dependencies. Running `pip install scgpt` pulls in torchtext which then conflicts with any torch > 2.3 on arm64. Developers assume "pip install fixed it" when the import chain still breaks at runtime on the C extension boundary.

**How to avoid:**
- Do not `pip install scgpt` into `bio_fm_worker/.venv`. Instead, install scGPT's Python source directly without its dependency on torchtext (install scGPT from source with `--no-deps`, then install its other deps minus torchtext).
- Shim `torchtext.vocab.Vocab` with a minimal local implementation before importing any scGPT module. Place the shim in `bio_fm_worker/` and import it before scGPT: `import sys; sys.modules['torchtext.vocab'] = VocabShim()`.
- Pin torch to `2.3.1` (last version with a coordinated arm64 wheel that works with the old-style scGPT checkpoint format) **only if** the `torch==2.3.1` + MPS backend combination is verified working on the dev machine. Test with `torch.device('mps')` explicitly; do not assume MPS is available just because `torch.backends.mps.is_available()` returns True — some scGPT operations fall back silently to CPU on MPS and produce wrong outputs.
- Alternatively: pin `torch==2.1.2` + `torchtext==0.16.2` — this is the combination reported working in the scGPT issue tracker (issue #10, quickstart guides). This is the safer choice if MPS inference is not required in v1.2.
- Verify the fix with a unit test: load a real scGPT checkpoint, run inference on a 500-cell AnnData, check that gene embeddings are non-NaN and non-constant.

**Warning signs:**
- `ImportError: dlopen(...libtorchtext..., symbol not found)` at worker boot.
- `AttributeError: module 'torchtext.vocab' has no attribute 'vocab'` — torchtext installed but wrong version.
- Inference completes with no error but all embeddings are the same vector — MPS silent fallback producing constant output.

**Phase to address:**
scGPT ABI repair phase (must be completed before Geneformer is added; the torch version locked here constrains Geneformer's environment).

**Confidence:** MEDIUM-HIGH (torchtext archive confirmed via GitHub, working version combinations from community reports; macOS arm64 MPS behavior from PyTorch issue tracker).

---

### Pitfall 11: Geneformer cannot share a venv with scGPT — isolation is mandatory, not optional

**What goes wrong:**
Geneformer's setup.py (as of current HuggingFace release, `ctheodoris/Geneformer`) requires `transformers`, `datasets`, `peft`, and modern `torch` (typically 2.4+). scGPT's working configuration (Pitfall 10) pins `torch==2.1.2` or `torch==2.3.1` with no `transformers` dependency. These two requirement sets are **mutually incompatible in a single venv**:
- `torch==2.1.2` + Geneformer's `transformers>=4.35`: works at import level but Geneformer's attention implementations use `torch.compile` patterns that were incomplete in 2.1.x, producing silently wrong perturbation predictions.
- `torch==2.3.1` + `torchtext==0.18.0` + Geneformer: torchtext 0.18 was compiled against torch 2.3 but does not ship arm64 wheels for torch 2.3.1 specifically — results in the same dlopen failure.
- Attempting a single venv where either model "degrades gracefully" produces models that run without error but output garbage predictions.

Additionally, Geneformer's in-silico perturbation prediction (`InSilicoPerturber`) is GPU memory intensive: a batch of 128 cells at inference requires approximately 4–6 GB VRAM. On a consumer macOS machine with M-series (MPS, shared memory), this can be exceeded if scGPT has already allocated memory in the same process (if they were co-located).

**Why it happens:**
The bio_fm_worker pattern (subprocess isolation per model) was introduced in v1.0 specifically for the scGPT ABI issue but is not yet applied to Geneformer because Geneformer is a new addition. Teams add Geneformer to the existing scGPT worker environment as "it's just another model" — this is the failure path.

**How to avoid:**
- Give Geneformer its **own isolated subprocess worker** with its own `.venv`, separate from the scGPT worker. The existing `bio_fm_worker/` subprocess dispatch pattern should be parameterized by model name, routing to the correct worker process.
- Geneformer worker: `torch>=2.4` (latest stable for arm64), `transformers>=4.35`, `datasets`, `peft`. No torchtext.
- scGPT worker: `torch==2.1.2` or `torch==2.3.1`, torchtext shim (Pitfall 10). No transformers >= 4.x.
- Each worker process is spawned fresh per inference call (or kept warm with a model-loaded process pool of size 1). GPU memory is fully released when the process exits.
- For GPU memory: enforce `batch_size=32` for Geneformer `InSilicoPerturber` on MPS/small VRAM. The published default batch size assumes A100 (40GB). On <8GB shared memory, `batch_size=16` or lower with explicit `torch.mps.empty_cache()` calls between batches.
- Test: run scGPT inference on a dataset, then immediately run Geneformer in the same session. Verify neither produces NaN/constant output.

**Warning signs:**
- `torch.compile()` errors or `RuntimeError: Expected all tensors to be on the same device` when Geneformer is first invoked.
- Geneformer `InSilicoPerturber` returns all-zero perturbation deltas — symptom of silent MPS OOM fallback or wrong device placement.
- `MPS: out of memory` error, especially if scGPT and Geneformer calls happen in the same session without a process boundary.

**Phase to address:**
Geneformer worker phase — must come after scGPT ABI repair (Pitfall 10) is locked in, because the scGPT torch version constrains what the Geneformer venv can use. Do not start Geneformer integration until scGPT tests pass cleanly.

**Confidence:** MEDIUM (Geneformer requirements from setup.py on HuggingFace; torch version interactions from community reports; GPU memory from scGPT issue tracker GPU OOM report for 20k-gene inference).

---

### Pitfall 12: Direct `.h5ad` upload — silent memory explosion on large files

**What goes wrong:**
The v1.1 upload handler uses `UploadFile` (Starlette SpooledTemporaryFile). For the existing MTX trio, this is fine because the files are small. An `.h5ad` from a public dataset can be 500MB–4GB. Three failure modes:

1. **`anndata.read_h5ad(path)` loads the full matrix into memory eagerly by default.** A 2GB `.h5ad` for 50k cells × 20k genes loads a 50k×20k float32 matrix into RAM, consuming ~4GB. On a system also running scGPT/Geneformer workers, this triggers OOM kills with no user-facing error — the Docker container crashes silently.

2. **The Starlette `UploadFile` spools to disk after a configurable threshold**, but the default spool size is small (1MB). Files below this threshold stay in RAM. A researcher uploading a 10MB test h5ad followed by a 2GB real h5ad in the same session will hit the in-memory path on the first and the disk path on the second — inconsistent behavior that's hard to debug.

3. **No format validation before reading.** An `.h5ad` file with missing `encoding-type` on its `X` matrix (a known Allen Brain Map error case) causes `anndata.read_h5ad()` to throw `KeyError: 'encoding-type'` deep in the HDF5 reader, not a user-friendly error. This bubbles up as an unhandled 500 in the existing v1.1 API and triggers `PostToolUseFailure` in the agent loop.

**Why it happens:**
The existing `ingest_10x` path was designed for MTX files (three small files). The `.h5ad` upload path reuses the same UploadFile handler pattern without adjusting for order-of-magnitude larger file sizes or the need to validate HDF5 structure before reading.

**How to avoid:**
- **Always open h5ad in backed mode first for validation**: `adata = anndata.read_h5ad(path, backed='r')` — this opens the HDF5 file without loading X into memory, allowing you to check shape, obs columns, and var columns cheaply before deciding to load.
- Check file size before reading: if `os.path.getsize(path) > 500MB`, warn the researcher and use backed mode for the session, not in-memory mode.
- Add explicit HDF5 validation before calling `read_h5ad`: verify the file is a valid HDF5 with `h5py.is_hdf5(path)` and that the `X` key exists with an `encoding-type` attribute. Return a structured tool error if not.
- Catch `KeyError`, `OSError`, and `ValueError` from `read_h5ad` and convert to `is_error=True` tool responses (consistent with the v1.1 `PostToolUseFailure` fix).
- For the Docker compose deployment: set container memory limits in `docker-compose.yml` (e.g., `mem_limit: 8g`) rather than letting OOM killer silently terminate the backend. An explicit memory error to the researcher is better than a silent container restart.

**Warning signs:**
- Backend memory usage spikes to >4GB during h5ad ingest then drops to 0 (OOM kill, not clean exit).
- `anndata.read_h5ad` raises `KeyError: 'encoding-type'` in server logs with no corresponding error response to the frontend.
- Upload succeeds (201 response) but the subsequent ingest tool call returns empty `adata.obs` — the file was loaded but X was empty or null.

**Phase to address:**
Direct `.h5ad` upload phase — implement backed-mode validation before the happy path, not after first complaints.

---

### Pitfall 13: Session transcript storage — SQLite write contention and size blowup in multi-turn sessions

**What goes wrong:**
BioClaw's session history replay requires storing and retrieving the full conversation transcript (user + assistant messages, tool call inputs/outputs). Two distinct failure modes emerge:

**Write contention**: If the v1.1 `SessionMemory` layer uses SQLite (or any SQLite-backed store) for transcript persistence, concurrent writes from multiple in-flight tool calls in the same session trigger `OperationalError: database is locked`. The agent's agentic loop fires multiple tool calls per turn; each tool completion triggers a write. Without WAL mode and busy timeout, writes serialize through Python thread-level locks which can deadlock with asyncio's event loop if called from a coroutine.

**Transcript size blowup**: In a long bioinformatics session (10+ turns), tool results include gene expression matrices, cluster label arrays, and DE tables. If stored naively as JSON blobs in the transcript, a single tool result can be 500KB–2MB. By turn 20, the stored transcript exceeds 20MB. Reading this back for "session history replay" involves loading all 20MB into memory, JSON-deserializing it, and sending it to the frontend — introducing multi-second delays on session resume. Worse, tool result blobs are re-sent to the LLM as context on every subsequent turn, burning through the 200k context window and causing cache misses.

**Why it happens:**
The v1.1 `SessionMemory` was designed for session metadata (session ID, name, turn count) and compact memory entries, not full transcript replay. Extending it to store raw tool call I/O is a natural reach but exceeds its design assumptions.

**How to avoid:**
- Enable SQLite WAL mode on every connection: `PRAGMA journal_mode=WAL; PRAGMA busy_timeout=5000`. This allows concurrent reads during writes and retries on lock contention instead of failing immediately. Required for SQLite 3.51.3+ (check the Docker base image's SQLite version).
- Store transcript messages in a dedicated `messages` table, not the existing session metadata table, with a schema: `(id, session_id, role, turn_index, content_text, tool_results_ref)`.
- Do **not** store raw tool result blobs inline. Store a reference key and serialize tool results to a separate sidecar file (e.g., `<session_id>/turn_<n>_tool_results.msgpack`). Load them lazily only when needed for frontend rendering, not for every LLM context rebuild.
- Cap stored tool result size at 64KB per result. If a result exceeds the cap, store a truncated summary in the transcript and the full result in the sidecar. The summary is sufficient for session history display; the agent re-runs the tool if it needs the full result.
- For the frontend replay, only send the last N turns (configurable, default 20) plus a summary of earlier turns. Do not send the full transcript to the LLM on resume — rebuild the session memory summary from `SessionMemory.touch()` as in v1.1 (this pattern is already established and correct).

**Warning signs:**
- `OperationalError: database is locked` in server logs during a session with rapid tool calls.
- Session resume endpoint takes >3 seconds for a session with >10 turns.
- `MemoryError` or process RSS spikes to 8GB+ when loading a transcript for a long session.
- Context window exhaustion errors from the LLM on turn 15+ of a session that has been doing active analysis.

**Phase to address:**
Session history replay phase — design the schema and size constraints before implementing replay. Do not retrofit caps after discovering the blowup in testing.

**Integration risk with existing code:**
The v1.1 `SessionMemory.touch()` + `build_options()` ordering constraint (hard-learned lesson) must be preserved. Any transcript persistence layer must call through or alongside `SessionMemory`, not bypass it, to avoid losing the memory state that drives context injection.

---

### Pitfall 14: Docker compose + `--workers N` silently breaks the entire session model

**What goes wrong:**
The v1.1 FastAPI backend maintains in-process state: `SessionMemory` objects, the bio_fm_worker subprocess handles, WebSocket connection registries, and the active agent run state are all held in Python module-level dictionaries or singleton objects in the single uvicorn process. Adding `--workers 2` (or more) to the uvicorn command in `docker-compose.yml` forks N separate OS processes, each with its own copy of all state. The result:

- A `POST /sessions/{id}/ask` request routed to Worker A starts a session; the next WebSocket connection from the same browser may land on Worker B, which has no knowledge of that session and returns a 404 or sends the wrong stream.
- `SessionMemory` for session X exists only in Worker A's process; Worker B cannot call `touch()` or `build_options()` for it.
- The bio_fm_worker subprocess handles held in Worker A's process table are invisible to Worker B.
- If the Docker container spawns workers by reading `multiprocessing.cpu_count()` (which, inside a container without CPU limit set, sees the host machine's full CPU count — e.g., 16 on an M2 Pro), the container may boot 16 workers, immediately OOM, and crash in a restart loop.

This is a silent breakage: the API returns 200 responses, but session state is randomly split across workers with no error message.

**Why it happens:**
The docker-compose.yml is written with a `CMD ["uvicorn", "app.main:app", "--workers", "$(nproc)"]` or similar, mimicking a "production-ready" configuration from tutorials. Bioinformatics ML server configs online always recommend multiple workers for throughput. BioClaw's architecture is explicitly single-process by design (one session = one agent run = one consistent memory state), but this constraint is not documented in the compose file.

**How to avoid:**
- **Hard-code `--workers 1` in the Docker compose CMD**. No autodetection. Add a comment: `# BioClaw requires single-worker: session state and bio_fm_worker subprocesses are in-process.`
- Add a startup assertion: at app boot, check `os.environ.get('WEB_CONCURRENCY', '1')`. If > 1, log a fatal error and exit. This makes accidental multi-worker deployment fail loudly instead of silently.
- If horizontal scaling is ever needed in the future, it requires moving all session state to an external store (Redis, Postgres) — document this explicitly as a future architecture requirement, not something that can be enabled by adding `--workers`.
- In the compose file, set explicit CPU and memory limits: `cpus: "2"` and `mem_limit: "6g"` for the backend service, and `mem_limit: "8g"` for the GPU worker service. This prevents the container from seeing host-level CPU count.

**Warning signs:**
- Sessions appear to "forget" previous turns intermittently (round-robin routing to a worker that doesn't hold the session).
- WebSocket connections drop with `404 session not found` despite the session having been created.
- Container starts then immediately exits with OOM — sign that worker count equals host CPU count and each tried to load scGPT/Geneformer checkpoints.

**Phase to address:**
Docker compose phase — write the constraint into the compose file and startup assertion before any other service wiring. This is cheap to do first and expensive to discover in integration testing.

---

### Pitfall 15: Scanpy script export — "reproducible" scripts that aren't reproducible

**What goes wrong:**
The result export feature includes generating a "reproducible scanpy script" from the session's analysis. Several well-documented failure modes make such scripts non-reproducible even when the author believes they are:

1. **UMAP and Leiden are non-deterministic across CPU architectures.** Even with `random_state=42`, UMAP's multi-threaded optimization (since 0.4) produces different layouts on different CPUs due to floating-point race conditions between threads. Leiden clustering (via `leidenalg`) also uses graph partition algorithms whose thread ordering is architecture-dependent. A script that produces "Figure 3" on an M2 Mac will produce a different-looking figure on an Intel server — with the same code and seed.

2. **The script has no environment pinning.** A script that begins with `import scanpy as sc` and calls `sc.tl.umap()` will behave differently on scanpy 1.9 vs. 1.11 because default parameter values changed between versions (e.g., `sc.tl.umap()` default `min_dist` changed; `sc.pl.umap()` default color scheme changed). Without an embedded `pip freeze` or explicit `#requirements:` comment, the script is not reproducible.

3. **Cell barcode ordering is not preserved.** The script reconstructs the AnnData from the session context but may not preserve the exact cell ordering from the original upload. If a researcher runs the script on a slightly different version of the dataset (e.g., re-exported from their LIMS with different barcode ordering), all cluster assignments shift silently.

4. **No checkpoint for which census version was queried.** If the analysis used `cellxgene_census`, the census version (e.g., `2024-07-01`) must be pinned in the exported script. The public census is updated monthly; re-running the script on the "latest" census will fetch a different dataset.

**Why it happens:**
Agents generate scripts by narrating the analysis steps in natural language then translating to Python. The agent knows it should call `sc.tl.umap(adata, random_state=42)` but doesn't know about UMAP's threading non-determinism, doesn't capture the running environment's package versions, and doesn't know to embed the census snapshot date.

**How to avoid:**
- **Every exported script must begin with a `#requirements:` block** generated at export time from the live session environment: `scanpy==X.Y.Z`, `anndata==X.Y.Z`, `umap-learn==X.Y.Z`, `leidenalg==X.Y.Z`, and the scGPT/Geneformer checkpoint hash if a bio FM was used.
- For UMAP reproducibility: set `n_components=2, random_state=42` AND pin `numba` and `umap-learn` versions. Include the comment: `# Note: UMAP results may differ across CPU architectures even with fixed random_state. Results here were generated on [arch].`
- If the analysis used `cellxgene_census`, the exported script must include: `census = cellxgene_census.open_soma(census_version="YYYY-MM-DD")` with the exact version string, not `"latest"`.
- Include the original cell barcodes as a filter assertion early in the script: `assert set(adata.obs_names) == EXPECTED_BARCODES` so the script fails loudly if the dataset has changed rather than silently re-clustering different cells.
- The agent tool that generates the script should call `importlib.metadata.version()` for each relevant package at export time and embed those versions — not guess from training data.

**Warning signs:**
- Two researchers running the "same exported script" on different machines get different UMAP layouts.
- Script fails silently when run on a new census version, producing empty results rather than an error.
- Script uses `sc.pp.highly_variable_genes()` without a `min_mean`/`max_mean` that matches the original run — produces a different gene set.

**Phase to address:**
Result export phase — the reproducibility constraints must be in the script template design, not discovered after the first researcher tries to reproduce a figure.

---

### Pitfall 16: Geneformer 4-step pipeline requires disk I/O between steps — running it synchronously blocks for hours

**What goes wrong:**
Geneformer's in-silico perturbation pipeline is not a single function call. It has four mandatory sequential steps:

1. **Tokenize**: `TranscriptomeTokenizer.tokenize_anndata()` converts the AnnData to a HuggingFace `.dataset` directory on disk (rank-value encoded token sequences). This step can take 10–30 minutes for 50k+ cells.
2. **Perturb**: `InSilicoPerturber.perturb_data()` reads the tokenized `.dataset` from disk, runs the transformer model forward pass on each cell with each target gene deleted or overexpressed, and writes batched pickle files to an output directory. This step writes many separate `{prefix}_dict_cell_embs_{n}batch{m}` pickle files — one per batch — and can run for 1–6 hours on CPU.
3. **Aggregate**: `InSilicoPerturberStats.get_stats()` reads all the pickle files from step 2, aggregates cosine shift statistics per gene, and writes a final stats pickle. The output is a **ranked gene list by cosine shift magnitude** (shift toward/away from goal state), NOT a post-perturbation expression vector.
4. **Interpret**: The BioClaw tool layer reads the stats pickle and converts the ranked gene list into a structured tool result.

If any step is called synchronously inside the `geneformer_worker` subprocess — and the subprocess itself is called from the FastAPI event loop without `asyncio.to_thread()` — the entire pipeline blocks the event loop for hours. Additionally, because steps 2 and 3 communicate via disk (pickle files in a directory), a failure in step 3 leaves orphaned pickle files from step 2 that must be cleaned up before a retry, otherwise step 3 aggregates partial results silently.

**Why it happens:**
Developers treat `InSilicoPerturber` as a single inference call (analogous to `model.predict()`), not as a multi-step pipeline with disk I/O between stages. The HuggingFace `ctheodoris/Geneformer` documentation shows code examples where all four steps appear in sequence in a single notebook cell, giving no indication of runtime scale or the disk dependency between steps 2 and 3.

Additionally, there is a known bug in `InSilicoPerturberStats.get_stats()` when using `mode="goal_state_shift"`: if both `cell_embs_dict` and `gene_embs_dict` pickle files are present in the output directory from step 2 (which happens when `emb_mode='cell_and_gene'` was used in step 2), the stats step raises an error. The fix is to use `emb_mode='cell'` in step 2, or move the `gene_embs_dict` pickle files out of the directory before running step 3.

**How to avoid:**
- **Each step of the pipeline must be treated as an independent async operation.** In the `geneformer_worker` subprocess, run each step in a separate thread via `asyncio.to_thread()` with an appropriate timeout (step 1: 2h, step 2: 6h, step 3: 30m). The subprocess itself must be spawned via `asyncio.to_thread()` from the FastAPI event loop, not called inline.
- **Use `emb_mode='cell'` in `InSilicoPerturber`** (not `'cell_and_gene'`) for perturbation prediction. This avoids the `InSilicoPerturberStats` directory-contents bug and reduces disk usage. Only cell embeddings are needed for cosine shift ranking.
- **Clean up intermediate pickle files on failure.** The subprocess worker must wrap steps 2 and 3 in a try/finally that removes the step-2 output directory on any exception, so retries start clean.
- **Document the output format explicitly**: the tool result is a ranked list of (gene, cosine_shift_to_goal) pairs, NOT predicted expression values. This is a fundamentally different output type from the linear perturbation model (which returns an expression vector). The tool schema must communicate this or the agent will misinterpret it and report nonsense.
- **Progress reporting**: emit WebSocket events after each step (tokenization complete, perturbation batches N/M complete, aggregation complete) — without these, the researcher sees no activity for hours and assumes the server is dead.

**Warning signs:**
- `geneformer_worker` subprocess takes >30 minutes and no intermediate progress events appear in the WebSocket stream.
- `InSilicoPerturberStats.get_stats()` raises `KeyError` or an assertion error — almost always means `gene_embs_dict` pickle files are present alongside `cell_embs_dict` files.
- Tool result contains a gene expression vector where the caller expected a ranked gene list — sign the output format was misunderstood in the tool schema.
- Orphaned pickle directories in the Geneformer worker output path after a failed run — next run double-counts results.

**Phase to address:**
Geneformer worker phase — design the 4-step pipeline async wrapper and disk cleanup before any integration testing. The output format distinction (cosine shift ranking, not expression vector) must be encoded in the tool schema before the agent is allowed to call the tool.

**Integration risk with existing code:**
The existing `bio_fm_worker` pattern (single subprocess for scGPT) does not have multi-step disk I/O. The Geneformer worker introduces a new pattern where the subprocess must manage a pipeline across multiple stages and an intermediate disk directory. The existing subprocess dispatch code in `annotation/fm_client.py` does not support this — a new `geneformer_worker/` dispatch module is needed, not a shim in `bio_fm_worker/`.

**Confidence:** MEDIUM-HIGH (pipeline steps verified against official Geneformer docs and HuggingFace discussions; `emb_mode` bug confirmed in official discussion thread #436; output format from official `InSilicoPerturberStats` docs; async design is standard FastAPI pattern).

---

### Pitfall 17: Geneformer requires Ensembl IDs in `adata.var` — gene symbols produce silent empty tokenization

**What goes wrong:**
Geneformer's `TranscriptomeTokenizer` requires a column named exactly `"ensembl_id"` in `adata.var` containing stable Ensembl gene IDs (e.g., `ENSG00000141510`). It also requires a column named `"n_counts"` in `adata.obs` containing per-cell total read counts.

Datasets loaded through BioClaw's standard ingest pipeline (`ingest/loaders.py`) have **gene symbols** as `adata.var_names` (e.g., `TP53`, `GAPDH`) and do not have an `"ensembl_id"` column in `adata.var` at all. The tokenizer does not raise an error on missing or wrong-format gene IDs. Instead, it silently skips every gene that does not match a key in its 25,424-gene vocabulary (which is keyed by Ensembl ID). A dataset with only gene symbols produces **zero matched tokens** per cell. The model then runs without error on these zero-length sequences, producing all-identical embeddings. The perturbation deltas are all zero. The tool returns a "result" that looks like valid output with no exception raised.

Additionally, Ensembl IDs frequently carry version suffixes in real data (e.g., `ENSG00000141510.21`) that do not match the unversioned IDs in Geneformer's vocabulary (`ENSG00000141510`). Even if a researcher uploads an h5ad with Ensembl IDs as var_names, version-suffix mismatch silently drops those genes from tokenization.

**Why it happens:**
The standard 10x Genomics ingest pipeline stores gene symbols, not Ensembl IDs, as var_names — this is the biological community's default for analysis because gene symbols are human-readable. Geneformer was trained on Ensembl IDs because they are stable and unambiguous across gene databases. The mismatch between "what ingest produces" and "what Geneformer requires" is invisible at runtime because the tokenizer does not raise an error on a missing mapping, it just skips unmatched genes.

**How to avoid:**
- **Add Ensembl ID mapping as an explicit pre-processing step in the Geneformer worker**, not something assumed to exist in the input AnnData. The worker must:
  1. Check whether `adata.var` has an `"ensembl_id"` column. If not, attempt to map from gene symbols using `pyensembl`, `mygene`, or a static mapping file bundled with the worker.
  2. Strip version suffixes from any Ensembl IDs before matching: `ensg_id.split('.')[0]` applied to both the data and the vocabulary keys.
  3. Count how many genes matched successfully. If < 50% of genes matched, emit a tool error or warning: "Only N% of genes matched Geneformer vocabulary; results may be unreliable."
  4. Never proceed silently with <100 matched genes — the model's token sequences will be degenerate and the cosine shifts meaningless.
- **Check for `n_counts` in `adata.obs`.** If absent, compute it from `adata.layers['counts'].sum(axis=1)` (raw counts, consistent with BioClaw's existing counts-layer contract) and add it as `adata.obs["n_counts"]` before tokenization.
- **Test with a dataset that has only gene symbols.** The test must assert that either a valid match rate was achieved (>50%) or the tool returned `is_error=True` with a descriptive message — never that all embeddings are identical vectors.

**Warning signs:**
- Geneformer cosine shifts are all 0.0 or all identical — sign of empty/degenerate tokenization.
- `len(tokenized_dataset)` shows the correct cell count but each row has 0 or 1 input_ids — tokenization ran but matched nothing.
- No `"ensembl_id"` column in `adata.var` for any dataset ingested via the standard 10x pipeline.
- Ensembl IDs in `adata.var` end in `.N` suffixes (e.g., `.21`) — version suffix mismatch.

**Phase to address:**
Geneformer worker phase — the Ensembl ID mapping step must be part of the worker design from the start, not retrofitted after observing all-zero perturbation deltas. This is the most likely silent failure mode for a researcher who uploads real 10x Genomics data.

**Integration risk with existing code:**
The v1.1 ingest pipeline (`ingest/loaders.py`, `ingest/contract.py`) uses gene symbols as `var_names` throughout, and no part of the existing pipeline adds an `"ensembl_id"` column. Geneformer's preprocessing requirement is orthogonal to the existing ingest contract — it must be handled inside the `geneformer_worker/` subprocess, not by modifying the ingest pipeline (which would break scGPT and other consumers that expect gene symbols).

**Confidence:** HIGH (Ensembl ID requirement confirmed in official Geneformer tokenizer docs and HuggingFace discussion #36; version-suffix mismatch is a standard Ensembl ID handling issue confirmed across multiple bioinformatics tools; silent skip behavior confirmed via official Geneformer model card).

---

## Technical Debt Patterns

| Shortcut | Immediate Benefit | Long-term Cost | When Acceptable |
|----------|-------------------|----------------|-----------------|
| Hard-code batch correction and QC thresholds as pipeline defaults instead of exposing/logging them | Faster first working demo | Silently biases every dataset the same way; hard to retrofit auditability | MVP demo on one known dataset only, never for Biopunk Labs' real ongoing use |
| Skip building a statistical baseline tool alongside the FM tool | Less to build for MVP | No way to tell if the FM is even better than a trivial predictor (Pitfall 4) | Never — this is cheap to build and central to credibility |
| Let the agent's natural-language answer be the only output artifact (no linked structured data) | Simpler UX for the demo | Impossible to audit hallucinated claims; researcher can't verify | Only for a first internal throwaway prototype, never past that |
| Self-host scGPT/Geneformer on whatever GPU is available without capacity planning | Skip infra decision now | OOM failures or silent truncation on larger datasets once real Biopunk Labs data arrives | Acceptable only while testing on small public datasets (<50k cells) |
| Treat VCC benchmark validation as a one-time check instead of a repeatable regression test | Faster to claim "validated against VCC" | No way to detect regressions as the pipeline/tools evolve | Never for anything beyond a single demo screenshot |
| Co-locate scGPT and Geneformer in a single venv to save setup time | One less environment to manage | Silent wrong predictions from ABI/version conflicts; both models unreliable | Never |
| Call cellxgene-census synchronously inline in a tool handler | Less code, looks simpler | Blocks event loop; breaks WebSocket streaming; appears as server hang to researcher | Never |
| Store full tool result blobs in transcript JSON | Simpler schema | 20MB+ transcripts, multi-second session resume, context window exhaustion | Never past 5-turn sessions |
| `--workers $(nproc)` in docker-compose CMD | Mimics "production" config | Silently splits session state; non-deterministic failures | Never — BioClaw is architecturally single-worker |
| Export scanpy script without pinned dependency versions | Less code in template | Non-reproducible; different results on different machines | Acceptable for a quick internal demo; never for a result a researcher will publish |
| Call Geneformer InSilicoPerturber synchronously inside the subprocess | Looks like a single model call | Blocks for hours; disk I/O between steps fails silently; no progress to frontend | Never |
| Skip Ensembl ID mapping before Geneformer tokenization and hope the data already has them | Saves one preprocessing step | Silent all-zero perturbation deltas with no error; looks like a result | Never |

## Integration Gotchas

| Integration | Common Mistake | Correct Approach |
|-------------|----------------|------------------|
| scGPT / Geneformer (HuggingFace-hosted or self-hosted checkpoints) | Assuming zero-shot output is reliable without task-specific fine-tuning or baseline comparison | Always pair FM tool calls with a baseline comparison (Pitfall 4); treat zero-shot output as a hypothesis |
| AnnData `.raw` attribute | Using `adata.raw = adata` assuming it snapshots counts | Use `adata.layers['counts'] = adata.X.copy()` for a real, independent copy |
| 10x Genomics `.mtx`/`.h5` ingest | Assuming all uploaded files are already filtered/cell-called correctly by upstream instrument software | Re-run/verify cell calling and basic sanity checks (barcode counts, gene counts) rather than trusting the raw vendor output blindly |
| Virtual Cell Challenge public dataset | Using only the metric(s) that make the pipeline look best (e.g., reporting only DES) | Report all three official metrics (PDS, DES, MAE) with documented caveats per Arc's own findings |
| Claude/agentic tool-calling loop | Not logging/validating that a claimed tool call actually executed | Execution-trace validation before presenting any tool-derived result (Pitfall 6) |
| cellxgene-census `open_soma()` | Calling synchronously inside `async def` route or MCP tool | Wrap in `asyncio.to_thread()`; require filter in query schema; check cell count before `get_anndata()` |
| scGPT `bio_fm_worker` and torchtext | Trying to install a compatible torchtext for torch 2.4+ | torchtext is archived; shim `torchtext.vocab` locally; pin `torch==2.1.2` or `2.3.1` |
| Geneformer and scGPT workers | Running both in the same subprocess or venv | Separate subprocess workers with separate venvs; different torch version per model |
| SQLite `SessionMemory` for transcript storage | Default journal mode with no busy timeout | `PRAGMA journal_mode=WAL; PRAGMA busy_timeout=5000`; separate messages table; sidecar files for tool blobs |
| Docker compose `CMD` | `--workers $(nproc)` auto-detection | Hard-code `--workers 1`; assert at startup; document constraint |
| Scanpy script export | Omitting package versions and census snapshot date | Embed `importlib.metadata.version()` output; census version string; architecture caveat for UMAP |
| `.h5ad` file upload | `read_h5ad(path)` loading full X matrix eagerly | Open with `backed='r'` first; validate HDF5 structure; check size before full load |
| Geneformer `InSilicoPerturber` | Treating as a single function call; running synchronously | Four-step pipeline with disk I/O between steps; wrap each step in async executor; use `emb_mode='cell'` |
| Geneformer tokenizer | Passing AnnData with gene symbols as var_names; skipping Ensembl ID mapping | Add `ensembl_id` column via gene-symbol-to-Ensembl mapping before tokenizing; strip version suffixes; validate match rate |

## Performance Traps

| Trap | Symptoms | Prevention | When It Breaks |
|------|----------|------------|----------------|
| Loading full `.h5ad` into memory per agent tool call | Slow/failing tool calls as dataset size grows | Use backed mode / chunked access (`anndata` backed=`r`) for large datasets; don't reload full object per tool invocation | Datasets above a few hundred thousand cells or when running on modest self-hosted hardware |
| Re-running FM inference from scratch on every conversational turn | Slow, expensive repeated GPU calls for the "same" dataset the researcher already asked about | Cache FM embeddings/predictions keyed to dataset version + params in the session/memory layer | As soon as a multi-turn conversation revisits the same dataset — which is the explicit MVP requirement |
| No dataset versioning across a multi-turn session | Agent gives different answers to the same question because the "current dataset" silently changed (re-QC'd, re-filtered) mid-conversation | Version every canonical dataset artifact (content hash or explicit version tag) and have session memory reference the exact version, not just a dataset name | As soon as more than one processing run of the same source data exists |
| cellxgene-census query without cell count pre-check | Materializing a >2GB AnnData from a tissue slice with >500k cells; OOM kill | Metadata-only query first to check `len(obs)`; use incremental iteration for >100k | Any query without explicit tissue+cell-type filters on the full human organism |
| Tool result blobs stored inline in transcript | Session resume takes >5 seconds; context window exhausted at turn 15 | Sidecar files for large results; cap inline storage at 64KB | Sessions longer than 5 turns that include DE or clustering results |
| Geneformer InSilicoPerturber with default batch_size on MPS | OOM kill mid-inference; all-zero deltas on resume | Enforce batch_size=16 or lower on MPS/shared memory; explicit `torch.mps.empty_cache()` between batches | Any dataset >10k cells on M-series Mac with <16GB unified memory |

## Security Mistakes

| Mistake | Risk | Prevention |
|---------|------|------------|
| Agent has unrestricted code-execution/filesystem access while processing wet-lab data | Prompt injection or a malformed tool call could exfiltrate or corrupt proprietary Biopunk Labs research data; container escape via crafted inputs (documented CVE pattern in agent sandboxes, e.g., CVE-2024-21626-style Dockerfile/WORKDIR escapes) | Run all code-execution tool calls in a resource-limited (cgroup-enforced, not just app-level) sandbox with no default network egress and read-only mounts except for scoped dataset directories |
| Treating internal-tool status as "no security needed yet" | Even though PROJECT.md scopes this as internal-only with no auth/multi-tenant work, unrestricted agent tool access to a researcher's real data is still a risk within a single-user context | Apply the same tool-execution sandboxing discipline even for a single internal user — the risk is agent error/hallucination, not just external attackers |
| No provenance/audit trail for what data an FM tool call sent externally (if using hosted inference rather than self-hosted) | Wet-lab data (potentially pre-publication, IP-sensitive to Biopunk Labs) could leave the local environment without anyone noticing | If hosted inference is used, explicitly log and disclose every external API call boundary in the tool contract; default to self-hosting for anything not yet cleared for external transfer |
| Docker GPU worker service has no resource limits | Geneformer `InSilicoPerturber` or scGPT inference with large batch size OOM-kills the container; Docker restarts it silently, resetting all session state | Set `mem_limit` and `deploy.resources.reservations.devices` with explicit GPU constraints in compose; handle worker restart gracefully with session checkpoint |

## UX Pitfalls

| Pitfall | User Impact | Better Approach |
|---------|-------------|-----------------|
| Presenting FM/agent output as a single confident sentence with no uncertainty indicator | Researcher over-trusts a borderline or wrong result (Pitfall 5) | Always surface effect size + confidence/uncertainty alongside any interpreted claim |
| No link from a natural-language answer back to the underlying data/plot/table | Researcher can't independently verify or reuse the analysis, defeating the point of replacing manual scripting | Every answer includes or links the structured artifact (DE table, UMAP, prediction matrix) it's summarizing |
| Silent QC filtering with no visibility into what was removed | Researcher unknowingly loses a cell population relevant to their question (Pitfall 3) | QC step always reports what/how much was filtered and why, even in an automated agent run |
| Agent picks a default reference/model version without asking or disclosing it | Results aren't reproducible across sessions if defaults change later | Every tool call output should record and display which model/reference version was used |
| No progress feedback during census query or FM inference | Researcher sees a frozen UI for 30–300 seconds and assumes the server crashed | WebSocket progress messages during all long-running operations (census fetch, scGPT inference, Geneformer inference) |
| Session resume shows "Resuming..." with no prior context | Researcher loses track of what analysis was already done; repeats work | Full transcript replay in the UI, not just a banner; prior tool results visible in the activity panel |
| Exported scanpy script fails on first run due to missing environment | Researcher experience: "your export feature is broken" | Every exported script includes dependency install instructions at the top and fails with a clear error if versions don't match |
| Geneformer tool returns "result" with all-zero cosine shifts | Researcher concludes gene has no perturbation effect; actually a silent data format failure (Pitfall 17) | Validate match rate after tokenization; surface match rate and gene count in tool output; block execution if <50% genes matched |

## "Looks Done But Isn't" Checklist

- [ ] **Ingest pipeline:** Often missing an immutable raw-counts layer — verify `adata.layers['counts']` exists and is never touched by normalization steps.
- [ ] **QC step:** Often missing per-cluster/per-cell-type breakdown of what was filtered — verify a filtering report exists, not just a final filtered object.
- [ ] **Bio FM tool wrapper:** Often missing a baseline comparison — verify a non-FM baseline tool exists and its output appears in every FM-derived answer.
- [ ] **Agent interpretation layer:** Often missing traceability from natural-language claims to underlying numeric tool output — verify every claim in a final answer can be traced to a logged tool-call result.
- [ ] **Tool-calling loop:** Often missing execution-trace validation — verify there's no path for the agent to present a result without a corresponding logged tool invocation.
- [ ] **Session/memory layer:** Often missing dataset versioning — verify "the dataset we're discussing" resolves to a specific immutable version, not a mutable name.
- [ ] **VCC benchmark validation:** Often missing multi-metric reporting — verify PDS, DES, and MAE are all reported with baseline comparison, not a single cherry-picked metric.
- [ ] **cellxgene-census tool:** Often missing filter validation and cell count pre-check — verify unfiltered queries are blocked at the tool schema level, not discovered via server-side timeout.
- [ ] **cellxgene-census tool:** Often missing executor wrapping — verify `asyncio.to_thread()` is used; test by running a census query and checking that another WebSocket session stays live.
- [ ] **scGPT worker:** Often "fixed" by reinstalling torchtext — verify the torchtext shim is in place, not a version pin that will break again after next torch minor release.
- [ ] **Geneformer worker:** Often shares venv with scGPT — verify separate `.venv` directories and subprocess dispatch routing; test by running both models in the same session.
- [ ] **Geneformer worker:** Often treats InSilicoPerturber as a single call — verify 4-step pipeline is implemented with async wrapping per step, disk cleanup on failure, and `emb_mode='cell'`.
- [ ] **Geneformer worker:** Often skips Ensembl ID mapping — verify `ensembl_id` column exists in `adata.var` before tokenization, match rate is validated, and all-zero output is treated as an error.
- [ ] **h5ad upload:** Often missing backed-mode validation — verify `h5py.is_hdf5()` check and try opening with `backed='r'` before full load; test with a malformed h5ad file.
- [ ] **Session transcript:** Often missing WAL mode — verify `PRAGMA journal_mode` returns `wal` at session startup; run concurrent tool calls and check for `OperationalError`.
- [ ] **Docker compose:** Often has `--workers` auto-detected or set to >1 — verify CMD contains `--workers 1` explicitly; test by running two concurrent sessions and verifying state is consistent.
- [ ] **Exported scanpy script:** Often missing environment pinning — verify the script begins with a `#requirements:` block generated from the live environment; test by running on a fresh venv with different package versions and confirming it fails with a clear error.

## Recovery Strategies

| Pitfall | Recovery Cost | Recovery Steps |
|---------|---------------|----------------|
| Raw counts silently corrupted (Pitfall 1) | LOW-MEDIUM | Re-ingest from original `.mtx`/`.h5` source files if retained; add layer-contract validation going forward |
| Over-aggressive batch correction erased real signal (Pitfall 2) | MEDIUM | Re-run analysis without correction or with a milder method on the same raw-count layer; compare effect sizes before/after |
| Agent presented a hallucinated/unverifiable claim (Pitfall 5/6) | MEDIUM-HIGH | Retrofit execution-trace logging and require re-verification of any prior "final answers" given without a traceable tool-call log |
| VCC validation only reported misleading metric (Pitfall 7) | LOW | Re-run evaluation harness reporting all three metrics plus baseline comparison; no data reprocessing needed if raw predictions were saved |
| Wrong/low-confidence cell-type labels shipped without disclosure (Pitfall 8) | MEDIUM | Re-run annotation tool with confidence/reference metadata surfaced; flag prior outputs as needing review |
| Event loop blocked by census query (Pitfall 9) | LOW | Add `asyncio.to_thread()` wrapper; no data loss; no session state change required |
| scGPT torchtext ABI broken (Pitfall 10) | MEDIUM | Create torchtext shim module; re-test inference; pin torch version in bio_fm_worker requirements.txt |
| Geneformer/scGPT venv conflict (Pitfall 11) | MEDIUM | Split into two separate subprocess workers; re-test both models; verify no shared state |
| h5ad OOM on large upload (Pitfall 12) | LOW-MEDIUM | Add size check and backed-mode path; existing successful sessions not affected |
| SQLite database locked (Pitfall 13) | LOW | Enable WAL mode; add busy timeout; migrate transcript to separate table with sidecar for large results |
| Multi-worker session split (Pitfall 14) | LOW (before deployment) / HIGH (after) | Change `--workers 1` in compose; if already deployed with split state, sessions are unrecoverable — users must restart |
| Non-reproducible exported script (Pitfall 15) | MEDIUM | Re-generate script with environment pinning; communicate to researcher which environment was used for the original |
| Geneformer pipeline blocking / orphaned disk files (Pitfall 16) | MEDIUM | Add async wrapping per step; add finally-block disk cleanup; re-run affected sessions from ingest |
| Geneformer all-zero output from missing Ensembl IDs (Pitfall 17) | LOW (data not corrupted) | Add Ensembl ID mapping step; re-run Geneformer tool on same dataset; existing scGPT/linear results unaffected |

## Pitfall-to-Phase Mapping

| Pitfall | Prevention Phase | Verification |
|---------|------------------|--------------|
| Silent raw-count corruption (#1) | Ingest/QC pipeline phase | Automated test: normalize a dataset, confirm `layers['counts']` unchanged |
| Batch correction erasing signal (#2) | Ingest/QC pipeline + perturbation-model tool phase | Compare DE effect sizes pre/post correction on a known perturbation dataset |
| QC over-filtering (#3) | Ingest/QC pipeline phase | QC report includes per-cluster filtering breakdown reviewed before shipping |
| FM underperforming baseline undetected (#4) | Bio FM tool-wrapper phase | Baseline tool exists and its output appears in every FM tool test/demo |
| LLM hallucinated interpretation (#5) | Interpretation/reporting phase | Every demo answer traces to a specific logged tool-call result; spot-check with adversarial ambiguous queries |
| Tool-call hallucination / bypass (#6) | Agent orchestration/tool-routing phase | Execution-trace audit: no presented result lacks a matching tool-call log entry |
| VCC metric misuse (#7) | VCC benchmark-validation phase | Validation report includes PDS, DES, MAE, and baseline comparison — checked against Arc's 2025 wrap-up caveats |
| Cell-type/ontology mismatch (#8) | Bio FM tool-wrapper phase | Annotation tool output includes reference/version/confidence fields, tested against a known-label dataset |
| cellxgene-census blocks event loop (#9) | cellxgene-census tool phase | Event loop latency test: run census query; verify other WebSocket sessions stay alive |
| scGPT torchtext ABI (#10) | scGPT ABI repair phase | Inference unit test: load real checkpoint, run on 500-cell AnnData, assert non-NaN non-constant embeddings |
| Geneformer/scGPT venv conflict (#11) | Geneformer worker phase (after #10 locked) | Both models invoked in same session; verify correct outputs; check subprocess process table shows two distinct .venvs |
| h5ad upload OOM (#12) | Direct h5ad upload phase | Upload a 2GB+ h5ad; verify backed-mode path taken; upload a malformed h5ad; verify structured error returned |
| SQLite write contention (#13) | Session history replay phase | Concurrent tool calls in same session; verify no `OperationalError`; 20-turn session resume test for latency |
| Multi-worker session split (#14) | Docker compose phase | Hard-code `--workers 1` and startup assertion; verify in compose smoke test |
| Non-reproducible scanpy export (#15) | Result export phase | Run exported script on fresh venv with different package versions; verify it fails with clear dependency error |
| Geneformer 4-step pipeline blocking / disk I/O (#16) | Geneformer worker phase | Run full pipeline with progress events; verify WebSocket stays alive; test failure cleanup by killing mid-step |
| Geneformer Ensembl ID mismatch (#17) | Geneformer worker phase | Test with a gene-symbol dataset; verify either >50% match rate achieved or is_error returned; assert cosine shifts are non-zero |

## Sources

- [Batch correction methods used in single-cell RNA sequencing analyses are often poorly calibrated (PMC, 2025)](https://pmc.ncbi.nlm.nih.gov/articles/PMC12315870/) — HIGH confidence, peer-reviewed
- [Performance Assessment and Selection of Normalization Procedures for Single-Cell RNA-Seq (PMC/ScienceDirect)](https://pmc.ncbi.nlm.nih.gov/articles/PMC6544759/) — HIGH confidence, peer-reviewed
- [Adata.raw gets modified upon log normalization of adata · Issue #3073 (scverse/scanpy GitHub)](https://github.com/scverse/scanpy/issues/3073) — HIGH confidence, official repo issue
- [Chapter 8 Doublet detection — Advanced Single-Cell Analysis with Bioconductor](https://bioconductor.org/books/3.15/OSCA.advanced/doublet-detection.html) — HIGH confidence, official reference text
- [Common Considerations for Quality Control Filters for Single Cell RNA-seq Data (10x Genomics)](https://www.10xgenomics.com/analysis-guides/common-considerations-for-quality-control-filters-for-single-cell-rna-seq-data) — HIGH confidence, official vendor guidance
- [Deep-learning-based gene perturbation effect prediction does not yet outperform simple linear baselines (Nature Methods, 2025)](https://www.nature.com/articles/s41592-025-02772-6) — HIGH confidence, peer-reviewed
- [Zero-shot evaluation reveals limitations of single-cell foundation models (Genome Biology, 2025)](https://link.springer.com/article/10.1186/s13059-025-03574-x) — HIGH confidence, peer-reviewed
- [Virtual Cell Challenge 2025 Wrap-Up: Winners and Reflections (Arc Institute)](https://arcinstitute.org/news/virtual-cell-challenge-2025-wrap-up) — HIGH confidence, official organizer post-mortem
- [More Vulnerable than You Think: On the Stability of Tool-Integrated LLM Agents (arXiv, 2025)](https://arxiv.org/pdf/2506.21967) — MEDIUM confidence, preprint
- [LLM-based Agents Suffer from Hallucinations: A Survey of Taxonomy, Methods, and Directions (arXiv, 2025)](https://arxiv.org/pdf/2509.18970) — MEDIUM confidence, preprint survey
- [torchtext is Deprecated · Issue #352 · bowang-lab/scGPT](https://github.com/bowang-lab/scGPT/issues/352) — HIGH confidence, official upstream repo
- [[RFC] Deprecate/Stop TorchText releases starting with Pytorch release 2.4 · Issue #2250 · pytorch/text](https://github.com/pytorch/text/issues/2250) — HIGH confidence, official PyTorch repo
- [pytorch/text repository archived September 10, 2025](https://github.com/pytorch/text) — HIGH confidence, official
- [Can we have requirements.txt to get required environment? · Issue #10 · bowang-lab/scGPT](https://github.com/bowang-lab/scGPT/issues/10) — MEDIUM confidence, community issue tracker
- [Geneformer setup.py — HuggingFace ctheodoris/Geneformer](https://huggingface.co/ctheodoris/Geneformer/raw/main/setup.py) — HIGH confidence, official model card
- [geneformer.in_silico_perturber — geneformer 0.1.0 documentation](https://geneformer.readthedocs.io/en/latest/geneformer.in_silico_perturber.html) — HIGH confidence, official docs
- [geneformer.in_silico_perturber_stats — geneformer 0.1.0 documentation](https://geneformer.readthedocs.io/en/latest/geneformer.in_silico_perturber_stats.html) — HIGH confidence, official docs
- [Errors of InSilicoPerturberStats · ctheodoris/Geneformer Discussion #436](https://huggingface.co/ctheodoris/Geneformer/discussions/436) — HIGH confidence, official maintainer response
- [ensembl_id and in silico perturbation · ctheodoris/Geneformer Discussion #36](https://huggingface.co/ctheodoris/Geneformer/discussions/36) — HIGH confidence, official maintainer response
- [geneformer.tokenizer — geneformer 0.1.0 documentation](https://geneformer.readthedocs.io/en/latest/geneformer.tokenizer.html) — HIGH confidence, official docs
- [Querying and fetching the single-cell data — cellxgene-census documentation](https://chanzuckerberg.github.io/cellxgene-census/notebooks/api_demo/census_query_extract.html) — HIGH confidence, official docs
- [Computing on X using online (incremental) algorithms — cellxgene-census documentation](https://chanzuckerberg.github.io/cellxgene-census/notebooks/api_demo/census_compute_over_X.html) — HIGH confidence, official docs
- [cellxgene-census agent skills — filter requirement noted](https://github.com/K-Dense-AI/scientific-agent-skills/blob/main/skills/cellxgene-census/SKILL.md) — MEDIUM confidence, community
- [How to Fix SQLite "Database Is Locked" Errors Under Concurrent Writes (OneUptime, 2026)](https://oneuptime.com/blog/post/2026-09-08-fix-sqlite-database-is-locked-concurrent-writes/view) — MEDIUM confidence, technical blog
- [SQLite concurrent writes and "database is locked" errors (Ten Thousand Meters)](https://tenthousandmeters.com/blog/sqlite-concurrent-writes-and-database-is-locked-errors/) — HIGH confidence, well-sourced technical post
- [Fixing Claude Code's concurrent session problem implementing memory MCP with SQLite WAL mode (DEV Community)](https://dev.to/daichikudo/fixing-claude-codes-concurrent-session-problem-implementing-memory-mcp-with-sqlite-wal-mode-o7k) — MEDIUM confidence, community
- [Server Workers — Uvicorn with Workers (FastAPI official docs)](https://fastapi.tiangolo.com/deployment/server-workers/) — HIGH confidence, official
- [Running FastAPI SSE Behind Gunicorn with Multiple Workers — stateful subscriber queues break](https://www.server-sent-events.com/backend-stream-generation-connection-management/python-fastapi-sse-implementation-guide/running-fastapi-sse-behind-gunicorn-with-multiple-workers/) — MEDIUM confidence, technical blog
- [Run Docker Compose services with GPU access (Docker official docs)](https://docs.docker.com/compose/how-tos/gpu-support/) — HIGH confidence, official
- [Docker Compose does not automatically use GPU (MyIT Cyber)](https://myitcyber.com/insights/docker-compose-gpu-access) — MEDIUM confidence
- [Problem at reproducibility of UMAP / leiden · Issue #1009 · scverse/scanpy](https://github.com/scverse/scanpy/issues/1009) — HIGH confidence, official repo
- [leiden and umap not reproducible on different CPUs · Issue #2014 · scverse/scanpy](https://github.com/scverse/scanpy/issues/2014) — HIGH confidence, official repo
- [UMAP Reproducibility — umap 0.5.8 documentation](https://umap-learn.readthedocs.io/en/latest/reproducibility.html) — HIGH confidence, official docs
- [Malformed input h5ad file — Allen Brain Map Community Forum](https://community.brain-map.org/t/malformed-input-h5ad-file/3863) — MEDIUM confidence, community forum
- [UploadFile hogs RAM · Issue #579 · Kludex/starlette](https://github.com/Kludex/starlette/issues/579) — HIGH confidence, official repo issue
- [Question about perturbation prediction in scGPT · Issue #314 · bowang-lab/scGPT](https://github.com/bowang-lab/scGPT/issues/314) — MEDIUM confidence, upstream issue (20GB GPU memory for 20k-gene inference)

---
*Pitfalls research for: BioClaw (agentic harness for bio foundation models, single-cell MVP)*
*Originally researched: 2026-09-03*
*v1.2 update: 2026-09-16*
