# Phase 5: Perturbation-Response Tool + VCC Benchmark Harness - Research

**Researched:** 2026-09-08
**Domain:** Single-cell perturbation-response prediction (CRISPR knockdown) + Virtual Cell Challenge (VCC) benchmark harness
**Confidence:** MEDIUM-HIGH (metrics/dataset/ingest findings are HIGH confidence, source-verified against Arc Institute's actual code; the GEARS-vs-hybrid architecture recommendation is MEDIUM confidence — a judgment call informed by verified evidence, not a single documented "right answer")

<user_constraints>
## User Constraints (from CONTEXT.md)

No CONTEXT.md exists for this phase (not yet run through `/gsd:discuss-phase`). No user decisions or discretion areas are locked in beyond what's already recorded in `.planning/PROJECT.md` and `.planning/ROADMAP.md`. Binding project-level constraints relevant to this phase, copied from PROJECT.md:

- **VCC scope is bounded**: "benchmark against VCC's public task format and official metrics — not a competitive entry against the live 2026 leaderboard" and explicitly listed as Out of Scope: "Formal Virtual Cell Challenge competition entry/leaderboard submission." Do not over-invest in leaderboard-chasing model quality; the requirement is a credible, correctly-scored benchmark run, not a winning score.
- **Domain interop constraint**: must consume/produce standard single-cell formats (`.mtx`/`.h5`/`.h5ad`) — no bespoke formats.
- **Compute constraint**: self-hosted by default; no requirement for GPU-only paths to be the sole option.
- Phase 4 precedent (Isolation Boundary pattern) is not a hard requirement here — it applies only if a heavy/conflicting dependency (e.g., PyTorch Geometric) is actually chosen. See Architecture Patterns below for the recommendation to avoid needing it in this phase.

No deferred ideas apply to this phase specifically.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-------------------|
| PERT-01 | Perturbation-response tool predicts post-knockdown expression from control profiles + target gene (GEARS/cell-gears, or documented simpler hybrid statistical+neural fallback) | Standard Stack (linear-additive primary recommendation), Architecture Patterns, Code Examples, State of the Art (Nature Methods 2025 evidence) |
| PERT-02 | Tool's predictions automatically compared against a naive perturbation-mean baseline; baseline never reported alone | Don't Hand-Roll (`cell_eval.build_base_mean_adata`), Code Examples, Common Pitfalls |
| VCC-01 | VCC's public dataset ingested through the existing Phase 1 ingest pipeline (`ingest/`), no bespoke ingest path | Architecture Patterns (thin `.h5ad` loader adapter), Common Pitfalls (ingest format gap), Code Examples |
| VCC-02 | Eval harness calls the perturbation tool directly (bypassing the agent loop), computes PDS, DES, MAE exactly as Arc Institute defines them | Standard Stack (`cell-eval`), Code Examples (`MetricsEvaluator`), Sources (verified against Arc's own source) |
| VCC-03 | Benchmark results report all three metrics plus the naive-baseline comparison | Don't Hand-Roll, Code Examples, Common Pitfalls (never report predictor score without baseline) |
</phase_requirements>

## Summary

Phase 5 has two halves: (1) a perturbation-response predictor, and (2) a VCC-faithful eval harness. The eval harness half is now fully de-risked — Arc Institute publishes an official Python package, `cell-eval` (PyPI, `ArcInstitute/cell-eval` on GitHub), that implements PDS, DES, and MAE exactly as used in the live competition, plus an official naive-baseline builder (`build_base_mean_adata`). This is a pure-Python/CPU package with no PyTorch dependency — it installs directly into the main project venv, no isolation needed. Verified by reading Arc's actual source (`_pipeline/_runner.py`, `metrics/_anndata.py`, `_types/_de.py`, `_baseline.py`, `_evaluator.py`), not by trusting blog posts or rendered docs.

The predictor half required resolving the phase's own explicit "GEARS or documented hybrid fallback" branch point. Investigation shows GEARS is a real but heavy option: it requires PyTorch Geometric as a manual (non-transitive) prerequisite, requires full supervised training on the target dataset (it is not a zero-shot pretrained foundation model — no usable pretrained checkpoint transfers to VCC's own gene panel), and explicitly does not handle cross-cell-type generalization or combinatorial perturbations well. Critically, the investigated alternative of avoiding GEARS by reusing the already-installed scGPT worker's perturbation task is a dead end: scGPT's own `Tutorial_Perturbation.ipynb` fine-tuning workflow imports `from gears import PertData, GEARS` and `torch_geometric` directly — it is built on top of GEARS, not an independent path. Meanwhile, a Nature Methods 2025 paper ("Deep-learning-based gene perturbation effect prediction does not yet outperform simple linear baselines") and its associated preprint establish, with peer-reviewed evidence, that simple linear/additive models (predicted perturbed expression = control expression + a per-perturbation linear shift) are competitive with or exceed GNN-based approaches like GEARS on this exact task class. Combined with the fact that scikit-learn is already an installed transitive dependency (via scanpy) and needs zero new packages, the hybrid statistical approach is the prescribed primary path for this phase; GEARS is documented as a heavier, explicitly optional stretch goal, not a coin-flip alternative.

**Primary recommendation:** Build the perturbation predictor as a scikit-learn-based linear/ridge "control + learned per-gene shift" model living directly in the main project venv (no isolation, no new heavy dependencies) satisfying PERT-01's own "documented simpler hybrid statistical+neural fallback" allowance; use Arc Institute's official `cell-eval` package unmodified for VCC-02/03 metrics and its `build_base_mean_adata()` for the PERT-02/VCC-03 naive baseline; add a thin `.h5ad`-detection branch to `ingest/loaders.py` to satisfy VCC-01 without a bespoke pipeline.

## Standard Stack

### Core

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|---------------|
| `cell-eval` | >=0.8.2 | Computes PDS (`discrimination_score_l1`), DES (`overlap_at_N`), MAE exactly as Arc Institute scores the live VCC leaderboard; also builds the naive perturbation-mean baseline | It is Arc Institute's own official implementation (`ArcInstitute/cell-eval`), the literal ground truth for "exactly as Arc Institute defines them" (VCC-02) |
| `scikit-learn` | already installed (1.9.0, transitive via `scanpy`) | Ridge/linear regression backbone for the "hybrid statistical" perturbation predictor | Already present in the venv (`Required-by: pynndescent, scanpy, umap-learn`) — zero new dependency cost; industry-standard, well-tested linear model implementations |
| `scanpy` / `anndata` | already installed (>=1.12 / >=0.13) | AnnData I/O and manipulation for both the predictor and the ingest adapter | Already the project's data backbone (Phase 1-4 precedent) |

### Supporting

| Library | Version | Purpose | When to Use |
|---------|---------|---------|--------------|
| `pdex` | >=0.2.5 (transitive via `cell-eval`) | Parallel Mann-Whitney U differential expression, used internally by `cell-eval` for DES | Never called directly — `cell-eval`'s `MetricsEvaluator.compute()` invokes it automatically when `de_pred`/`de_real` are not precomputed |
| `gcsfs` | latest | Streaming reads from the VCC dataset's public GCS bucket (`gs://arc-institute-virtual-cell-atlas/...`) without downloading the full file first | Only needed if downloading the VCC `.h5ad` files directly rather than via a pre-downloaded local copy; not needed if data is fetched once via `gsutil`/`gcloud storage cp` and cached locally |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Linear/ridge hybrid statistical predictor (primary) | GEARS (`cell-gears` + PyTorch Geometric) | GEARS is a real, published, GNN-based perturbation predictor with a documented API (`PertData`/`GEARS` classes), but requires: (a) PyTorch Geometric as a manual prerequisite not pulled in by `pip install cell-gears`, (b) full supervised training per target dataset (no usable pretrained checkpoint transfers to VCC's gene panel — checkpoints found on HuggingFace/Dataverse are trained on the Norman dataset's own gene panel/GO-graph), (c) the same Isolation Boundary treatment as Phase 4's scGPT worker (heavy/conflicting torch stack). Use GEARS only as an explicit stretch-goal/second predictor once the linear baseline and eval harness are working end-to-end, not as the phase's critical path. |
| Linear/ridge hybrid statistical predictor (primary) | `pertpy`'s `scGen` (autoencoder-based, JAX) | `pertpy` (v1.3.0) is a legitimate scverse-ecosystem package (same family as the already-used `decoupler`), `requires-python >=3.12` matches the project floor, and its base install has no torch dependency. `scGen` is more expressive than a pure linear model but is still a learned generative model requiring training per dataset; offers no clear advantage over the linear baseline given the Nature Methods 2025 finding that linear approaches are competitive. Worth noting as a documented middle ground if the linear baseline underperforms badly on held-out target genes. |
| Routing perturbation prediction through the existing scGPT worker (`bio_fm_worker/`) | N/A — investigated and rejected | scGPT's own perturbation fine-tuning tutorial (`Tutorial_Perturbation.ipynb`) imports `from gears import PertData, GEARS` and `from torch_geometric.loader import DataLoader` directly — it is GEARS-dependent, not an alternative to it. Reusing the scGPT worker would require installing GEARS + torch_geometric *inside* that worker anyway, plus scGPT's own additional `TransformerGenerator` fine-tuning complexity on top. No dependency-avoidance benefit; strictly more complex than installing GEARS standalone. |

**Installation:**
```bash
uv pip install "cell-eval>=0.8.2"
# scikit-learn, scanpy, anndata: already present, no action needed
# Only if pursuing the GEARS stretch goal, in an isolated venv mirroring bio_fm_worker/:
# pip install torch_geometric   # manual prerequisite, not transitive
# pip install cell-gears
```

## Architecture Patterns

### Recommended Project Structure

```
perturbation/
├── __init__.py
├── model.py          # LinearAdditivePerturbationModel: control + per-gene learned shift (ridge regression)
├── pipeline.py        # predict(adata_control, target_gene) -> AnnData of predicted perturbed profiles
├── summary.py          # PerturbationCall / PerturbationSummary bounded dataclasses (mirrors annotation/summary.py)
└── baseline.py         # thin wrapper around cell_eval.build_base_mean_adata for PERT-02

benchmark/
├── __init__.py
├── vcc_eval.py         # calls perturbation.pipeline.predict() directly, bypassing the agent loop (VCC-02)
└── report.py           # formats PDS/DES/MAE + baseline comparison for VCC-03 (never report predictor alone)

ingest/
└── loaders.py           # ADD a `.h5ad` detection branch (VCC-01) — see Pattern 2 below
```

This mirrors the `annotation/` package shape from Phase 4 (bounded dataclass contracts, a `pipeline.py` entrypoint, a `summary.py` for structured results) but does **not** need an isolated worker venv or a `_client.py` subprocess shim, because the recommended predictor has no heavy/conflicting dependencies — everything runs in the main project venv.

### Pattern 1: Linear-additive perturbation model (primary predictor, PERT-01)

**What:** For each target gene seen in training data, learn a per-gene additive shift vector from paired (control-mean, perturbed-mean) pseudobulk profiles; for genes never seen in training (the actual VCC held-out test set), predict the shift via ridge regression over gene-level features (e.g., the target gene's own control-population expression profile, or correlation/co-expression similarity to trained genes) rather than a bespoke GNN.

**When to use:** Default predictor for all of Phase 5. This satisfies PERT-01's explicit allowance for "a documented simpler hybrid statistical+neural fallback" and is directly supported by peer-reviewed evidence that such models are competitive with deep-learning approaches on this task class (see State of the Art).

**Example (sketch — planner should refine into `perturbation/model.py`):**
```python
# Source: pattern synthesized from Nature Methods 2025 "linear additive" baseline description
# + scikit-learn Ridge docs (https://scikit-learn.org/stable/modules/linear_model.html#ridge-regression)
import numpy as np
from sklearn.linear_model import Ridge

class LinearAdditivePerturbationModel:
    """control_expr + learned per-target-gene shift = predicted perturbed_expr"""

    def __init__(self, alpha: float = 1.0):
        self.alpha = alpha
        self._known_shifts: dict[str, np.ndarray] = {}   # target_gene -> shift vector
        self._fallback_model: Ridge | None = None          # for unseen target genes

    def fit(self, control_mean: np.ndarray, pert_means: dict[str, np.ndarray]):
        # pert_means: {target_gene: perturbed_pseudobulk_mean_vector}
        self._known_shifts = {g: v - control_mean for g, v in pert_means.items()}
        # Fallback: regress each known shift on the target gene's own control-population
        # expression (its baseline abundance) to interpolate to unseen genes.
        X = np.array([[control_mean[self._gene_index(g)]] for g in self._known_shifts])
        Y = np.array(list(self._known_shifts.values()))
        self._fallback_model = Ridge(alpha=self.alpha).fit(X, Y)

    def predict(self, control_mean: np.ndarray, target_gene: str) -> np.ndarray:
        if target_gene in self._known_shifts:
            shift = self._known_shifts[target_gene]
        else:
            x = np.array([[control_mean[self._gene_index(target_gene)]]])
            shift = self._fallback_model.predict(x)[0]
        return control_mean + shift
```
The planner must decide the exact feature representation for the fallback path (control-population expression of the target gene is the simplest defensible choice; richer options like co-expression similarity to trained genes are a documented stretch improvement, not required for v1).

### Pattern 2: Thin `.h5ad` ingest adapter (VCC-01)

**What:** `ingest/loaders.py::load(path)` currently only dispatches on (a) a directory → `sc.read_10x_mtx`, or (b) a `.h5` file → `sc.read_10x_h5`. It raises `ValueError` on anything else — VCC ships pre-assembled `.h5ad` files, which this loader cannot currently read.

**When to use:** Required for VCC-01. Add exactly one new branch, do not build a parallel/bespoke ingest path.

**Example:**
```python
# ingest/loaders.py — add alongside existing directory/.h5 branches
elif path_str.endswith(".h5ad"):
    return sc.read_h5ad(path)
```
Everything downstream (`ingest/pipeline.py::ingest_10x`, `ingest/contract.py::set_counts_layer`) operates on whatever ends up in `.X` regardless of source format, so no other pipeline changes are needed — the gap is purely in the format-dispatch branch of `loaders.py`. Confirmed by reading `ingest/pipeline.py` (`ingest_10x` calls `loaders.load(path)` then `contract.set_counts_layer(adata)` unconditionally) and `ingest/contract.py` (`set_counts_layer` just copies whatever is in `.X`).

### Pattern 3: VCC eval harness bypasses the agent loop (VCC-02)

**What:** The eval harness must call the perturbation tool's underlying prediction function directly — not through the Claude agent's tool-calling loop — so that benchmark runs are fast, deterministic, and don't burn LLM tokens/latency on every one of hundreds of held-out perturbations.

**Example:**
```python
# Source: cell-eval README (ArcInstitute/cell-eval) + verified _evaluator.py source
from cell_eval import MetricsEvaluator
import anndata as ad

pred_adata = build_predictions_adata(...)   # calls perturbation.pipeline.predict() per target gene directly
real_adata = ad.read_h5ad("vcc_test_real.h5ad")

evaluator = MetricsEvaluator(
    adata_pred=pred_adata,
    adata_real=real_adata,
    control_pert="non-targeting",   # DEFAULT_CTRL in cell-eval's own _const.py — verify matches actual VCC obs column value
    pert_col="target_gene",          # DEFAULT_PERT_COL in cell-eval's own _const.py
    num_threads=-1,
    outdir="./vcc_eval_results",
)
results = evaluator.compute(profile="vcc")   # profile="vcc" == exactly [mae, discrimination_score_l1, overlap_at_N]
```

### Anti-Patterns to Avoid

- **Hand-rolling PDS/DES/MAE formulas from a paper or blog description:** Arc Institute's own `cell-eval` package is the ground truth (VCC-02 explicitly requires "exactly as Arc Institute defines them"). Any hand-rolled reimplementation risks subtle divergence (e.g., DES's exact rank-normalization formula, or PDS's exclude-target-gene-column-by-default behavior) that would silently produce scores that don't match the real competition.
- **Reporting the predictor's score without the naive baseline alongside it (violates PERT-02/VCC-03):** Always run `cell_eval.build_base_mean_adata()` (or the `cell-eval baseline` CLI) on the same real/held-out split and report both scores side by side in every benchmark report — never the predictor score alone.
- **Building a bespoke VCC-specific ingest path parallel to `ingest/pipeline.py` (violates VCC-01):** The fix is one new branch in `loaders.py`, not a new pipeline module.
- **Treating GEARS as a zero-shot pretrained model:** It requires supervised training on the specific target dataset/gene panel; there is no "just download a checkpoint and predict" path for VCC's gene panel.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|--------------|-----|
| Naive perturbation-mean baseline (PERT-02, VCC-03) | A custom "average all perturbed profiles together" script | `cell_eval.build_base_mean_adata(adata, counts_df, pert_col="target_gene", control_pert="non-targeting")` or `cell-eval baseline -a <adata> -o baseline.h5ad -O baseline_de.csv` CLI | This is Arc Institute's own official naive baseline implementation — reimplementing it risks not matching the semantics used in the actual competition, and defeats the point of "compared against a naive baseline" being a credible, external, non-cherry-picked comparison |
| PDS computation (VCC-02) | Custom L1-distance-and-rank code | `cell_eval.metrics._anndata.discrimination_score()` via `MetricsEvaluator(...).compute(profile="vcc")` | Exact algorithm verified from source: for each perturbation, L1 pairwise distance between the predicted effect vector and ALL real effect vectors (excluding the target gene's own column by default), rank the correct match, normalize as `1 - (rank / n_perts)`. Reimplementing this from a paper description risks getting the exclusion/normalization details wrong |
| DES computation (VCC-02) | Custom DE-gene-overlap code | `cell_eval.DEComparison.compute_overlap()` (internally called by `MetricsEvaluator.compute(profile="vcc")`, which maps to `overlap_at_N`) | Exact algorithm verified from source: `k_eff = real_genes.size` (number of real significant DE genes at FDR<0.05, sorted by `abs_log2_fold_change`), `overlap = intersect1d(real_subset, pred_subset).size / k_eff` |
| MAE computation (VCC-02) | Custom mean-absolute-error over per-cell or per-gene arrays | `cell_eval.metrics._anndata.mae()` (`sklearn.metrics.mean_absolute_error` applied to bulk/pseudobulk-per-perturbation arrays, not per-cell) | The exact aggregation level (pseudobulk per perturbation, not per-cell) matters for matching Arc's actual scoring; verified from source |
| Differential expression for DES's underlying gene ranking | Reusing Phase 2's `scanpy` Wilcoxon rank-sum DE tool | `pdex` (parallel Mann-Whitney U + FDR), invoked automatically inside `cell-eval` | `cell-eval`'s DES metric is defined relative to `pdex`'s specific DE statistics; using a different DE test (even a reasonable one like Phase 2's Wilcoxon tool) would compute a different, non-comparable ranking and break "exactly as Arc Institute defines them" |

**Key insight:** Every numeric piece of VCC-02/VCC-03 already has an official, source-verified implementation in `cell-eval`. The only genuinely novel engineering in this phase is the predictor itself (PERT-01) and the one-line ingest adapter (VCC-01) — everything else is integration, not invention.

## Common Pitfalls

### Pitfall 1: GEARS is mistaken for a zero-shot pretrained model
**What goes wrong:** Assuming a pretrained GEARS checkpoint (e.g., ones found on HuggingFace under `matthewshu/gears-norman`) can be loaded and used directly to predict on VCC's dataset.
**Why it happens:** Phase 4's scGPT precedent (a single "whole-human" pretrained checkpoint usable across datasets) creates an expectation that other bio-FM-adjacent tools work the same way.
**How to avoid:** If GEARS is pursued (stretch goal only), budget for full supervised training on the VCC training split, including building its GO-similarity gene graph for VCC's own 300-gene panel via `PertData.new_data_process()`.
**Warning signs:** Any plan step that says "load pretrained GEARS checkpoint" without a corresponding training step for VCC's own data.

### Pitfall 2: torch_geometric is not an automatic dependency of `cell-gears`
**What goes wrong:** Running `pip install cell-gears` and expecting GEARS to work; it imports `torch_geometric` at runtime but the PyPI package's `requires_dist` does not include it.
**Why it happens:** GEARS' own README says "Install PyG, and then do `pip install cell-gears`" — it's a documented manual prerequisite, not a packaging oversight, but easy to miss.
**How to avoid:** If pursuing GEARS, install `torch_geometric` explicitly first, matching the exact torch version used (mirror Phase 4's `bio_fm_worker` isolation pattern and its documented `torch==2.3.0` pin to avoid ABI mismatches).
**Warning signs:** `ImportError: No module named 'torch_geometric'` when importing `gears`.

### Pitfall 3: Assuming the scGPT worker can shortcut around GEARS
**What goes wrong:** Attempting to reuse the existing isolated `bio_fm_worker/` scGPT environment for perturbation prediction to avoid setting up GEARS separately.
**Why it happens:** scGPT is already installed and working (Phase 4); it seems natural to extend it.
**How to avoid:** Verified via direct source inspection of `Tutorial_Perturbation.ipynb`: scGPT's perturbation task itself imports `from gears import PertData, GEARS` and `torch_geometric` — it requires GEARS as a dependency, plus its own additional `TransformerGenerator` fine-tuning layer on top. There is no dependency-avoidance benefit to this route.
**Warning signs:** Discovering mid-implementation that "using scGPT for perturbation" still requires installing GEARS anyway.

### Pitfall 4: `pert_col` / `control_pert` naming defaults must be verified against actual VCC data, not assumed
**What goes wrong:** Silently mismatched column names or control-token values cause `cell-eval` to either error or (worse) silently produce a scientifically meaningless score.
**Why it happens:** `cell-eval`'s own defaults are `DEFAULT_PERT_COL = "target_gene"` and `DEFAULT_CTRL = "non-targeting"` (both verified from `cell_eval/_const.py`, and confirmed identical in the CLI's `_run.py`, which passes `args.pert_col`/`args.control_pert` through to `MetricsEvaluator` unchanged) — these are consistent within `cell-eval` itself, but separately, `cell-eval prep`'s CSV-genelist validation step has been observed (via WebFetch of `_cli/_prep.py`) to reference a `"ntc"` negative-control token as a default in a different code path. **This inconsistency needs a one-time verification against the actual VCC dataset's `.obs` columns before implementation** — do not assume either token/column name without inspecting the real downloaded `.h5ad`.
**How to avoid:** After downloading the VCC training `.h5ad`, run `adata.obs["target_gene"].unique()` (or equivalent) and confirm the exact control-token string (`"non-targeting"` vs `"ntc"` vs something dataset-specific) before wiring up `MetricsEvaluator`.
**Warning signs:** `MetricsEvaluator` raising a `ValueError` about a missing control group, or computing suspiciously uniform/zero scores across all perturbations (a sign the control filter matched nothing).

### Pitfall 5: QC-filtering the VCC dataset through Phase 1's QC pipeline can break metric parity
**What goes wrong:** Running VCC's ingested data through the existing `ingest/pipeline.py::ingest_10x` QC step (doublet detection, mito%, low-count filtering) before benchmark scoring can remove cells that Arc's official scoring expects to be present, or change per-perturbation cell counts in ways that shift pseudobulk means — causing benchmark numbers that don't match what an external observer would get running `cell-eval` directly on Arc's unmodified data.
**Why it happens:** VCC-01 requires ingesting through the *existing* pipeline (which includes QC) "no bespoke ingest path" — this is correct for VCC-01, but VCC-02 separately requires exact metric parity with Arc's own scoring, which assumes Arc's original (unfiltered by this project's own QC) cell population.
**How to avoid:** Document explicitly in the benchmark report which QC state (raw ingested-and-QC'd via the project pipeline, vs. Arc's original unfiltered public release) the reported scores reflect. This is not a contradiction to resolve silently — it's a fact to report transparently (VCC-03's "report all three metrics" should include this provenance note).
**Warning signs:** Benchmark scores that differ meaningfully from any publicly reported baseline scores on the same VCC public split without an accompanying explanation of why.

### Pitfall 6: Train/test leakage across perturbations
**What goes wrong:** Fitting the linear/ridge fallback model (or any GEARS training) on the same target genes it is later evaluated on, producing artificially inflated PDS/DES/MAE scores.
**Why it happens:** VCC's public dataset ships train/validation/test splits by design specifically to prevent this — but a bespoke ad hoc pipeline may not respect the split boundaries if it isn't careful about which gene set backs training data.
**How to avoid:** Use VCC's own published train/validation/test partition (`train/adata_Training.h5ad`, `validation/`, `test/` under the GCS bucket path) rather than re-splitting the combined dataset randomly; confirm the target genes in the eval set are disjoint from the genes used to fit the linear model's known-shift lookup.
**Warning signs:** Suspiciously high PDS/DES scores on first attempt, especially matching or exceeding published VCC leaderboard scores from teams using much more sophisticated models.

### Pitfall 7: VCC's public dataset bucket has moved
**What goes wrong:** Following stale documentation/tutorials pointing at `gs://arc-ctc-tahoe100/` or `gs://arc-scbasecount/`.
**Why it happens:** Arc Institute deprecated those buckets March 31, 2026, and migrated to `gs://arc-institute-virtual-cell-atlas/virtual-cell-challenge/`.
**How to avoid:** Use only the new bucket path; be aware it is subject to "Requester Pays" billing beyond a 2TB/month free tier — plan for a one-time authenticated download/cache rather than repeated live streaming during benchmark runs.
**Warning signs:** 403/404 errors against the old bucket paths found in older tutorials or blog posts.

## Code Examples

### Building and using the official naive baseline (PERT-02, VCC-03)
```python
# Source: ArcInstitute/cell-eval src/cell_eval/_baseline.py (verified via direct source read)
from cell_eval import build_base_mean_adata
import anndata as ad
import pandas as pd

train_adata = ad.read_h5ad("vcc_train.h5ad")
counts_df = pd.read_csv("pert_counts_Training.csv")  # ships alongside VCC training split

baseline_adata = build_base_mean_adata(
    train_adata,
    counts_df,
    pert_col="target_gene",
    control_pert="non-targeting",   # VERIFY against actual .obs values first (see Pitfall 4)
)
baseline_adata.write_h5ad("baseline_pred.h5ad")
```

### Computing the official VCC metric profile (VCC-02)
```python
# Source: ArcInstitute/cell-eval src/cell_eval/_pipeline/_runner.py (verified via direct source read)
# KNOWN_PROFILES = ["full", "minimal", "vcc", "de", "anndata", "pds"]
# VCC_METRICS = ["mae", "discrimination_score_l1", "overlap_at_N"]  <- PDS = discrimination_score_l1, DES = overlap_at_N
from cell_eval import MetricsEvaluator

evaluator = MetricsEvaluator(
    adata_pred=predicted_adata,
    adata_real=real_test_adata,
    control_pert="non-targeting",
    pert_col="target_gene",
    num_threads=-1,
)
vcc_results = evaluator.compute(profile="vcc")
# vcc_results now contains MAE, PDS (discrimination_score_l1), and DES (overlap_at_N)
```

### CLI equivalent (useful for a standalone benchmark-report script per VCC-03)
```bash
# Source: cell-eval README (ArcInstitute/cell-eval)
uv pip install -U cell-eval
cell-eval prep -i predicted.h5ad -g expected_genelist.csv
cell-eval baseline -a train.h5ad -o baseline_pred.h5ad -O baseline_de.csv
cell-eval run -ap predicted.h5ad -ar real_test.h5ad --num-threads 8 --profile vcc -o ./results
cell-eval run -ap baseline_pred.h5ad -ar real_test.h5ad --num-threads 8 --profile vcc -o ./baseline_results
# Report both ./results and ./baseline_results side by side — never the predictor alone (VCC-03)
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|-------------------|----------------|--------|
| GNN-based perturbation prediction assumed to be state-of-the-art by default (GEARS, 2023) | Simple linear/additive models shown to be competitive with or better than deep-learning approaches for single-perturbation effect prediction | Nature Methods, 2025 ("Deep-learning-based gene perturbation effect prediction does not yet outperform simple linear baselines") | Directly justifies choosing the "hybrid statistical+neural fallback" allowed by PERT-01 as the primary approach rather than a last-resort fallback |
| Hand-computing perturbation benchmark metrics from paper descriptions | Official `cell-eval` package (Arc Institute) as the canonical, versioned implementation of PDS/DES/MAE | `cell-eval` first released for the 2025/2026 VCC competition cycle, actively maintained (v0.8.2 as of this research) | Removes ambiguity from "exactly as Arc Institute defines them" (VCC-02) — use the package, don't reimplement |
| VCC public data hosted at `gs://arc-ctc-tahoe100/` / `gs://arc-scbasecount/` | Migrated to `gs://arc-institute-virtual-cell-atlas/virtual-cell-challenge/` | Old buckets deprecated March 31, 2026 | Any implementation must target the new bucket path; stale tutorials will 404 |

**Deprecated/outdated:**
- Old VCC GCS bucket paths (`arc-ctc-tahoe100`, `arc-scbasecount`): replaced by `arc-institute-virtual-cell-atlas`.

## Open Questions

1. **Exact `.obs` column values in the actual downloaded VCC dataset (pert_col name, control token)**
   - What we know: `cell-eval`'s own internal defaults are `pert_col="target_gene"`, `control_pert="non-targeting"` (verified from source, consistent between its CLI and `_const.py`). A separate WebFetch summary of `cell-eval prep`'s CLI flagged a `"ntc"` default in a different code path, which may or may not apply to the actual VCC release data.
   - What's unclear: Whether the real downloaded VCC `.h5ad` uses `"non-targeting"`, `"ntc"`, or a dataset-specific token, and whether the column is literally named `target_gene`.
   - Recommendation: First implementation task in Phase 5 should be "download VCC training split, inspect `.obs` columns/values directly," before wiring up either the predictor or the evaluator. Treat any hardcoded column/token name in code as provisional until verified.

2. **Whether GEARS should be attempted at all within this phase's scope**
   - What we know: GEARS is heavier (PyTorch Geometric + full training + Isolation Boundary treatment) and not clearly superior to the linear approach per the cited literature; PROJECT.md explicitly de-scopes competing for the live leaderboard.
   - What's unclear: Whether "documented simpler hybrid statistical+neural fallback" in PERT-01's own wording is meant as a true either/or choice for the planner to decide, or whether GEARS should still be attempted as a secondary/stretch predictor for comparison richness.
   - Recommendation: Plan the linear/ridge hybrid model as the only required predictor for Phase 5's success criteria. If time/scope allows, add GEARS as an explicitly optional stretch-goal plan wave, reusing the exact isolated-venv + subprocess-JSON pattern from Phase 4's `bio_fm_worker`/`annotation/fm_client.py`.

3. **Feature representation for the linear model's fallback path (unseen target genes)**
   - What we know: A pure per-gene lookup table cannot generalize to target genes absent from training (which is exactly VCC's held-out test design). The Nature Methods 2025 paper's own "linear additive" formulation implies some feature representation is used to interpolate to unseen perturbations, but the exact feature set used in that paper was not independently confirmed in this research pass (the primary source URL required institutional/cookie-based access that WebFetch could not bypass).
   - What's unclear: Best feature choice — target gene's own control-population expression (simplest), co-expression correlation to trained genes, or a small learned gene embedding.
   - Recommendation: Start with the simplest defensible feature (target gene's own control-mean expression value, per Pattern 1's sketch) and treat richer features as a documented, optional improvement if v1 MAE/PDS/DES scores are poor on held-out genes.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest >=8 (already configured, `[tool.pytest.ini_options]` in `pyproject.toml`) |
| Config file | `pyproject.toml` (existing `testpaths = ["tests"]`, `markers` list) |
| Quick run command | `pytest -m "not live_llm and not bio_fm_smoke and not vcc_data" -q` |
| Full suite command | `pytest -q` (requires VCC dataset downloaded/cached locally for `vcc_data`-marked tests) |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|---------------------|--------------|
| PERT-01 | Linear model predicts perturbed expression from control profile + target gene on a small synthetic fixture | unit | `pytest tests/test_perturbation_model.py -x` | ❌ Wave 0 |
| PERT-02 | Predictor's output is automatically compared against `build_base_mean_adata` baseline; report never emits predictor-only score | unit | `pytest tests/test_perturbation_baseline.py -x` | ❌ Wave 0 |
| VCC-01 | `.h5ad` file ingests via `ingest/loaders.py::load()` through the existing `ingest_10x` pipeline unchanged | unit | `pytest tests/test_loaders.py -k h5ad -x` | ❌ Wave 0 (extend existing file) |
| VCC-02 | `MetricsEvaluator(...).compute(profile="vcc")` returns MAE/PDS/DES on a small synthetic pred/real AnnData pair, matching hand-computed expected values | integration | `pytest tests/test_vcc_eval.py -x` | ❌ Wave 0 |
| VCC-03 | End-to-end benchmark report includes all three metrics plus baseline comparison, on a small synthetic dataset (no live GCS download required) | integration | `pytest tests/test_vcc_report.py -x` | ❌ Wave 0 |
| (smoke) | Full pipeline against real downloaded VCC public dataset | smoke, marked `vcc_data` (excluded from fast/CI runs, mirrors `bio_fm_smoke` pattern) | `pytest -m vcc_data -x` | ❌ Wave 0 |

### Sampling Rate
- **Per task commit:** `pytest -m "not live_llm and not bio_fm_smoke and not vcc_data" -q` (fast, synthetic-fixture-only)
- **Per wave merge:** `pytest -q` excluding only `vcc_data` (requires local VCC data cache; run manually/CI-gated once dataset is downloaded)
- **Phase gate:** Full suite green (including a `vcc_data`-marked smoke run against the real downloaded VCC split) before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `tests/test_perturbation_model.py` — covers PERT-01 (synthetic control/perturbed fixture, no real VCC download needed)
- [ ] `tests/test_perturbation_baseline.py` — covers PERT-02
- [ ] Extend `tests/test_loaders.py` — covers VCC-01 (`.h5ad` branch)
- [ ] `tests/test_vcc_eval.py` — covers VCC-02 (small synthetic pred/real AnnData with hand-verifiable PDS/DES/MAE)
- [ ] `tests/test_vcc_report.py` — covers VCC-03
- [ ] New pytest marker: add `vcc_data: requires the downloaded VCC public dataset, excluded from fast/CI runs` to `pyproject.toml`'s `markers` list, mirroring the existing `bio_fm_smoke` pattern
- [ ] Framework install: `uv pip install "cell-eval>=0.8.2"` — not yet in `pyproject.toml` dependencies

## Sources

### Primary (HIGH confidence)
- `ArcInstitute/cell-eval` GitHub repo, source files fetched and read directly: `src/cell_eval/_pipeline/_runner.py` (VCC_METRICS/KNOWN_PROFILES), `src/cell_eval/metrics/_anndata.py` (`discrimination_score`/`mae` implementations), `src/cell_eval/_types/_de.py` (`DEComparison.compute_overlap` — DES algorithm), `src/cell_eval/_baseline.py` (`build_base_mean_adata` — official naive baseline), `src/cell_eval/_evaluator.py` and `_cli/_run.py` (`MetricsEvaluator` API, `DEFAULT_PERT_COL`/`DEFAULT_CTRL` in `_const.py`), `pyproject.toml` (v0.8.2, deps, no torch)
- `ArcInstitute/arc-virtual-cell-atlas` GitHub repo: `virtual-cell-challenge/README.md` (official metric names: DES, PDS, MAE; dataset location and bucket migration notice) and the tutorial notebook (`.h5ad` format, `gcsfs` streaming pattern, path structure)
- `snap-stanford/GEARS` GitHub README (installation instructions, `PertData`/`GEARS` API, explicit "not designed for cross-cell-type" and "cannot reliably predict combinatorial perturbations" limitations)
- `scGPT/tutorials/Tutorial_Perturbation.ipynb` (raw source, first code cell): confirms `from gears import PertData, GEARS` and `torch_geometric` imports — scGPT's perturbation task depends on GEARS
- `cell-gears` PyPI JSON metadata (`/pypi/cell-gears/json`): confirms no `torch_geometric` in declared dependencies, no `requires_python` floor
- `pertpy` PyPI JSON metadata: v1.3.0, `requires-python >=3.12`, torch gated behind an `all` extra
- Local repo source read directly: `ingest/loaders.py`, `ingest/pipeline.py`, `ingest/contract.py`, `annotation/fm_client.py`, `annotation/summary.py`, `pyproject.toml`, `.planning/PROJECT.md`, `.planning/STATE.md`, `.planning/ROADMAP.md`, `.planning/REQUIREMENTS.md`, `.planning/config.json`, `bio_fm_worker/README.md`
- Local environment check: `pip show scikit-learn` confirms 1.9.0 already installed transitively via `scanpy`/`pynndescent`/`umap-learn`

### Secondary (MEDIUM confidence)
- Nature Methods 2025, "Deep-learning-based gene perturbation effect prediction does not yet outperform simple linear baselines" — WebSearch-surfaced title/abstract-level claim, cross-referenced by a related bioRxiv preprint discussing the same "linear additive" formulation; the full paywalled paper text could not be fetched (Nature's access-control redirect blocked WebFetch), so the exact feature representation used in the paper's own linear model is not independently verified — flagged as Open Question 3.
- `cell-eval` README (`ArcInstitute/cell-eval`), fetched via WebFetch: installation and CLI usage examples (`cell-eval prep`, `cell-eval run`, `cell-eval baseline`) — cross-verified against directly-read source code for the underlying behavior

### Tertiary (LOW confidence)
- `cell-eval` `_cli/_prep.py` WebFetch summary noting a `"ntc"` default negative-control token in the `prep` command path, apparently inconsistent with `_const.py`'s `DEFAULT_CTRL = "non-targeting"` used elsewhere — not independently re-verified by direct source read in this session; flagged explicitly as Common Pitfall 4 / Open Question 1 for implementation-time verification against real VCC data rather than presented as settled fact
- HuggingFace (`matthewshu/gears-norman`) and Harvard Dataverse GEARS checkpoint listings — surfaced via WebSearch, not independently verified for exact gene-panel compatibility beyond the general claim that GEARS checkpoints are dataset/gene-panel-specific

## Metadata

**Confidence breakdown:**
- Standard stack (cell-eval for metrics/baseline): HIGH — verified directly against Arc Institute's own source code, not secondary descriptions
- Standard stack (linear/hybrid predictor choice over GEARS): MEDIUM — well-evidenced by peer-reviewed literature and verified dependency-chain analysis, but is a judgment call the planner/user could reasonably revisit, not a single documented "correct" answer
- Architecture (ingest adapter, package structure): HIGH — verified directly by reading the actual `ingest/loaders.py`/`pipeline.py`/`contract.py` source and confirming the exact gap and fix
- Pitfalls: MEDIUM-HIGH — most pitfalls verified from direct source reads; the `pert_col`/`control_pert` naming inconsistency (Pitfall 4) is flagged LOW/needs-verification since it rests on a WebFetch summary rather than a direct source re-read

**Research date:** 2026-09-08
**Valid until:** 2026-10-08 (30 days) for `cell-eval`/GEARS package specifics (fast-moving, actively maintained packages); VCC dataset bucket location should be re-verified at implementation time given the March 2026 migration precedent
