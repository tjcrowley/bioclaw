# Docker deployment

One image, one container, three Python interpreters. The backend serves both
the API and the built frontend on port 8000.

```bash
cp .env.example .env          # then fill in ANTHROPIC_API_KEY and BIOCLAW_WEB_PASSWORD
docker compose up
```

Open <http://localhost:8000/app>.

GPU-enabled (NVIDIA device passthrough on the same service):

```bash
docker compose -f docker-compose.yml -f docker-compose.gpu.yml up
```

> **Do not port-forward this to the internet.** The webapp has a single shared
> password, no account model, and no rate limiting. It is designed for a
> laptop, a lab workstation, or a trusted LAN. The `ANTHROPIC_API_KEY` in
> `.env` is readable by anyone who reaches the host — prefer a dedicated key
> with its own spend limit, and `chmod 600 .env`.

## Why the image is built the way it is

BioClaw needs **three mutually incompatible Python environments**, so the image
builds each in its own stage and copies the finished venv into the runtime:

| Environment | Python | Why it cannot share |
|---|---|---|
| main app | 3.13 | FastAPI + scanpy + Claude Agent SDK |
| scGPT worker | 3.9 | `torchtext` is archived upstream and only ships cp39 wheels; its exact pairing with `torch==2.3.0` is what avoids a dlopen crash |
| Geneformer worker | 3.10 | needs a newer torch than scGPT's pin allows |

The app never imports torch. `annotation/fm_client.py` and
`perturbation/geneformer_client.py` shell out to the worker interpreters as
subprocesses, which is what makes three conflicting dependency sets possible in
one image.

## What the build automates

Everything. There are no manual setup steps beyond `.env`.

| Stage | Produces |
|---|---|
| `main-builder` | root venv via `uv sync --frozen --extra web` |
| `scgpt-builder` | Python 3.9 venv, scGPT 0.2.4, torch 2.3.0, torchtext 0.18.0, and the whole-human checkpoint fetched via `gdown` |
| `reference-builder` | `cellxgene-census`-derived `reference.h5ad` (uses the **main** venv — the reference builder has no torch dependency) |
| `geneformer-builder` | Python 3.10 venv, Geneformer clone + LFS pull, CUDA-fallback patch, `transformers==4.46` |
| `runtime` | copies all of the above to the paths the client shims hardcode, then asserts they work |

Artifacts land at exactly these paths, because the client code already expects
them and was not modified:

```
/app/bio_fm_worker/checkpoints/scGPT_human/{args.json,best_model.pt,vocab.json}
/app/bio_fm_worker/reference/reference.h5ad
/app/geneformer_worker/src/Geneformer-V1-10M/
/app/geneformer_worker/src/geneformer/gene_dictionaries_30m/
```

Baking artifacts in at **build** time rather than first-run is deliberate
(14-RESEARCH.md Pattern 2): a reproducible, CI-able `docker build` failure is a
better researcher experience than a `docker compose up`-time network failure.

## Two things that will bite you if you edit the Dockerfile

**1. The interpreter relocation is load-bearing.** Each FM stage runs
`cp -a /usr/local /opt/pyXX` before creating its venv. `python -m venv` records
an *absolute* symlink at `.venv/bin/python`. The runtime stage is
`python:3.13-slim`, where `/usr/local/bin/python` **is 3.13** — so a venv built
the obvious way silently resolves to 3.13 after `COPY --from=`, while its
site-packages stay in `lib/python3.9`. Every cp39 wheel then vanishes behind
`ModuleNotFoundError` at first inference, long after a green build. This is not
hypothetical: it is exactly what shipped before Plan 14-03 fixed it.

**2. Builder-stage assertions cannot catch it.** Inside `scgpt-builder`,
`/usr/local/bin/python` genuinely is 3.9, so the torch/torchtext guard passes on
a venv that is already doomed. The decisive check has to run in the **runtime**
stage, after the COPY:

```dockerfile
RUN /app/bio_fm_worker/.venv/bin/python -c "\
import sys, torch, torchtext, scgpt; \
assert sys.version_info[:2] == (3, 9), 'scGPT venv resolved to ' + sys.version; ..."
```

If you add a stage, add its runtime assertion too.

## Platform: the image is amd64-only

Every stage is pinned `FROM --platform=linux/amd64`. This is forced, not a
preference: `torchtext` (archived upstream since 2023) and `scikit-misc`
publish no linux **aarch64** cp39 wheels, and a single image cannot mix
architectures across `COPY --from=`.

On Apple Silicon the build therefore runs under emulation and takes roughly an
hour from cold. It works, it is just slow. A native arm64 port is tracked as
Milestone v1.3 (`.planning/research/JETSON-ORIN-NANO.md`).

## Manual fallback if an automated fetch fails

Both FM artifact fetches hit third-party services that can fail independently of
your setup. If `docker build` dies in one of these steps, use the fallback
below — **do not script around the anti-automation controls.**

### scGPT checkpoint (Google Drive)

The model zoo's only distribution channel is Google Drive, which is not a
stable automatable API. Symptoms: `gdown` returns an HTML interstitial instead
of a file, a rate-limit page, or a permission wall. A tell-tale sign is a
`best_model.pt` that is a few KB instead of **~205MB**.

Fetch the three files onto the host by hand from the
[scGPT model zoo](https://github.com/bowang-lab/scGPT) (`scGPT_human`), place
them at `bio_fm_worker/checkpoints/scGPT_human/`, then bind-mount over the
image's copy:

```yaml
# docker-compose.override.yml
services:
  backend:
    volumes:
      - ./bio_fm_worker/checkpoints/scGPT_human:/app/bio_fm_worker/checkpoints/scGPT_human:ro
```

The exact file IDs the build uses are in the `Dockerfile` and in
`bio_fm_worker/checkpoints/scGPT_human/gdown.log`.

### Geneformer (Hugging Face LFS)

Symptoms: `git lfs pull` fails on auth or network, or succeeds but leaves
pointer stubs rather than real files. The include pattern **must** cover both
the checkpoint and the gene dictionaries:

```bash
GIT_LFS_SKIP_SMUDGE=1 git clone https://huggingface.co/ctheodoris/Geneformer geneformer_worker/src
cd geneformer_worker/src
git lfs pull --include="Geneformer-V1-10M/*,geneformer/gene_dictionaries_30m/*,geneformer/*.pkl"
```

Omitting `gene_dictionaries_30m` is a real, previously-hit failure: the
tokenizer raises `pickle.UnpicklingError` on the first real run, long after a
green build (`geneformer_worker/README.md`, "Real-run fixes" #1). Verify all
four pickles are present:

```
ensembl_mapping_dict_gc30M.pkl   gene_median_dictionary_gc30M.pkl
gene_name_id_dict_gc30M.pkl      token_dictionary_gc30M.pkl
```

Then bind-mount `./geneformer_worker/src` to `/app/geneformer_worker/src`.

### cellxgene-census reference index

Requires network at build time and is pinned to `CENSUS_VERSION = "2025-11-08"`
(`annotation/reference.py`). To rebuild on the host:

```bash
uv run python -c "from annotation.reference import build_reference_index; build_reference_index()"
```

Produces `bio_fm_worker/reference/reference.h5ad` (~30MB); bind-mount as above.

## Known gaps

**Image size is 15.6GB.** A large share is an unconstrained CUDA stack in the
Geneformer venv: `pip install -e` on the vendored source resolves a bare `torch`
dependency to the newest release plus ~3.0GB of `nvidia_*` wheels — in an image
whose Geneformer worker is deliberately patched to run on **CPU**
(`docker/geneformer_cuda_fallback.patch`, ~15 hardcoded `device="cuda"` sites).
The scGPT stage already avoids this by pre-installing its pin; the Geneformer
stage does not. Tracked in
`.planning/phases/14-docker-compose-deployment/deferred-items.md`.

**Build is slow on Apple Silicon** — see the platform note above.

**No GPU is used by default.** `docker-compose.yml` reserves no devices; GPU
passthrough only happens with the `docker-compose.gpu.yml` overlay, and only on
a CUDA-capable host with the NVIDIA Container Toolkit installed.

## State persistence

Session data, the agent memory SQLite DB, and the tool-call log all live under
`/app/state`, backed by the named volume `bioclaw-state`:

```
BIOCLAW_STORE_ROOT=/app/state/data
BIOCLAW_MEMORY_DB=/app/state/agent/memory.sqlite
BIOCLAW_LOG_PATH=/app/state/tool_calls.jsonl
```

`docker compose down` preserves the volume; state survives a restart. To wipe
it deliberately:

```bash
docker compose down -v
```

## The single-worker constraint

`webapp/backend/streaming.py` keeps its queue registry **in memory**, so the
backend is single-process only. More than one worker silently breaks live
tool-activity streaming.

The constraint lives in the image's own `ENTRYPOINT` (`docker/entrypoint.sh`),
which execs a fixed uvicorn command and **ignores all arguments**. A compose
`command:` override or trailing `docker run` args cannot reintroduce
`--workers`. `scripts/docker_compose_smoke_test.sh` asserts no
`command:`/`entrypoint:` key exists in the resolved config.

Verify it directly:

```bash
docker compose exec backend cat /proc/1/cmdline | tr '\0' ' '
# .../uvicorn webapp.backend.main:app --host 0.0.0.0 --port 8000 --workers 1
```

## Smoke test

```bash
sh scripts/docker_compose_smoke_test.sh
```

Validates the no-override constraint, the blank-password guard, a full build,
a healthy `/api/health`, and clean teardown.
