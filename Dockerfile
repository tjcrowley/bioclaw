# syntax=docker/dockerfile:1

# Every stage is pinned to linux/amd64 rather than inheriting the builder's
# native platform. This is forced, not a preference: the scGPT worker (Python
# 3.9) needs `scikit-misc` and `torchtext`, and neither publishes a linux
# aarch64 cp39 wheel. `torchtext` has been archived upstream since 2023, so one
# will never be published -- and its exact pairing with torch==2.3.0 is what
# fixes the dlopen crash documented in bio_fm_worker/README.md. Building on an
# arm64 host (Apple Silicon) therefore works only under emulation, which is
# slow but correct. A single image cannot mix architectures across
# `COPY --from=`, so the pin applies to all stages, not just the FM ones.
# The intended deployment target is amd64 Linux anyway -- docker-compose.gpu.yml
# reserves an nvidia GPU, which does not exist on arm64 Macs.
FROM --platform=linux/amd64 python:3.13-slim AS main-builder
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/
WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --extra web --no-install-project
COPY . .
RUN uv sync --frozen --extra web

# --- Stage: scGPT worker venv (Python 3.9) ---
FROM --platform=linux/amd64 python:3.9-slim AS scgpt-builder
# Deviation from bio_fm_worker/README.md's literal command order, for cost not
# behaviour. The README runs `pip install scgpt` then pins `torch==2.3.0`. Done
# in that order pip first resolves torch 2.8.0 (888MB) plus the whole CUDA 12.8
# stack (nvidia_cublas_cu12 alone is 594MB), then discards it to download
# torch 2.3.0 and CUDA 12.1 -- multiple GB downloaded twice.
#
# scgpt 0.2.4 requires only `torch>=1.13.0`, so pre-installing the pin means the
# resolver already finds it satisfied and never fetches 2.8.0. The README's
# actual invariant -- that the pin is re-asserted immediately after scgpt and
# before anything imports torch -- is preserved by the third line, which is a
# no-op when scgpt left torch alone and a repair if it did not. The matched
# torch 2.3.0 / torchtext 0.18.0 pair is load-bearing: torchtext is archived
# upstream and its compiled extension dlopen-crashes against newer torch ABIs.
#
# The pip cache mount matters here specifically because this stage is multi-GB
# over an emulated x86_64 layer; without it every retry of a later failing step
# re-downloads everything.
# The venv is built from a RELOCATED copy of the 3.9 interpreter rather than
# from /usr/local, and that is load-bearing. `python -m venv` records an
# absolute symlink at .venv/bin/python pointing at the interpreter that created
# it. The final runtime stage is python:3.13-slim, where /usr/local/bin/python
# IS 3.13 -- so a venv built the obvious way silently resolves to 3.13 after the
# `COPY --from=`, while its site-packages stay at lib/python3.9. Every cp39 wheel
# in it (torch 2.3.0, torchtext) then disappears behind ModuleNotFoundError at
# first inference, long after a green build. Copying 3.9 to a prefix 3.13 does
# not own keeps that symlink valid in the runtime image. Safe because every base
# image here is Debian 13 trixie, so the relocated interpreter's system
# libraries resolve identically.
RUN cp -a /usr/local /opt/py39

RUN --mount=type=cache,target=/root/.cache/pip \
    /opt/py39/bin/python3.9 -m venv /opt/bio_fm_worker_venv \
 && /opt/bio_fm_worker_venv/bin/pip install --upgrade pip \
 && /opt/bio_fm_worker_venv/bin/pip install "torch==2.3.0" \
 && /opt/bio_fm_worker_venv/bin/pip install scgpt \
 && /opt/bio_fm_worker_venv/bin/pip install "torch==2.3.0"

# Fail the build loudly on the exact regression bio_fm_worker/README.md
# documents: a silently re-upgraded torch whose ABI breaks torchtext's
# compiled extension. Importing torchtext here is the point -- that import is
# what dlopen-crashes on a mismatched pair, and catching it at build time is
# far cheaper than catching it at first inference.
RUN /opt/bio_fm_worker_venv/bin/python -c "\
import torch, torchtext; \
assert torch.__version__.startswith('2.3.0'), 'torch got re-upgraded to ' + torch.__version__; \
print('torch', torch.__version__, '/ torchtext', torchtext.__version__)"

# scGPT whole-human checkpoint (bowang-lab/scGPT model zoo, Google Drive --
# not a stable automatable API, 14-RESEARCH.md Pitfall 2. Individual
# file-ID fetches, not --folder, to avoid the double-nesting bug
# 04-05-SUMMARY.md documented. If this RUN step fails (interactive
# confirmation page / rate limit), see docker/README.md's manual fallback
# (added in Plan 14-05) -- do not script around an anti-automation control.
RUN --mount=type=cache,target=/root/.cache/pip \
    mkdir -p /app/bio_fm_worker/checkpoints/scGPT_human \
 && /opt/bio_fm_worker_venv/bin/pip install gdown \
 && /opt/bio_fm_worker_venv/bin/gdown "https://drive.google.com/uc?id=1hh2zGKyWAx3DyovD30GStZ3QlzmSqdk1" -O /app/bio_fm_worker/checkpoints/scGPT_human/args.json \
 && /opt/bio_fm_worker_venv/bin/gdown "https://drive.google.com/uc?id=14AebJfGOUF047Eg40hk57HCtrb0fyDTm" -O /app/bio_fm_worker/checkpoints/scGPT_human/best_model.pt \
 && /opt/bio_fm_worker_venv/bin/gdown "https://drive.google.com/uc?id=1H3E_MJ-Dl36AQV6jLbna2EdvgPaqvqcC" -O /app/bio_fm_worker/checkpoints/scGPT_human/vocab.json

# scgpt 0.2.4 has an UNDECLARED runtime dependency on IPython. Its metadata
# lists 14 Requires-Dist entries and ipython is not among them, yet
# scgpt/utils/util.py:16 does `from IPython import get_ipython` at module top
# level -- so `pip install scgpt` yields a venv where `import scgpt` raises
# ModuleNotFoundError. Verified against this build: of the 154 packages pip
# installed here, IPython is the ONLY scgpt top-level import with no provider;
# every other one (matplotlib, seaborn, sklearn, anndata, tqdm, ...) arrives
# transitively through scanpy/scvi-tools. The dev host masks the bug because
# something unrelated pulled IPython in there; a clean container does not.
# 8.18.1 is the final release supporting Python 3.9 and matches the host.
#
# Placed after the checkpoint fetch rather than beside the scgpt install purely
# to keep that layer cached -- re-running gdown re-downloads ~1.5GB from Google
# Drive, an anti-automation surface that rate-limits (14-RESEARCH.md Pitfall 2).
RUN --mount=type=cache,target=/root/.cache/pip \
    /opt/bio_fm_worker_venv/bin/pip install "ipython==8.18.1"

# Import scgpt ITSELF, not merely its torch stack. The guard above proves the
# torch/torchtext ABI pair loads; that is a different failure mode and says
# nothing about whether the scgpt package is importable. Without this step an
# unimportable scgpt survives the whole builder stage and only surfaces in the
# runtime assertion at step 12/13 -- after every checkpoint download, the
# reference index build, and all the COPYs have already run. GeneVocab is
# imported specifically because it is the torchtext-dependent class the shim in
# annotation/fm_client.py actually constructs.
RUN /opt/bio_fm_worker_venv/bin/python -c "\
import scgpt; \
from scgpt.tokenizer.gene_tokenizer import GeneVocab; \
print('scgpt import OK', scgpt.__version__)"

# --- Stage: cellxgene-census reference index (uses the MAIN venv, not
# the scGPT worker venv -- annotation/reference.py has no torch dependency) ---
FROM main-builder AS reference-builder
RUN /app/.venv/bin/python -c "from annotation.reference import build_reference_index; build_reference_index()"

# --- Stage: Geneformer worker venv (Python 3.10) ---
FROM --platform=linux/amd64 python:3.10-slim AS geneformer-builder
RUN apt-get update && apt-get install -y --no-install-recommends git git-lfs \
 && git lfs install \
 && rm -rf /var/lib/apt/lists/*

# Same relocation as the scGPT stage, for the same reason -- see the comment
# above /opt/py39. A 3.10 venv whose bin/python resolves to the runtime's 3.13
# is just as broken as a 3.9 one.
RUN cp -a /usr/local /opt/py310

RUN /opt/py310/bin/python3.10 -m venv /opt/geneformer_worker_venv \
 && /opt/geneformer_worker_venv/bin/pip install --upgrade pip

# Geneformer has no PyPI package -- git clone + editable install
# (geneformer_worker/README.md "How it was created"). GIT_LFS_SKIP_SMUDGE
# defers the large-file pull to the next RUN so the include pattern below
# is explicit and auditable as its own layer.
RUN GIT_LFS_SKIP_SMUDGE=1 git clone https://huggingface.co/ctheodoris/Geneformer /opt/geneformer_src

# Include pattern MUST cover both the V1-10M checkpoint AND the gene
# dictionaries (geneformer_worker/README.md "Real-run fixes" #1 -- the
# original single-path include missed a sibling directory the tokenizer
# also needs, causing a pickle.UnpicklingError on first real tokenize).
RUN cd /opt/geneformer_src \
 && git lfs pull --include="Geneformer-V1-10M/*,geneformer/gene_dictionaries_30m/*,geneformer/*.pkl"

# Apply the CUDA-fallback patch from Plan 14-01 BEFORE pip install -e --
# the vendored package hardcodes device="cuda" in ~15 spots with no CPU
# fallback (geneformer_worker/README.md "Real-run fixes" #2); applying
# after install would be equally correct but applying before keeps the
# installed package and the on-disk source in sync from the start.
COPY docker/geneformer_cuda_fallback.patch /tmp/geneformer_cuda_fallback.patch
RUN cd /opt/geneformer_src && git apply /tmp/geneformer_cuda_fallback.patch

# A C toolchain is required, not defensive. Geneformer depends on `tdigest`,
# which depends on `accumulation-tree` -- a Cython package publishing only an
# sdist (accumulation_tree-0.6.4.tar.gz, 12kB) and no wheels for any platform
# or Python version. It must compile at install time, and python:3.10-slim
# ships no compiler, so the install below dies with
# `error: [Errno 2] No such file or directory: 'gcc'`. That failure surfaces
# ~50 minutes in, because pip builds sdists only after resolving and
# downloading every wheel in the graph -- so one missing 12kB package fails the
# step last, after ~3GB of successful downloads.
#
# Installed here rather than beside git/git-lfs at the top of the stage so the
# cached LFS checkout above stays valid; adding a package to that first layer
# invalidates the clone and forces a multi-GB re-pull under emulation.
# Nothing leaks into the final image -- the runtime stage copies only
# /opt/py310, the venv, and the source checkout.
RUN apt-get update && apt-get install -y --no-install-recommends build-essential \
 && rm -rf /var/lib/apt/lists/*

RUN --mount=type=cache,target=/root/.cache/pip \
    /opt/geneformer_worker_venv/bin/pip install -e /opt/geneformer_src \
 && /opt/geneformer_worker_venv/bin/pip install "transformers==4.46"
RUN /opt/geneformer_worker_venv/bin/python -c "from geneformer import TranscriptomeTokenizer, EmbExtractor, InSilicoPerturber, InSilicoPerturberStats; print('geneformer OK')"

# --- Final runtime stage ---
FROM --platform=linux/amd64 python:3.13-slim AS runtime
WORKDIR /app
COPY --from=main-builder /app /app
# The two relocated interpreters must land before the venvs that symlink into
# them; each venv's bin/python is an absolute path into these prefixes.
COPY --from=scgpt-builder /opt/py39 /opt/py39
COPY --from=geneformer-builder /opt/py310 /opt/py310

COPY --from=scgpt-builder /opt/bio_fm_worker_venv /app/bio_fm_worker/.venv
COPY --from=scgpt-builder /app/bio_fm_worker/checkpoints /app/bio_fm_worker/checkpoints
COPY --from=reference-builder /app/bio_fm_worker/reference /app/bio_fm_worker/reference
COPY --from=geneformer-builder /opt/geneformer_worker_venv /app/geneformer_worker/.venv

# `pip install -e` records the absolute build-time path /opt/geneformer_src in
# the venv's __editable__ finder, so the source must remain reachable there or
# `import geneformer` fails in the runtime image even though the venv is intact
# (14-03-PLAN.md Task 3). Keeping the checkout at its recorded path and
# symlinking the repo-relative path onto it satisfies both the editable finder
# and perturbation/geneformer_client.py's hardcoded
# model_dir="geneformer_worker/src/Geneformer-V1-10M", without duplicating a
# multi-GB LFS checkout. .dockerignore excludes geneformer_worker/src/, so
# nothing from main-builder occupies this path.
COPY --from=geneformer-builder /opt/geneformer_src /opt/geneformer_src
RUN ln -sfn /opt/geneformer_src /app/geneformer_worker/src

# Assert the FM environments work in THIS stage, not just in their builders.
# The builder-stage torch/torchtext guard above cannot catch a venv broken by
# the COPY itself -- it passed green while the shipped image raised
# ModuleNotFoundError, because bin/python resolved to the runtime's 3.13. These
# imports run through the exact interpreters and paths the subprocess shims in
# annotation/fm_client.py and perturbation/geneformer_client.py invoke.
RUN /app/bio_fm_worker/.venv/bin/python -c "\
import sys, torch, torchtext, scgpt; \
assert sys.version_info[:2] == (3, 9), 'scGPT venv resolved to ' + sys.version; \
assert torch.__version__.startswith('2.3.0'), 'torch is ' + torch.__version__; \
print('runtime scGPT OK:', sys.version.split()[0], torch.__version__)" \
 && /app/geneformer_worker/.venv/bin/python -c "\
import sys, geneformer; \
assert sys.version_info[:2] == (3, 10), 'Geneformer venv resolved to ' + sys.version; \
print('runtime Geneformer OK:', sys.version.split()[0])" \
 && test -d /app/geneformer_worker/src/Geneformer-V1-10M \
 && test -f /app/bio_fm_worker/reference/reference.h5ad

RUN chmod +x /app/docker/entrypoint.sh
ENV BIOCLAW_STORE_ROOT=/app/state/data
ENV BIOCLAW_MEMORY_DB=/app/state/agent/memory.sqlite
ENV BIOCLAW_LOG_PATH=/app/state/tool_calls.jsonl
EXPOSE 8000
ENTRYPOINT ["/app/docker/entrypoint.sh"]
