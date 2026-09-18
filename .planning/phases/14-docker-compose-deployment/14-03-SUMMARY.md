---
phase: 14-docker-compose-deployment
plan: 03
subsystem: docker
tags: [docker, dockerfile, scgpt, geneformer, multi-interpreter, checkpoints, emulation]

# Dependency graph
requires:
  - phase: 14
    plan: 02
    provides: multi-stage Dockerfile with main-builder + runtime stages, WORKDIR /app, non-overridable single-worker ENTRYPOINT
  - phase: 14
    plan: 01
    provides: docker/geneformer_cuda_fallback.patch (CUDA-fallback for ~15 hardcoded device="cuda" sites)
provides:
  - Buildable `bioclaw:latest` (15.6GB) containing all three Python interpreters
  - scgpt-builder stage (Python 3.9) — scGPT 0.2.4 + torch 2.3.0 + torchtext 0.18.0 + whole-human checkpoint
  - reference-builder stage (FROM main-builder) — cellxgene-census reference.h5ad
  - geneformer-builder stage (Python 3.10) — Geneformer V1-10M + gene dictionaries + CUDA patch
  - Runtime-stage assertions proving each venv resolves to its own interpreter AFTER the COPY
affects: [14-05-docs, 15-jetson-port]

# Tech tracking
tech-stack:
  added:
    - "python:3.9-slim, python:3.10-slim builder stages (verified against Docker Engine 29.3.1)"
    - "ipython==8.18.1 in the scGPT venv (undeclared upstream dependency)"
    - "build-essential in the geneformer-builder stage (Cython sdist compilation)"
  patterns:
    - "Interpreter relocation: `cp -a /usr/local /opt/pyXX` before venv creation, so .venv/bin/python's absolute symlink stays valid after COPY into a runtime image owning a different /usr/local/bin/python"
    - "Runtime-stage import assertions, not just builder-stage ones — a builder guard cannot catch a venv broken by the COPY itself"
    - "Cache-preserving fix placement: new RUN steps appended AFTER expensive rate-limited layers (gdown, git lfs pull) rather than beside logically-related ones"

key-files:
  created:
    - .planning/phases/14-docker-compose-deployment/14-03-SUMMARY.md
  modified:
    - Dockerfile

key-decisions:
  - "Interpreter relocation is load-bearing, and the previously-shipped image proves it: `bioclaw:latest` built before this plan had a scGPT venv whose bin/python resolved to Python 3.13.15 while its site-packages sat in lib/python3.9, so `import torch` raised ModuleNotFoundError at first inference despite a fully green build. `cp -a /usr/local /opt/py39` keeps the venv's absolute interpreter symlink valid in the runtime stage."
  - "Added runtime-stage assertions rather than trusting the builder-stage torch/torchtext guard. That guard passed green on the broken image — it runs in the builder, where /usr/local/bin/python IS 3.9. The decisive check `sys.version_info[:2] == (3, 9)` can only be made after the COPY."
  - "scgpt 0.2.4 has an UNDECLARED dependency on IPython: its metadata lists 14 Requires-Dist entries with no ipython, yet scgpt/utils/util.py:16 does `from IPython import get_ipython` at module top level. Cross-checked every scgpt top-level import against all 154 packages pip installed — IPython was the only one with no provider; the rest arrive transitively via scanpy/scvi-tools. Pinned to 8.18.1, the last release supporting Python 3.9."
  - "Added a builder-stage `import scgpt` + GeneVocab assertion. The pre-existing guard imported only torch/torchtext, so an unimportable scgpt survived the entire builder stage and surfaced at runtime step 12/13 — after every checkpoint download, the census index build, and all COPYs. Now it fails in seconds."
  - "build-essential added to geneformer-builder: geneformer -> tdigest -> accumulation-tree, a Cython package publishing only a 12kB sdist and no wheels for any platform/Python. python:3.10-slim has no compiler. Because pip builds sdists only after resolving and downloading the whole graph, this 12kB package failed the step LAST, ~50 minutes and ~3GB of successful downloads in."
  - "Both fixes placed after their stage's expensive layer (gdown checkpoints; git lfs pull) purely to preserve cache. Touching the earlier layers would re-pull ~1.5GB from Google Drive, an anti-automation surface that rate-limits (14-RESEARCH.md Pitfall 2)."

requirements-completed: [DOCK-01]

# Metrics
duration: ~3h (dominated by three full build cycles under x86_64 emulation)
completed: 2026-09-18
---

# Phase 14 Plan 03: scGPT, reference-index, and Geneformer builder stages

**`bioclaw:latest` (15.6GB) now contains three isolated Python interpreters — main 3.13.15, scGPT 3.9.25, Geneformer 3.10.21 — each with its own venv, both FM checkpoints, and the cellxgene-census reference index, all at the exact repo-relative paths the existing subprocess shims already hardcode.**

The Dockerfile grew 208 lines across three new stages. No client code changed: `annotation/fm_client.py` and `perturbation/geneformer_client.py` were already written against these paths and remain untouched.

## Verification

All run live against Docker Engine 29.3.1.

### Build-time (final build, `DOCKER_BUILD_EXIT=0`)

```
#36 [scgpt-builder 7/7]        scgpt import OK 0.2.4
#39 [geneformer-builder 11/11] geneformer OK
#47 [runtime 12/13]            runtime scGPT OK: 3.9.25 2.3.0+cu121
#47 [runtime 12/13]            runtime Geneformer OK: 3.10.21
```

Step 47 additionally `&&`-chains `test -d /app/geneformer_worker/src/Geneformer-V1-10M`
and `test -f /app/bio_fm_worker/reference/reference.h5ad`; reaching exit 0 means both passed.

### Runtime (fresh containers, not build-time RUN steps)

This distinction is the whole point — the previously-shipped image passed every
build-time check and still had an unimportable torch.

| venv | interpreter | stack |
|---|---|---|
| `/app/bio_fm_worker/.venv` | 3.9.25 | torch 2.3.0+cu121, torchtext 0.18.0+cpu, scgpt 0.2.4 |
| `/app/geneformer_worker/.venv` | 3.10.21 | geneformer imports |
| `/app/.venv` | 3.13.15 | — |

### Baked artifacts at client-expected paths

```
/app/bio_fm_worker/checkpoints/scGPT_human/   args.json 1300 | best_model.pt 205385258 | vocab.json 1317639
/app/bio_fm_worker/reference/reference.h5ad   29893945
/app/geneformer_worker/src/Geneformer-V1-10M  config.json, model.safetensors, pytorch_model.bin, training_args.bin
/app/geneformer_worker/src/geneformer/gene_dictionaries_30m/
    ensembl_mapping_dict_gc30M.pkl, gene_median_dictionary_gc30M.pkl,
    gene_name_id_dict_gc30M.pkl, token_dictionary_gc30M.pkl
```

`best_model.pt` at 205MB is real weights, not a Google Drive HTML interstitial —
Pitfall 2 did not bite. All four gene dictionary pickles are present, satisfying
`geneformer_worker/README.md` "Real-run fixes" #1, whose original single-path
include pattern missed this sibling directory and caused a pickle.UnpicklingError.
The CUDA-fallback patch is applied (`emb_extractor.py` shows the CPU-fallback guards).

## What went wrong, in order

Three full build cycles were needed. Each failure was real and each fix is now
encoded in the Dockerfile with its reasoning.

1. **`gcc` missing** — `accumulation-tree` (via `tdigest`) is Cython, sdist-only.
   Failed ~50min in, after ~3GB of successful downloads, because pip defers sdist
   builds until the whole graph resolves. Fixed with `build-essential`.
2. **`IPython` missing** — undeclared upstream dependency of scgpt 0.2.4. Failed at
   runtime step 12/13. Fixed with `ipython==8.18.1` plus a new builder-stage
   `import scgpt` guard so this class now fails in seconds rather than ~40 minutes.
3. **Green.**

A process note worth recording: the first build was initially misread as successful
because its wrapper ended in `echo "BUILD EXITED WITH CODE $?"`, which always exits 0
and masked Docker's exit 1. Subsequent builds wrote `DOCKER_BUILD_EXIT=$?` into the
log and were verified by reading that line, not the task's exit status.

## Deviations from plan

- **Platform pin.** Every stage is `FROM --platform=linux/amd64`, not the plan's bare
  `FROM`. Forced, not preferred: `torchtext` (archived upstream since 2023) and
  `scikit-misc` publish no linux aarch64 cp39 wheels, and a single image cannot mix
  architectures across `COPY --from=`. On this Apple Silicon host every stage therefore
  runs under emulation, which is why build cycles are ~50min. Directly motivates Phase 15.
- **torch pre-install order.** The plan (from `bio_fm_worker/README.md`) runs
  `pip install scgpt` then pins `torch==2.3.0`. The Dockerfile pre-installs the pin
  first so the resolver never fetches torch 2.8.0 + CUDA 12.8 only to discard it. The
  README's actual invariant — the pin re-asserted before anything imports torch — is
  preserved by a third `pip install "torch==2.3.0"` line.
- **Two dependency fixes** not in the plan (`build-essential`, `ipython==8.18.1`), both
  required to make the plan's own commands succeed in a clean container.

## Known issues

- **Image is 15.6GB.** A large share is an unconstrained CUDA 13 stack in the Geneformer
  venv — logged in `deferred-items.md`. `pip install -e /opt/geneformer_src` resolves a
  bare `torch` dependency to **torch 2.14.0** plus ~3.0GB of `nvidia_*` wheels, in an
  image whose Geneformer worker Plan 14-01 deliberately patched to run on CPU. The scGPT
  stage already solves exactly this problem for exactly this reason; the Geneformer stage
  never got the same treatment. Not fixed here — changing the resolved torch version is a
  behaviour change deserving its own verification.
- **No end-to-end inference test yet.** These assertions prove the environments import and
  the artifacts exist at the right paths. They do not prove a real annotation or
  perturbation run completes through the subprocess shims. That is Plan 14-05's smoke test.
