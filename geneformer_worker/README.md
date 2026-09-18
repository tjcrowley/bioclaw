# geneformer_worker/ — isolated Geneformer environment

A second, separate Python environment, deliberately outside both the root
project's `.venv`/`pyproject.toml` *and* `bio_fm_worker/.venv`. Geneformer
requires Python >=3.10 and pulls in a new, largely unpinned `torch`/
`transformers` stack that is incompatible with `bio_fm_worker/.venv`'s
pinned `torch==2.3.0`/`torchtext==0.18.0` scGPT combination (13-RESEARCH.md
Anti-Patterns) — merging the two would reintroduce the exact ABI-mismatch
class of bug `bio_fm_worker/README.md` documents fixing for scGPT.
`perturbation/geneformer_client.py` (Plan 13-03) will talk to this
environment only via `subprocess`, never via a direct import, mirroring
`annotation/fm_client.py`'s existing pattern for `bio_fm_worker/`.

Geneformer has no PyPI package — it is installed via `git clone` from
Hugging Face (`ctheodoris/Geneformer`) followed by an editable `pip install`.

## How it was created

```bash
python3.10 -m venv geneformer_worker/.venv
geneformer_worker/.venv/bin/pip install --upgrade pip
git lfs install
GIT_LFS_SKIP_SMUDGE=1 git clone https://huggingface.co/ctheodoris/Geneformer geneformer_worker/src
cd geneformer_worker/src && git lfs pull --include="Geneformer-V1-10M/*" && cd -
geneformer_worker/.venv/bin/pip install -e geneformer_worker/src
geneformer_worker/.venv/bin/python -c "import geneformer; print('geneformer OK')"
```

Only the smallest checkpoint directory, `Geneformer-V1-10M/*`, was pulled via
LFS (per 13-RESEARCH.md's CPU-feasibility recommendation) — the larger
`Geneformer-V2-104M`, `Geneformer-V2-104M_CLcancer`, and `Geneformer-V2-316M`
directories were left un-smudged (LFS pointer files only, ~130 bytes each)
and were never downloaded.

Python version: **3.10.14** (`/opt/homebrew/bin/python3.10`, confirmed
present on this machine by 13-RESEARCH.md). This is Geneformer's stated
floor (`python_requires=">=3.10"` in its `setup.py`) — one full minor version
above `bio_fm_worker/.venv`'s Python 3.9.6 and one+ below the root project's
`>=3.12` floor. Fully isolated; this interpreter version has no bearing on
either of the other two environments.

## Install outcome: SUCCESS (2026-09-17) — `import geneformer` works

The editable install (`pip install -e geneformer_worker/src`) resolved
cleanly on the first attempt, including `torch-2.14.0` and the *unpinned*
latest `transformers-5.17.0` (Geneformer's `setup.py` `install_requires`
lists `transformers` with no version constraint, unlike its
`requirements.txt`, which does pin `transformers==4.46`).

That first-attempt install **did not** actually work — `import geneformer`
failed:

```
ImportError: cannot import name 'SpecialTokensMixin' from 'transformers'
```

`transformers-5.17.0`'s public API removed/moved `SpecialTokensMixin`,
which one of Geneformer's own submodules
(`geneformer/collator_for_classification.py`) still imports directly.
Repinning to the exact version Geneformer's own `requirements.txt`
specifies fixed it:

```bash
geneformer_worker/.venv/bin/pip install "transformers==4.46"
```

(`4.46.0` is flagged by PyPI as a **yanked** release — "does not work with
3.8 but we did not drop the support yet" — this warning is about Python 3.8
support, not 3.10, and is unrelated to the ABI issue above; the yank is
benign for this environment.)

Verified after the repin:

```bash
geneformer_worker/.venv/bin/python -c "
from geneformer import TranscriptomeTokenizer, EmbExtractor, InSilicoPerturber, InSilicoPerturberStats
print('four-step pipeline classes import OK')
"
# -> four-step pipeline classes import OK
```

All four of the pipeline's classes (`TranscriptomeTokenizer.tokenize_data()`
-> `EmbExtractor.extract_embs()` -> `InSilicoPerturber.perturb_data()` ->
`InSilicoPerturberStats.get_stats()`, per 13-RESEARCH.md's "Four-Step
Pipeline" section) import without error.

If this venv is ever rebuilt from scratch, pin `transformers==4.46`
immediately after `pip install -e geneformer_worker/src` and before
anything imports `geneformer`/`transformers`, mirroring
`bio_fm_worker/README.md`'s equivalent `torch==2.3.0` repin note — otherwise
a bare re-resolve can silently pull the latest, incompatible `transformers`
again.

**Checkpoint used:** `Geneformer-V1-10M` (79 MB on disk after LFS pull),
the smallest available checkpoint, chosen for CPU-feasible smoke testing per
13-RESEARCH.md.

**No manual step remains for this plan's `user_setup` entry** — the
automated LFS pull for `Geneformer-V1-10M` succeeded without hitting a
network, auth, or LFS-quota wall. Plan 13-04's `checkpoint:human-verify`
step is where any *future* re-run's manual fallback (documented in this
plan's `user_setup`) would be resolved, if the automated pull ever fails on
a different machine/checkout.

## Worker script

`geneformer_worker/run_geneformer_perturb.py` (Plan 13-03) implements the
real match-rate computation against Geneformer's token vocabulary and the
four-step pipeline orchestration with its on-disk checkpoints between
stages, mirroring `bio_fm_worker/run_scgpt_embed.py`'s subprocess-worker
shape.

## Real-run fixes (Plan 13-04 Task 3, 2026-09-17)

Three real bugs surfaced only by running the actual (unmocked) four-step
pipeline end to end against this checkpoint -- none were caught by the
mocked unit tests in Plans 13-02/13-03, since those never execute real
`geneformer`/`torch` code:

1. **Missing V1 gene dictionaries (LFS pointer stubs).** The original
   `git lfs pull --include="Geneformer-V1-10M/*"` (see "How it was created"
   above) only fetched the checkpoint weights -- it missed
   `geneformer/gene_dictionaries_30m/*.pkl` (token dictionary, gene median,
   Ensembl mapping, gene name/ID dict), which live outside that path and are
   required by `TranscriptomeTokenizer` for any V1 run. Those `.pkl` files
   were still ~131-byte LFS pointer stubs, causing
   `pickle.UnpicklingError: invalid load key, 'v'` (`'v'` from the pointer
   file's `"version https://git-lfs..."` text) on first tokenize. Fixed by:
   `cd geneformer_worker/src && git lfs pull --include="geneformer/gene_dictionaries_30m/*,geneformer/*.pkl"`.
   If `src/` is ever rebuilt from scratch, add this to the LFS pull step in
   "How it was created" above -- the original single `--include` was
   insufficient.

2. **Unconditional `device="cuda"` in the vendored `geneformer` package.**
   `geneformer/emb_extractor.py`, `geneformer/in_silico_perturber.py`, and
   `geneformer/perturber_utils.py` (as of upstream commit `1f7fbae`, 2026-09-12)
   hardcode `device="cuda"` / `.to("cuda")` in ~15 spots with no
   `torch.cuda.is_available()` fallback -- unlike `bio_fm_worker`'s scGPT,
   which silently falls back to CPU (13-RESEARCH.md). This is a known,
   unresolved upstream limitation (a community fork,
   `petadimensionlab/Geneformer`, exists specifically to add a central
   CPU/multi-backend device resolver). Patched **in place** in this
   machine's `geneformer_worker/src/` checkout: every unconditional
   `device="cuda"` / `.to("cuda")` now resolves
   `"cuda" if torch.cuda.is_available() else "cpu"`, and every
   `torch.cuda.empty_cache()` is guarded by the same check. **This patch is
   NOT tracked by git** (`geneformer_worker/src/` is gitignored by the root
   `.gitignore` as a separate nested clone) -- if `src/` is ever deleted and
   re-cloned/re-installed on this or any other CPU-only machine, these same
   ~15 edits must be reapplied before a real (non-CUDA) run will succeed.
   Search for `device="cuda"` / `.to("cuda")` / `torch.cuda.empty_cache()` in
   `emb_extractor.py`, `in_silico_perturber.py`, and `perturber_utils.py` to
   find every spot.

3. **`InSilicoPerturberStats.get_stats()` returns `None`, not the stats
   DataFrame.** `run_geneformer_perturb.py`'s `_run_pipeline()` originally
   assumed `get_stats()`'s return value was the aggregated cosine-shift
   DataFrame (mirroring how most of Geneformer's other pipeline methods
   behave) -- verified via `inspect.getsource` that its body ends on
   `cos_sims_df.to_csv(output_path)` with no `return` statement at all. This
   produced `'NoneType' object is not subscriptable` in
   `_build_ranked_genes()`. Fixed (and committed, unlike fixes #1/#2 above)
   by reading the just-written `<output_directory>/<output_prefix>.csv`
   back via `pandas.read_csv()` instead of trusting a return value.

Verified end to end after all three fixes: `uv run pytest
tests/test_geneformer_integration.py -m geneformer_smoke -x -v -s` passes,
real latency ~14s for a 24-cell/18-gene smoke fixture, non-degenerate
cosine-shift values (range ~0.86-0.995 across 17 affected genes, target
gene ACTB).
