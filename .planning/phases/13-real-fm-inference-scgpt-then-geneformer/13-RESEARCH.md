# Phase 13: Real FM Inference — scGPT then Geneformer - Research

**Researched:** 2026-09-17
**Domain:** Bio foundation model inference (scGPT cell-type annotation, Geneformer perturbation prediction) via isolated-venv subprocess workers
**Confidence:** HIGH (scGPT: direct introspection of the actually-installed package in this repo's own `bio_fm_worker/.venv`; Geneformer: official readthedocs API pages fetched live + official HF repo, cross-checked against this project's own prior PITFALLS.md research)

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-------------------|
| FM-01 | Agent calls real scGPT inference (not a stub) for cell-type annotation, returning per-cell-type predictions with a k-NN vote-fraction confidence proxy alongside the existing decoupler statistical baseline | "Existing Implementation State" + "scGPT: What Already Works" + "Pattern 1: k-NN Vote-Fraction Confidence" sections below — the subprocess/API integration already exists and is verified against the real installed package; the concrete gap is the confidence metric and hardening/re-verification |
| FM-02 | Agent can invoke Geneformer as a second perturbation-response model, returning a ranked gene list by cosine shift — explicitly distinct from the linear model's expression-vector output — with Ensembl IDs validated in `adata.var` before inference runs | "Geneformer: Four-Step Pipeline" + "Don't Hand-Roll" (Ensembl ID mapping) + "Common Pitfalls" (Pitfalls 2-4) sections below |
</phase_requirements>

## Summary

This phase has two very differently-shaped halves. **scGPT (FM-01)** is not being built from scratch — Phase 4 already shipped a working `annotation/fm_client.py` → `bio_fm_worker/run_scgpt_embed.py` subprocess pipeline that calls the real, installed `scgpt.tasks.embed_data()` API, and a `bio_fm_smoke`-marked integration test already demonstrated it working end-to-end against a real checkpoint (git commit `8e500d7`, 2026-09-08). I independently re-verified `scgpt.tasks.embed_data()`'s live signature and full source directly against the installed package in `bio_fm_worker/.venv` (Python 3.9.6, scgpt 0.2.4) in this research session — it matches exactly what `run_scgpt_embed.py` already assumes. The real, concrete gap between what exists and what FM-01/the roadmap's success criteria demand is: (1) the confidence proxy currently implemented is top-1 cosine similarity of the majority label, not the "k-NN vote-fraction" the requirement explicitly asks for, and (2) the checkpoint/reference-index/embedding-cache artifacts are all gitignored (`bio_fm_worker/checkpoints/`, `*.h5ad`, `*.scgpt_emb.npy`), meaning nothing about this pipeline is reproducible on a clean checkout — which is very likely *why* the roadmap still calls it a "stub" despite the code and one verified local run existing. Treat FM-01 as "verify, harden, and swap the confidence metric," not "write the scGPT integration."

**Geneformer (FM-02)** is genuinely new work with no prior code in this repo. It has no PyPI package (confirmed via a live 404 from `pypi.org/pypi/geneformer/json` — a WebSearch AI summary incorrectly claimed a PyPI package exists; do not trust that claim), requires Python ≥3.10 (available on this machine at `/opt/homebrew/bin/python3.10`, confirmed live), and is installed by `git clone` from Hugging Face (`ctheodoris/Geneformer`) followed by `pip install .` inside a **second, separate** isolated venv (`geneformer_worker/.venv`) — it cannot share `bio_fm_worker/.venv` (Python 3.9, old torch/torchtext pins) or the main venv (Python 3.12+). The "four-step pipeline" the roadmap references maps to four real, distinct Geneformer classes with real disk I/O between them: `TranscriptomeTokenizer.tokenize_data()` → `EmbExtractor.extract_embs()` → `InSilicoPerturber.perturb_data()` → `InSilicoPerturberStats.get_stats()`. This is categorically more complex than scGPT's single-function-call pattern, which is exactly why the roadmap sequences scGPT first — the subprocess/JSON-over-stdout dispatch contract established by `annotation/fm_client.py` is the reusable part; the multi-stage-with-disk-checkpoints orchestration inside the worker script is new.

**Primary recommendation:** For FM-01, keep `annotation/fm_client.py`'s subprocess contract exactly as-is and modify only `run_scgpt_embed.py`'s `_match_and_aggregate()` to compute a proper k-nearest-neighbor vote-fraction confidence (this is a small, local diff, not a rewrite) — then re-run the `bio_fm_smoke` test to confirm it still passes and document the checkpoint/reference reproducibility gap. For FM-02, build a new `geneformer_worker/` (venv + `run_geneformer_perturb.py`) mirroring `bio_fm_worker/`'s structure, a new `perturbation/geneformer_client.py` mirroring `annotation/fm_client.py`'s subprocess-shim shape, and pick the smallest available checkpoint (`Geneformer-V1-10M`) for CPU-feasible smoke testing — do not clone the full multi-checkpoint HF repo; use a sparse/selective fetch of one checkpoint directory.

## Existing Implementation State (read this before planning any tasks)

| File | Status | Notes |
|------|--------|-------|
| `annotation/fm_client.py` | **Already implements real scGPT subprocess call.** `call_scgpt_annotate()` shells out to `bio_fm_worker/.venv/bin/python bio_fm_worker/run_scgpt_embed.py`, parses JSON from stdout, raises `RuntimeError` on non-zero exit/timeout. | Also contains `ensure_worker_compatible_h5ad()` — a required pre-write step for any `.h5ad` crossing into the worker (pandas 3.0/anndata 0.13 main-venv vs. anndata 0.10.9 worker-venv on-disk incompatibility). Any new Geneformer client must call this too if it writes `.h5ad` for its worker. |
| `bio_fm_worker/run_scgpt_embed.py` | **Already calls the real, verified `scgpt.tasks.embed_data()` API.** Confidence is currently top-1 cosine similarity of the majority-vote label per cluster — NOT the k-NN vote-fraction FM-01 requires. | This is the file to modify for FM-01, not rewrite. See Pattern 1 below for the concrete diff shape. |
| `annotation/pipeline.py::annotate()` | Calls `call_scgpt_annotate()` inside a bare `try/except Exception: fm_calls = []` — any FM-side failure (missing checkpoint, path issue, timeout) is **silently swallowed**, no error surfaced to the summary or the researcher. | This silent-degradation behavior is very likely why the roadmap/PROJECT.md still describe this as a "stub" from the product's point of view even though the underlying call is real. Consider whether FM-01's plan should surface a distinguishable "fm_error" field instead of an empty list, so a broken pipeline doesn't look identical to "no scGPT signal." |
| `bio_fm_worker/checkpoints/`, `bio_fm_worker/reference/*.h5ad`, `*.scgpt_emb.npy` | **All gitignored.** Present locally on this machine (checkpoint is 205 MB, `best_model.pt`), but do not exist on a clean checkout. | FM-01's plan should explicitly address reproducibility: either document the manual acquisition steps (already in `bio_fm_worker/README.md`) as a required setup step, or add an automated fetch attempt (as Phase 4's 04-05 plan did) re-verified for this phase. |
| `perturbation/model.py`, `perturbation/pipeline.py`, `perturbation/summary.py` | Existing PERT-01 linear-additive model. Returns a full per-gene **expression vector** (`PerturbationCall.predicted_expression: list[float]`), one call per target gene. | FM-02's Geneformer output (a ranked gene list by cosine shift) is a **structurally different shape** — not a drop-in replacement for `PerturbationCall`. Planner must decide: extend `PerturbationSummary` with a new optional field, or add a parallel `GeneformerCall`/`GeneformerSummary` dataclass. Do not force Geneformer's output into `predicted_expression`. |
| `agent/tools.py` | `predict_perturbation_tool` takes `{name, target_gene}` (version optional, read via `.get()` per the established "optional args omitted from dict schema" pattern — see Pitfall 2 note in that file). No `method`/`model` selector param exists yet. | FM-02 needs either a new tool (e.g. `predict_perturbation_geneformer`) or a `method` arg added to the existing tool schema. Mirror `annotate_cell_type_tool`'s pattern (single tool, both FM and baseline always returned) only if Geneformer's runtime cost allows it to run unconditionally — given the 4-step pipeline can take hours (see Pitfall 3 below), a **separate, explicitly-invoked tool** is almost certainly correct here, unlike scGPT/decoupler which are cheap enough to always both run. |
| Geneformer anywhere in the repo | **Does not exist yet.** No `geneformer_worker/`, no `perturbation/geneformer_client.py`. Only prior-research mentions in `.planning/research/{STACK,PITFALLS}.md` (written 2026-09-16, before any Geneformer code existed). | This is genuinely new-build work, not verify-and-harden work. |

## Standard Stack

### Core (scGPT side — already installed, verify don't reinstall)

| Library | Version (verified live in `bio_fm_worker/.venv`) | Purpose | Why Standard |
|---------|---------|---------|--------------|
| `scgpt` | 0.2.4 | Zero-shot cell embedding via `scgpt.tasks.embed_data()` | Already the project's chosen cell-type-annotation FM (Phase 4 decision) |
| `torch` | 2.3.0 (pinned) | scGPT backend | Must stay pinned — paired against `torchtext==0.18.0`'s compiled ABI; upgrading torch alone reintroduces the 2026-09-07 `dlopen` crash |
| `torchtext` | 0.18.0 (pinned) | scGPT's `GeneVocab` wrapper | Unmaintained upstream since 2023; this exact pin is non-negotiable, not "whatever resolves" |
| `anndata` | 0.10.9 (ceiling, forced by Python 3.9) | AnnData I/O inside the worker | `anndata>=0.11` requires Python ≥3.10, which scGPT's own transitive pins (`scvi-tools<1.0`) can't satisfy |
| Python | 3.9.6 (`bio_fm_worker/.venv`) | Worker interpreter | Isolated from the main repo's `>=3.12` floor; fully self-contained venv |

### Core (Geneformer side — new install required)

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| `geneformer` | git `main`/current release, `ctheodoris/Geneformer` on Hugging Face | Tokenization, embedding extraction, in-silico perturbation, perturbation stats | Official reference implementation; the only credible non-NVIDIA-account-gated source (see Alternatives Considered) |
| `torch` (Geneformer venv) | Current stable 2.x (resolved by `pip install .`, no pin in `setup.py`) | Geneformer backend | No `torchtext` dependency in this venv — no ABI conflict risk, unlike scGPT's venv |
| `transformers`, `datasets`, `peft`, `pyarrow` | Whatever `pip install .` resolves (`setup.py` has no version pins) | HF-stack dependencies Geneformer is built on | Required transitively; do not hand-pin unless a conflict actually appears |
| Python | 3.10.x — confirmed present at `/opt/homebrew/bin/python3.10` (v3.10.14) on this machine | Geneformer worker interpreter | `setup.py: python_requires=">=3.10"` — incompatible with `bio_fm_worker/.venv`'s Python 3.9.6, hence the second isolated venv |

### Supporting

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `numpy` | already present in both venvs | Cosine similarity / k-NN vote-fraction computation | scGPT's `_cosine_similarity_matrix` already exists in `run_scgpt_embed.py`; extend, don't replace |
| `sklearn.neighbors.NearestNeighbors` (optional) | whatever resolves | Alternative to the hand-rolled cosine-similarity-matrix + `argpartition` approach for k-NN lookup | Only worth adding if the reference set grows large enough that a brute-force `a @ b.T` matrix becomes a memory/perf problem; at reference sizes used here (~3000 cells) the existing dense matrix approach is simpler and already correct |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Official `ctheodoris/Geneformer` (git clone) | `helical` (PyPI-installable wrapper library that includes a Geneformer model interface) | Could not fully verify `helical`'s in-silico-perturbation support during this research (page fetch failed) — LOW confidence, don't adopt without further verification. The project's own prior STACK.md research already chose the official repo; there's no evidence-based reason to switch. |
| Official `ctheodoris/Geneformer` | NVIDIA BioNeMo's Geneformer re-implementation | Requires an NVIDIA NGC account; not the reference implementation; explicitly rejected in this project's own prior STACK.md "What NOT to Add" table |
| `Geneformer-V1-10M` (smallest checkpoint, recommended default here) | `Geneformer-V2-104M` / `Geneformer-V2-316M` | V2 models are larger (trained on ~104M cells, Dec 2024) and likely more accurate, but a 316M-parameter transformer running a 4-step CPU pipeline (tokenize → embed → perturb-forward-pass-per-gene → stats) on this project's CPU-only self-hosted pattern would make even a smoke test impractically slow. Use V1-10M for development/smoke-testing; document V2 as a future upgrade path once latency is measured. |
| k-NN vote-fraction (this phase's target) | Top-1 cosine similarity (current implementation) | Top-1 gives no sense of how consistent the neighborhood is — a cell whose single nearest neighbor happens to agree but whose next 9 neighbors disagree looks identical to a cell in the dead center of a reference cluster. Vote-fraction over k neighbors is the standard fix (see Pattern 1). |

**Installation (Geneformer worker — new):**
```bash
python3.10 -m venv geneformer_worker/.venv
git lfs install
# Prefer a shallow/selective clone: the full HF repo contains multiple
# multi-GB checkpoint directories (V1-10M, V2-104M, V2-104M_CLcancer,
# V2-316M) under git-lfs. Cloning all of them is unnecessary and slow.
GIT_LFS_SKIP_SMUDGE=1 git clone https://huggingface.co/ctheodoris/Geneformer geneformer_worker/src
cd geneformer_worker/src
git lfs pull --include="Geneformer-V1-10M/*"   # only the smallest checkpoint
cd -
geneformer_worker/.venv/bin/pip install -e geneformer_worker/src
geneformer_worker/.venv/bin/python -c "import geneformer; print('geneformer OK')"
```

## Architecture Patterns

### Recommended Project Structure (additions only — existing structure is correct and should be mirrored, not replaced)

```
bio_fm_worker/            # UNCHANGED structurally — scGPT, Python 3.9.6
├── .venv/
├── run_scgpt_embed.py    # MODIFY: _match_and_aggregate() -> k-NN vote-fraction
├── checkpoints/scGPT_human/
└── reference/reference.h5ad

geneformer_worker/         # NEW — Geneformer, Python 3.10.x, mirrors bio_fm_worker/'s shape
├── .venv/
├── src/                    # git-cloned ctheodoris/Geneformer (package + one checkpoint dir)
├── run_geneformer_perturb.py   # NEW CLI script; 4-step pipeline orchestrator
└── README.md               # mirror bio_fm_worker/README.md's "how it was created" convention

annotation/
└── fm_client.py            # UNCHANGED — already correct

perturbation/
├── fm_client.py             # NEW (or geneformer_client.py) — subprocess shim mirroring annotation/fm_client.py
├── model.py                 # UNCHANGED — linear additive model stays as-is
├── pipeline.py               # MODIFY or add sibling entrypoint for Geneformer path
└── summary.py                 # MODIFY — add a dataclass shape for ranked-gene-by-cosine-shift output
```

### Pattern 1: k-NN Vote-Fraction Confidence (FM-01)

**What:** Replace top-1 cosine-similarity confidence with a weighted-k-nearest-neighbor vote fraction: for each query cell, find its `k` nearest reference cells by cosine similarity in scGPT embedding space, take the majority cell-type label among those `k` neighbors, and set confidence = (count of neighbors voting for the majority label) / k. This is the standard technique used by scArches' WKNN label-transfer classifier and popV's consensus voting for single-cell reference mapping (MEDIUM-HIGH confidence — cross-referenced against scArches/HLCA docs and the popV Nature Genetics 2024 paper), not something to invent from scratch.

**When to use:** Directly replaces `run_scgpt_embed.py::_match_and_aggregate()`'s current top-1 `sims.argmax(axis=1)` logic.

**Example (concrete diff shape against the current file):**
```python
# Source: existing bio_fm_worker/run_scgpt_embed.py, modified per this research
def _match_and_aggregate(query, query_embed, reference, reference_embed, reference_dataset, k=15):
    """k-NN vote-fraction match per query cell, aggregated to one call per leiden group."""
    sims = _cosine_similarity_matrix(query_embed, reference_embed)  # (n_query, n_ref)
    k = min(k, sims.shape[1])
    # Top-k neighbor indices per query cell (unsorted within the top-k is fine —
    # only the label counts matter, not the order).
    topk_idx = np.argpartition(-sims, kth=k - 1, axis=1)[:, :k]

    ref_cell_type = reference.obs["cell_type"].to_numpy()
    ref_ontology_id = reference.obs["cell_type_ontology_term_id"].to_numpy()

    calls = []
    for cluster in sorted(query.obs["leiden"].unique(), key=str):
        mask = (query.obs["leiden"] == cluster).to_numpy()
        if not mask.any():
            continue
        # Per-cell majority label + per-cell vote fraction, then aggregate to the cluster.
        cell_labels, cell_confidences, cell_ontology_ids = [], [], []
        for row in np.nonzero(mask)[0]:
            neighbor_labels = ref_cell_type[topk_idx[row]]
            values, counts = np.unique(neighbor_labels, return_counts=True)
            majority_label = values[counts.argmax()]
            vote_fraction = counts.max() / k
            cell_labels.append(majority_label)
            cell_confidences.append(vote_fraction)
            majority_mask = neighbor_labels == majority_label
            cell_ontology_ids.append(ref_ontology_id[topk_idx[row]][majority_mask][0])

        values, counts = np.unique(cell_labels, return_counts=True)
        majority_label = values[counts.argmax()]
        group_mask = np.array(cell_labels) == majority_label
        confidence = float(np.mean(np.array(cell_confidences)[group_mask]))
        ontology_term_id = np.array(cell_ontology_ids)[group_mask][0]

        calls.append({
            "cluster": str(cluster),
            "label": str(majority_label),
            "confidence": confidence,   # now a k-NN vote fraction, not a raw cosine similarity
            "reference_dataset": reference_dataset,
            "ontology_term_id": None if ontology_term_id is None else str(ontology_term_id),
        })
    return calls
```
`confidence` stays in `[0.0, 1.0]` (a fraction of `k`), so `AnnotationCall`'s existing `confidence: float` field and the existing `0.0 <= call["confidence"] <= 1.0` test assertion in `tests/test_bio_fm_integration.py` need no schema change — only the underlying computation changes.

### Pattern 2: scGPT `embed_data()` — verified live API shape (not from training data)

**What:** Directly introspected from the actually-installed `scgpt==0.2.4` in `bio_fm_worker/.venv` via `inspect.signature`/`inspect.getsource` during this research session (not recalled from training data, not re-derived from docs).

```
(adata_or_file: Union[AnnData, str, PathLike], model_dir: Union[str, PathLike],
 gene_col: str = 'feature_name', max_length=1200, batch_size=64,
 obs_to_save: Optional[list] = None, device: Union[str, torch.device] = 'cuda',
 use_fast_transformer: bool = True, return_new_adata: bool = False) -> AnnData
```

Confirmed source-level behavior (source: live `bio_fm_worker/.venv` install):
- Requires `model_dir/vocab.json`, `model_dir/args.json`, `model_dir/best_model.pt` — exactly what `bio_fm_worker/checkpoints/scGPT_human/` already contains.
- Internally does `adata = adata[:, adata.var["id_in_vocab"] >= 0]` — **filters genes (columns), not cells (rows)**. Cell count/order is preserved; only unmatched genes are dropped before the forward pass. This means `embedded.obsm["X_scGPT"]` always has one row per input cell, correctly aligned with `query.obs["leiden"]` — the assumption `run_scgpt_embed.py` already makes is correct.
- `device="cuda"` (the default) silently falls back to CPU if CUDA is unavailable, printing a `WARNING: CUDA is not available` line to **stdout** (not stderr) — this is exactly why `call_scgpt_annotate()` has to scan stdout for the JSON line from the end rather than assuming stdout is pure JSON.
- `use_fast_transformer=True` (the default) requires `flash_attn`; the `TransformerModel` internals fall back to plain PyTorch attention if it's not installed (already confirmed working in this environment — no `flash_attn` is installed).
- `return_new_adata=False` (the default, and what `run_scgpt_embed.py` uses) writes embeddings to `adata.obsm["X_scGPT"]` and returns the (gene-filtered) `AnnData` — it does NOT return a bare embedding matrix. `run_scgpt_embed.py`'s `_embed()` already extracts `.obsm["X_scGPT"]` correctly.
- Cell embedding mode is hardcoded internally to `cell_embedding_mode="cls"` (CLS-token pooling) — not configurable via `embed_data()`'s public parameters.

**Conclusion for planning:** No code change is needed to `_embed()` itself. FM-01's plan should include a task that re-runs this exact introspection (`inspect.signature`/`inspect.getsource` against the live venv) as its first, cheap verification step before touching `run_scgpt_embed.py` — per the roadmap's explicit success-criterion wording — even though this research session already did it and found no drift.

### Pattern 3: Geneformer's four-step pipeline — verified class/method shapes (readthedocs, live-fetched)

Verified live against `geneformer.readthedocs.io` (current pages, fetched this session) and the official `ctheodoris/Geneformer` HF repo file listing — MEDIUM-HIGH confidence (official docs, not training-data recall; some class defaults show a placeholder `FILEPATH` in the docs rather than a literal value, meaning those defaults resolve to package-bundled resource files at import time — confirm the literal resolved path against the installed package once `geneformer_worker/.venv` exists, exactly as scGPT's API was reconfirmed above).

**Step 1 — Tokenize:**
```python
# Source: https://geneformer.readthedocs.io/en/latest/geneformer.tokenizer.html
from geneformer import TranscriptomeTokenizer

tk = TranscriptomeTokenizer(
    custom_attr_name_dict=None,
    nproc=1,
    model_input_size=4096,
    model_version="V1",              # match checkpoint: "V1" for Geneformer-V1-10M
    # gene_median_file / token_dictionary_file / gene_mapping_file default to
    # package-bundled resources matching model_version -- do not hand-supply
    # unless a non-default token dictionary is genuinely needed.
)
tk.tokenize_data(
    data_directory="path/to/h5ad_dir",   # directory containing one or more .h5ad files
    output_directory="path/to/tokenized",
    output_prefix="query",
    file_format="h5ad",
)
```
**Required `adata` shape before this call:** `adata.var["ensembl_id"]` (exact column name) and `adata.obs["n_counts"]` (exact column name; total raw counts per cell). No error is raised if either is missing/wrong — genes simply fail to tokenize silently (see Pitfall 4).

**Step 2 — Extract baseline embeddings:**
```python
# Source: https://geneformer.readthedocs.io/en/latest/geneformer.emb_extractor.html
from geneformer import EmbExtractor

extractor = EmbExtractor(model_type="Pretrained", emb_mode="cls", model_version="V1")
extractor.extract_embs(
    model_directory="path/to/Geneformer-V1-10M",
    input_data_file="path/to/tokenized/query.dataset",
    output_directory="path/to/embs",
    output_prefix="query_emb",
)
```

**Step 3 — In-silico perturb:**
```python
# Source: https://geneformer.readthedocs.io/en/latest/geneformer.in_silico_perturber.html
from geneformer import InSilicoPerturber

isp = InSilicoPerturber(
    perturb_type="delete",            # gene knockdown/knockout, matches PERT-01's "target gene" framing
    genes_to_perturb=[target_ensembl_id],   # a list, even for a single gene
    emb_mode="cell_and_gene",          # need gene-level output for a "ranked gene list by cosine shift"
    model_type="Pretrained",
    model_version="V1",
    forward_batch_size=100,            # reduce for CPU/low-memory hosts
)
isp.perturb_data(
    model_directory="path/to/Geneformer-V1-10M",
    input_data_file="path/to/tokenized/query.dataset",
    output_directory="path/to/perturb_out",
    output_prefix="query_perturb",
)
```
This writes batched pickle files to `output_directory`, not a return value — genuine disk I/O between steps, not an in-memory call chain.

**Step 4 — Aggregate + rank:**
```python
# Source: https://geneformer.readthedocs.io/en/latest/geneformer.in_silico_perturber_stats.html
from geneformer import InSilicoPerturberStats

stats = InSilicoPerturberStats(
    mode="aggregate_gene_shifts",      # per-gene cosine-shift aggregation, not goal-state/mixture-model modes
    genes_perturbed=[target_ensembl_id],
    model_version="V1",
)
result_df = stats.get_stats(
    input_data_directory="path/to/perturb_out",
    null_dist_data_directory=None,
    output_directory="path/to/stats_out",
    output_prefix="query_stats",
)
```
Output columns confirmed from official docs: `Gene`, `Gene_name`, `Ensembl_ID`, `N_Detections`, `Cosine_sim_mean`, `Cosine_sim_stdev`, plus mode-specific columns (`Shift_to_goal_end`, `Test_avg_shift`, etc. only apply to other `mode` values). **The library itself does not pre-rank genes** — sort `result_df` by `Cosine_sim_mean` (descending, by magnitude of shift) in the worker script to produce the "ranked gene list by cosine shift" FM-02 requires. This sort step is new code the worker script must implement; it is not something `InSilicoPerturberStats` does automatically.

### Anti-Patterns to Avoid

- **Treating `InSilicoPerturber.perturb_data()` as a single blocking call inside a fast subprocess timeout:** it can run for hours on CPU (batched forward pass over the full token sequence per perturbed gene, across all query cells). Follow `annotation/fm_client.py`'s existing precedent of a *generous* timeout (that file already uses 3600s/1 hour for scGPT's one-time reference embedding) — Geneformer's 4-step pipeline likely needs a longer ceiling still, or per-step timeouts if the worker script reports progress between steps.
- **Co-locating scGPT and Geneformer in one venv "since it's just another model":** already identified as a failure mode in this project's own prior research (PITFALLS.md Pitfall 11) — `scgpt`'s `torch==2.3.0`+`torchtext==0.18.0` pin and Geneformer's modern, unpinned `torch`+`transformers` stack are mutually incompatible in a single environment. Keep the two `.venv`s fully separate, exactly as `bio_fm_worker/` and the new `geneformer_worker/` are laid out above.
- **Assuming the query dataset already has Ensembl IDs:** see Don't Hand-Roll and Pitfall 4 below.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|--------------|-----|
| Gene-symbol → Ensembl-ID mapping for Geneformer input | A custom `pyensembl`/`mygene` lookup table or API-call-based mapper | `adata.var["gene_ids"]` — **already populated** for any dataset ingested through this project's existing MTX/`.h5` ingest path. Confirmed directly from the installed `scanpy` source (`scanpy/readwrite.py`): `sc.read_10x_mtx(..., var_names="gene_symbols")` (used by `ingest/loaders.py`) sets `adata.var["gene_ids"]` from the raw 10x `features.tsv.gz` Ensembl-ID column, and `sc.read_10x_h5()` does the same via its own internal `var_dict["gene_ids"]`. | For MTX/`.h5`-sourced datasets, the Geneformer worker only needs to alias `adata.var["gene_ids"]` → `adata.var["ensembl_id"]` (rename, and strip any `.N` version suffix) — no external mapping service, network call, or bundled static mapping file is needed. This does NOT hold for arbitrary `.h5ad` uploads (DATA-02) or census-fetched data (DATA-01) — validate presence of a usable Ensembl-ID-shaped column for those paths and fail loudly (per the roadmap's explicit "validated... before inference runs" wording) rather than silently falling back to symbols. |
| k-NN classification confidence | A hand-rolled probabilistic model or heuristic score | Vote-fraction over `k` nearest neighbors in embedding space (Pattern 1) | This is the exact metric used by scArches' WKNN label-transfer classifier and popV's consensus cell-type voting (published, peer-reviewed methods) — not a bespoke invention. Reuse the concept even though the exact code is small enough to write locally (no library dependency needed at this reference-set scale). |
| Cell Ontology metadata for annotation | A hand-built cell-type-to-ontology-ID mapping | `cellxgene_census`'s schema-enforced `cell_type_ontology_term_id` field, already wired into `annotation/reference.py` | Already solved in Phase 4 (04-RESEARCH.md's Don't Hand-Roll section) — no new work needed here, just confirming FM-01 doesn't regress it. |
| Ranking genes by perturbation effect | A custom cosine-distance-and-sort implementation reimplementing what Geneformer already computes internally | `InSilicoPerturberStats(mode="aggregate_gene_shifts").get_stats()`'s `Cosine_sim_mean` column, then sort in the worker script | The shift computation itself (embedding before vs. after in-silico perturbation) is exactly what `InSilicoPerturberStats` exists to do — only the final `sort_values()` call is new code, not the shift computation. |

**Key insight:** Both halves of this phase share one theme — the hard numerical/statistical work (embedding, perturbation-effect measurement, label-transfer voting) has an established, verifiable library or published-method answer. The actual engineering work in this phase is subprocess plumbing, data-shape validation (Ensembl IDs, gene_col alignment), and output-contract design (new dataclass shapes) — not new modeling code.

## Common Pitfalls

### Pitfall 1: The scGPT "stub" is really a reproducibility gap, not a missing feature
**What goes wrong:** A plan that assumes `annotate_cell_type_tool` needs new scGPT-calling code will end up re-deriving code that already exists and was already verified once (Phase 4, 2026-09-08).
**Why it happens:** `bio_fm_worker/checkpoints/`, `bio_fm_worker/reference/*.h5ad`, and the cached `*.scgpt_emb.npy` are all gitignored — so on a fresh checkout (or in CI) the pipeline silently returns `fm_calls: []` via `annotation/pipeline.py`'s broad `except Exception`, which *looks* exactly like a stub even though the code path is real.
**How to avoid:** Confirm (this research session already did) whether the checkpoint/reference/cache exist locally before assuming they need to be rebuilt from scratch; if they exist, the plan's actual work is the confidence-metric change (Pattern 1) plus deciding whether/how to surface FM-side failures distinctly from "ran successfully with an empty result."
**Warning signs:** A plan that includes tasks like "write `run_scgpt_embed.py`" or "install `scgpt`" from scratch — both already done.

### Pitfall 2: Geneformer's Ensembl ID requirement fails silently, not loudly
**What goes wrong:** `TranscriptomeTokenizer` does not raise an error on a missing/wrong `adata.var["ensembl_id"]` column or on unmatched IDs — it just tokenizes 0 genes for that cell, producing a degenerate but exception-free result. `InSilicoPerturber`/`InSilicoPerturberStats` will then run "successfully" on empty/near-empty token sequences and produce all-zero or near-identical cosine shifts that look like a valid, if uninteresting, result.
**Why it happens:** The tokenizer's vocabulary is keyed by unversioned Ensembl IDs; real-world Ensembl IDs sometimes carry `.N` version suffixes (`ENSG00000141510.21`) that don't match the vocabulary's `ENSG00000141510`. Confirmed against the official Geneformer tokenizer docs (HIGH confidence, matches this project's own prior PITFALLS.md Pitfall 17 finding, independently corroborated here).
**How to avoid:** Before calling `tokenize_data()`, explicitly: (1) confirm `adata.var["ensembl_id"]` exists (aliasing from `adata.var["gene_ids"]` for MTX/`.h5`-sourced data per the Don't Hand-Roll entry above), (2) strip `.N` suffixes on both the data and, if a custom `token_dictionary_file` is ever used, the vocabulary, (3) compute and report the match rate (`count(ensembl_id in vocab) / total genes`) as part of the tool's output, and (4) treat a low match rate (e.g. <50%, following this project's own prior PITFALLS.md recommendation) as a hard tool error, not a silently-returned "result."
**Warning signs:** Cosine shifts that are all `0.0` or suspiciously identical across genes; `len(tokenized_dataset)` shows correct cell count but each row has 0-1 `input_ids`.

### Pitfall 3: The four-step pipeline has multi-hour, disk-I/O-coupled stages — don't call it synchronously from the FastAPI event loop
**What goes wrong:** `InSilicoPerturber.perturb_data()` writes batched pickle files that `InSilicoPerturberStats.get_stats()` reads back from disk — a failure between the two steps can leave orphaned partial-batch pickle files that corrupt a retry's aggregation.
**Why it happens:** This is a genuine multi-stage pipeline with real wall-clock cost (tokenization alone can take 10-30 min for tens of thousands of cells; the perturbation forward pass is the most expensive step), not a single model call — the official Geneformer examples show all four steps in one notebook cell with no indication of this cost, which invites treating it like one function call.
**How to avoid:** Whatever subprocess script implements this (`geneformer_worker/run_geneformer_perturb.py`) should run inside a single subprocess call from `perturbation`'s client (matching `call_scgpt_annotate()`'s existing pattern of one subprocess covering the whole operation with one generous timeout, not four separate FastAPI-triggered stages) — but that subprocess's *internal* timeout budget must be sized for hours, not the seconds/minutes appropriate for scGPT annotation. If this tool is invoked directly from the agent loop (not `asyncio.to_thread()`ed), it will block the whole session; consider whether this call should be async-dispatched the same way DATA-01's census fetch already is (per STATE.md's existing `asyncio.to_thread()` pattern for blocking I/O).
**Warning signs:** No progress feedback for the entire duration of a Geneformer call; leftover pickle directories after a failed run.

### Pitfall 4: Geneformer output shape does not fit the existing `PerturbationCall`/`PerturbationSummary` contract
**What goes wrong:** Trying to shoehorn a ranked-gene-by-cosine-shift result into `PerturbationCall.predicted_expression: list[float]` (a full per-gene expression vector) either silently loses information (ranking discarded) or produces a nonsensical vector.
**Why it happens:** PERT-01's linear model and the roadmap's explicit framing for FM-02 ("explicitly distinct from the linear model's expression-vector output") are fundamentally different output types by design — a expression-vector regression vs. a top-K ranked list of genes by embedding-shift magnitude.
**How to avoid:** Design a new, explicit dataclass (e.g. `GeneformerPerturbationCall` with fields like `target_gene`, `ranked_genes: list[{gene, cosine_shift}]`, `match_rate: float`) rather than reusing `PerturbationCall` unmodified. Whether it lives in `perturbation/summary.py` alongside the existing contract or as a new module is a planning decision, not a research one — but the shape must not collapse to `predicted_expression`.
**Warning signs:** A plan task that says "populate `predicted_expression` from Geneformer output."

### Pitfall 5: Subprocess default paths are CWD-relative, not repo-root-anchored
**What goes wrong:** `annotation/pipeline.py::annotate()`'s defaults (`worker_python="bio_fm_worker/.venv/bin/python"`, etc.) only resolve correctly if the calling process's current working directory is the repo root. No `Path(__file__).parent`-anchored resolution exists.
**Why it happens:** This has apparently worked so far because every test/run happens to be invoked from the repo root, but it's a latent fragility, particularly relevant for Docker deployment (Phase 14) and for any Geneformer client that copies this pattern.
**How to avoid:** Not necessarily an in-scope fix for Phase 13, but worth flagging in the plan: if a new `perturbation/geneformer_client.py` mirrors this pattern, at minimum keep the same relative-path convention consistently (don't mix CWD-relative and `__file__`-relative resolution across the two clients) so Phase 14's Docker work has one consistent pattern to fix, not two different ones.
**Warning signs:** Works locally, fails when invoked from a different working directory (e.g. a systemd service, a Docker `WORKDIR`, or a test runner with a different `cwd`).

## Code Examples

See Pattern 1 (k-NN vote fraction diff), Pattern 2 (verified `scgpt.tasks.embed_data()` full source/behavior), and Pattern 3 (Geneformer four-step pipeline calls) above — all code there is either directly copied from the live-introspected installed package (scGPT) or built from officially-documented, live-fetched class signatures (Geneformer), not recalled from training data.

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|-------------------|---------------|--------|
| scGPT torch/torchtext ABI broken (`import scgpt` crashes) | Fixed by pinning `torch==2.3.0` alongside the existing `torchtext==0.18.0` | 2026-09-07 (this project, Phase 4) | Already resolved; no action needed in Phase 13 beyond confirming it still holds (it does — reconfirmed live in this session) |
| Geneformer V1 (10M params, trained on ~30M cells, 2021) | Geneformer V2 (104M/316M params, trained on ~104M cells, Dec 2024) | Dec 2024 (upstream) | V2 is the "current" recommended model upstream, but its size makes CPU-only self-hosted inference (this project's established pattern) much slower; V1 remains the pragmatic choice for this project's compute profile until latency is measured, exactly as scGPT's own CPU latency was empirically measured (not assumed) in Phase 4 |
| scGPT annotation confidence = top-1 cosine similarity | k-NN vote-fraction (this phase's target, matching scArches/popV precedent) | N/A (this phase) | More honest confidence signal — a single lucky top match no longer looks identical to a cell deep in a well-separated reference cluster |

**Deprecated/outdated:**
- `torchtext` itself: archived/unmaintained upstream since 2023. It is not "deprecated in favor of X" — there is no replacement; the pin (`torchtext==0.18.0` matched to `torch==2.3.0`) is a permanent constraint on the scGPT venv, not a temporary one to eventually upgrade away from.

## Open Questions

1. **Does re-verifying `scgpt.tasks.embed_data()`'s API shape (roadmap's explicit success-criterion #1) require anything beyond what this research already did?**
   - What we know: This research session directly introspected the live-installed `scgpt==0.2.4` package's `embed_data()` signature and full source and confirmed it matches `run_scgpt_embed.py`'s existing assumptions exactly.
   - What's unclear: Whether the phase's plan should still include an explicit "re-run this verification" task as a checkpoint (defensive, in case the venv is rebuilt or the package is upgraded between now and plan execution) or treat this research as sufficient.
   - Recommendation: Include a cheap, automatable verification task (`inspect.signature`/`inspect.getsource` against the live venv, same as this research did) as Task 1 of the FM-01 plan regardless — it costs seconds and directly satisfies the roadmap's literal wording ("verified... before the worker script is written").

2. **Should FM-01's `annotate()` stop silently swallowing scGPT failures?**
   - What we know: The current `except Exception: fm_calls = []` in `annotation/pipeline.py` makes a genuinely broken pipeline indistinguishable from "ran fine, no FM signal" in the returned summary.
   - What's unclear: Whether changing this is in FM-01's scope or a separate reliability concern (this project's v1.0 REQUIREMENTS.md already lists `RELIA-01`/`RELIA-02` as deferred v2 work covering exactly this kind of tool-output self-check/audit visibility).
   - Recommendation: At minimum, keep an internal record of *why* the FM call failed (log it, even if the returned summary still shows an empty `fm_calls` list) so a broken checkpoint path doesn't look identical to "the FM genuinely returned nothing" during phase verification.

3. **What checkpoint size should the Geneformer smoke test target, and how should the phase-gate verification for FM-02 be structured given multi-hour runtimes?**
   - What we know: Phase 4's own real-checkpoint verification for scGPT used a `checkpoint:human-verify` gate (a blocking manual step) precisely because a real, multi-GB checkpoint download and real inference latency can't be fully automated/asserted in CI.
   - What's unclear: Whether Geneformer's smoke test should target a tiny synthetic fixture (fast, but risks not exercising the real disk-I/O-between-steps failure mode) or a small-but-real dataset (slower, more representative, closer to Phase 4's precedent).
   - Recommendation: Follow Phase 4's precedent directly — a `bio_fm_smoke`-style marker (or a new `geneformer_smoke` marker) excluded from the default fast-tier run, plus a `checkpoint:human-verify` gate for the one-time real checkpoint acquisition and a measured, recorded latency number, exactly as `04-05-PLAN.md` did for scGPT.

4. **Exact resolved default paths for `gene_median_file`/`token_dictionary_file`/`gene_mapping_file` in the installed Geneformer package.**
   - What we know: The readthedocs class signatures show these parameters defaulting to a `FILEPATH` placeholder (meaning the actual docs page didn't render the literal path — it resolves to a package-bundled resource file matched to `model_version`).
   - What's unclear: The literal resolved path/filename, and whether it needs to be passed explicitly when the worker script's CWD differs from the package's installed location.
   - Recommendation: Once `geneformer_worker/.venv` exists, run the same live-introspection technique used for scGPT in this research (`inspect.signature`, and if needed `inspect.getsource` on `TranscriptomeTokenizer.__init__`) to get the literal default paths before writing `run_geneformer_perturb.py` — do not assume the readthedocs placeholder text is usable as a literal value.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 8.x |
| Config file | `pyproject.toml` (`[tool.pytest.ini_options]`) |
| Quick run command | `uv run pytest tests/ -q -m "not live_llm and not bio_fm_smoke and not vcc_data and not census_data"` (confirmed green: 252 passed, 7 deselected, 23.8s, this session) |
| Full suite command | `uv run pytest tests/ -q` (includes marker-gated real-checkpoint/network tests; not run in CI) |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|---------------------|-------------|
| FM-01 | `run_scgpt_embed.py`'s `_match_and_aggregate()` produces a valid `[0,1]` k-NN vote-fraction confidence, not top-1 cosine similarity | unit | `uv run pytest tests/test_annotation_fm_client.py -x` (extend with a new unit test for the vote-fraction math against a small synthetic embedding matrix) | ❌ Wave 0 — new unit test needed for the vote-fraction function itself, isolated from the subprocess boundary |
| FM-01 | Real, unmocked scGPT annotation still returns plausible non-empty results with the new confidence metric | smoke (marked, excluded from fast tier) | `uv run pytest tests/test_bio_fm_integration.py -m bio_fm_smoke -x -v` | ✅ exists (`tests/test_bio_fm_integration.py`) — re-run against the modified worker script |
| FM-02 | Ensembl-ID validation rejects/flags gene-symbol-only input before tokenization | unit | `uv run pytest tests/test_perturbation_geneformer_client.py -x` (new file) | ❌ Wave 0 |
| FM-02 | Geneformer subprocess client parses/handles success and failure JSON contracts (mirrors `test_annotation_fm_client.py`'s mocked-subprocess pattern) | unit | `uv run pytest tests/test_perturbation_geneformer_client.py -x` | ❌ Wave 0 |
| FM-02 | Real, unmocked four-step Geneformer pipeline returns a ranked-by-cosine-shift gene list for a real checkpoint | smoke (new marker, excluded from fast tier), `checkpoint:human-verify` gate | `uv run pytest tests/test_geneformer_integration.py -m geneformer_smoke -x -v` (new file, new marker) | ❌ Wave 0 |

### Sampling Rate
- **Per task commit:** the quick run command above
- **Per wave merge:** the quick run command above (smoke-marked tests are inherently manual/checkpoint-gated, not part of automated wave verification, matching Phase 4's and Phase 5's own precedent)
- **Phase gate:** `checkpoint:human-verify` steps for both the scGPT confidence-metric re-verification and the Geneformer real-checkpoint smoke test, before `/gsd:verify-work` — mirroring `04-05-PLAN.md`'s Task 3 structure exactly

### Wave 0 Gaps
- [ ] `tests/test_annotation_fm_client.py` — needs a new unit test isolating the k-NN vote-fraction math (pure numpy, no subprocess) so it's covered by the fast tier even though the full integration remains `bio_fm_smoke`-gated
- [ ] New `geneformer_worker/` package skeleton + `.venv` — does not exist yet
- [ ] New `perturbation/geneformer_client.py` (or equivalently named) subprocess shim — mirror `annotation/fm_client.py`'s structure and its mocked-subprocess unit test pattern (`tests/test_annotation_fm_client.py`)
- [ ] New pytest marker `geneformer_smoke` (or reuse `bio_fm_smoke` if the planner decides one marker covering both real-FM-checkpoint tests is preferable) registered in `pyproject.toml`'s `markers` list
- [ ] New dataclass(es) for Geneformer's ranked-gene-by-cosine-shift output shape in `perturbation/summary.py` (or a new module)

## Sources

### Primary (HIGH confidence)
- Direct `inspect.signature`/`inspect.getsource` introspection of the live-installed `scgpt==0.2.4` package in this repo's own `bio_fm_worker/.venv` (this research session) — `scgpt.tasks.embed_data()` full signature and source
- Direct read of this repo's own `annotation/fm_client.py`, `annotation/pipeline.py`, `annotation/reference.py`, `annotation/summary.py`, `bio_fm_worker/run_scgpt_embed.py`, `bio_fm_worker/README.md`, `perturbation/model.py`, `perturbation/pipeline.py`, `perturbation/summary.py`, `agent/tools.py`, `agent/server.py`
- Direct read of this repo's own `.planning/research/STACK.md` and `.planning/research/PITFALLS.md` (project's prior milestone-level research, 2026-09-16)
- Direct `git log` of `annotation/fm_client.py`/`bio_fm_worker/run_scgpt_embed.py`/`bio_fm_worker/README.md` confirming commit `8e500d7` ("complete bio_fm_smoke gate — real scGPT end-to-end verified", 2026-09-08) and reading `.planning/phases/04-bio-fm-cell-type-annotation/04-05-PLAN.md`
- Direct `git ls-files`/`.gitignore` check confirming `bio_fm_worker/checkpoints/`, `*.h5ad`, `*.scgpt_emb.npy` are gitignored (not reproducible on clean checkout)
- Direct `curl https://pypi.org/pypi/geneformer/json` — 404, confirming no PyPI package exists (contradicts a WebSearch AI-summary claim; do not trust that claim)
- Direct `which python3.10` / `python3.10 --version` on this machine — confirms Python 3.10.14 available at `/opt/homebrew/bin/python3.10`
- Direct read of installed `scanpy`'s `readwrite.py` source (this repo's main `.venv`) confirming `sc.read_10x_mtx()`/`sc.read_10x_h5()` populate `adata.var["gene_ids"]` with Ensembl IDs even when `var_names="gene_symbols"`
- https://geneformer.readthedocs.io/en/latest/geneformer.tokenizer.html — `TranscriptomeTokenizer` constructor, `tokenize_data()` signature, required `adata.var["ensembl_id"]`/`adata.obs["n_counts"]` columns (live-fetched this session)
- https://geneformer.readthedocs.io/en/latest/geneformer.emb_extractor.html — `EmbExtractor` constructor and `extract_embs()` signature (live-fetched this session)
- https://geneformer.readthedocs.io/en/latest/geneformer.in_silico_perturber.html — `InSilicoPerturber` constructor, `perturb_data()` signature, `emb_mode`/`perturb_type` options (live-fetched this session)
- https://geneformer.readthedocs.io/en/latest/geneformer.in_silico_perturber_stats.html — `InSilicoPerturberStats` constructor, `get_stats()` signature, output columns and `mode` options (live-fetched this session)
- https://huggingface.co/ctheodoris/Geneformer — installation instructions, checkpoint directory listing (`Geneformer-V1-10M`, `Geneformer-V2-104M`, `Geneformer-V2-104M_CLcancer`, `Geneformer-V2-316M`) (live-fetched this session)

### Secondary (MEDIUM confidence)
- WebSearch results on scArches WKNN / popV consensus voting for cell-type label-transfer uncertainty, cross-referenced against scArches/HLCA official docs and the popV Nature Genetics 2024 paper — supports the k-NN vote-fraction confidence design as an established method, not an invention
- WebSearch results on Geneformer `InSilicoPerturber` `emb_mode="gene"`/cosine-shift behavior, cross-referenced against the readthedocs pages fetched directly above

### Tertiary (LOW confidence — flagged, not relied upon)
- WebSearch AI-summary claim that a `geneformer` PyPI package exists — **directly contradicted** by a live `pypi.org` API 404 in this session; do not trust this claim
- `helical` (PyPI) as a simplified Geneformer wrapper alternative — page fetch failed during this research, could not verify feature parity (in-silico perturbation support specifically); not adopted, flagged only as a documented-but-unverified alternative

## Metadata

**Confidence breakdown:**
- scGPT standard stack/API shape: HIGH — directly introspected from the live-installed package in this repo, not recalled or re-derived from docs
- Geneformer standard stack/API shape: HIGH-MEDIUM — official readthedocs pages fetched live this session (HIGH for signatures/class names), MEDIUM for exact default-resource-file resolution behavior (flagged as Open Question 4, needs live re-verification once the venv exists, exactly as scGPT's was)
- Architecture/existing-implementation-state: HIGH — direct repository read + git log, not inference from documentation alone
- Pitfalls: HIGH for scGPT-specific pitfalls (already-encountered project history) and Ensembl-ID/four-step-pipeline pitfalls (this project's own prior PITFALLS.md, independently corroborated by live-fetched official docs this session); MEDIUM for GPU/memory-specific claims not re-verified this session (this repo's target hardware is CPU-only, so those claims are lower-priority to re-confirm)

**Research date:** 2026-09-17
**Valid until:** 30 days for the architectural/pitfall content (stable); re-verify the live `scgpt`/`geneformer` API introspection steps immediately before writing worker-script code regardless of elapsed time, per the roadmap's own explicit "verify before writing" requirement — treat any elapsed time as grounds for re-checking, not just a 30-day clock
