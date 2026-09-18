# Roadmap Item: Jetson Orin Nano 8GB Edge Appliance

**Status:** ROADMAP ONLY — not planned into executable plans, not built.
**Researched:** 2026-09-18
**Decisions locked:** 2026-09-18 (Darren)
**Depends on:** Phase 14 complete (14-03 image bake + 14-05 docs still outstanding)
**Proposed as:** Milestone v1.3, Phases 15 (port) + 16 (appliance)

---

## What this is

BioClaw as a self-contained benchtop appliance on an NVIDIA Jetson Orin Nano 8GB:
plug it in, it boots into a working stack, a researcher finds it on the lab
network and uses it. No attached monitor, no terminal, no `docker` commands.

**Scope boundary, stated once:** this is edge *tool execution*, not an edge LLM.
`qa/session.py::ask_question()` still calls the Anthropic API over the network.
The Orin runs scanpy, scGPT, and Geneformer locally. The appliance needs
internet; it is not offline-capable, and making it so is a separate project.

---

## Locked decisions

### 1. JetPack 6.2 — DECIDED

L4T r36.x, Ubuntu 22.04, **Python 3.10**, CUDA 12.6.

Load-bearing consequence: the host's system Python is 3.10, which is exactly
what `geneformer_worker/.venv` already requires, and NVIDIA's cp310 CUDA torch
wheels target it. JetPack 7.x (Ubuntu 24.04 / Python 3.12 / CUDA 13) would mean
revalidating the Geneformer venv against a Python version it has never run on.

This pins the L4T base image tag and the container CUDA version. **Container
CUDA must match host JetPack** — there is no runtime fallback if they diverge,
and a JetPack upgrade on the device is an image rebuild, not a `docker pull`.
Say so in the appliance docs.

### 2. scGPT: shim out torchtext, gated on a blocking spike — MY CALL, DECIDED

**Track A (chosen): replace torchtext's `Vocab` with a pure-Python shim.**

scGPT touches torchtext in exactly one place —
`scgpt/tokenizer/gene_tokenizer.py:11-12`, where `GeneVocab` subclasses
`torchtext.vocab.Vocab`. The exercised surface is `__init__(vocab)`,
`insert_token`, `set_default_index`, `get_stoi`, `get_itos`, `__getitem__`,
`__contains__`, `__len__`, plus the `torch_vocab.vocab(OrderedDict)` factory.
All pure-Python implementable in ~120 lines.

Why this and not the alternatives:

- Removing torchtext also removes the reason for the `torch==2.3.0` pin. That
  pin exists *solely* to stop torchtext's compiled extension from dlopen-crashing
  (`bio_fm_worker/README.md`). Without it, the worker can move to Python 3.10 and
  a cp310 CUDA wheel — **GPU scGPT on the appliance**, and one less archived
  dependency in the amd64 build too.
- **Track B (CPU-only Python 3.9 on arm64) is rejected.** It keeps the 3.9 floor,
  which additionally requires building `scikit-misc` from sdist (meson +
  gfortran; no cp39 wheels exist in 0.5.x), and it buys a CPU-only torch running
  transformer inference on six Cortex-A78AE cores. Worst of both: highest build
  complexity *and* worst runtime.
- **Track C (drop scGPT on edge) is the pre-declared fallback**, not Track B.
  Phase 4 mandates a `decoupler` statistical baseline alongside *every* FM
  annotation, so annotation still works without scGPT — it loses FM
  corroboration, which is honest degradation rather than a broken feature.

**Spike discipline — write this into the plan, not into a retrospective:**

- Timebox: one plan. If it overruns, take Track C and move on.
- Pass condition, declared before running: (a) token→index mapping identical to
  the shipped `vocab.json` across the full vocabulary, and (b) per-cell
  embeddings matching the amd64 build within a stated tolerance on a fixed input
  set. A silently reordered vocab produces plausible, wrong annotations — the
  worst failure mode available here, because nothing downstream would flag it.
- **If it passes, upstream it to the amd64 build in the same phase.** Two
  divergent vocab implementations across architectures is a correctness trap;
  one implementation, both arches, or don't ship it.

### 3. True appliance — DECIDED

This is the decision that most expands scope, and the reason for splitting
Phase 16 out. See "The appliance threshold" below.

---

## Why the port is not "change one line and rebuild"

Phase 14's Dockerfile pins **every stage** to `--platform=linux/amd64`
(`Dockerfile:3-14`), and that pin is load-bearing, not stylistic.

### Emulation is not a fallback on Jetson

Running the amd64 image under QEMU gives no GPU — the NVIDIA container runtime
cannot pass the iGPU into an emulated x86_64 container — and the emulation cost
lands on exactly the compute-bound work the box exists to do. **Native arm64 or
nothing.**

Pleasant inversion: the dev machine is Apple Silicon. Today it emulates to build
amd64. For an arm64 image it is the *native* builder and the Jetson is the slow
one. Build off-device, ship the image.

### The wheel availability that forced Decision 2

Verified against the PyPI JSON API on 2026-09-18:

| Package | Needed by | linux aarch64 wheel | sdist | Verdict |
|---|---|---|---|---|
| `torchtext==0.18.0` | scGPT (`gene_tokenizer.py`) | **NONE** (macOS arm64 only) | **NONE** | Dead end — archived upstream since 2023, will never appear |
| `scikit-misc` | `scanpy[skmisc]` in worker | **NONE** | yes | Buildable from sdist; no cp39 wheels at all in 0.5.x |
| `torch==2.3.0` | scGPT, pinned for torchtext ABI | yes (cp39 `manylinux2014_aarch64`) | — | Installs, but **CPU-only** |

NVIDIA's CUDA-enabled Jetson torch wheels are **cp310 (JP6) / cp312 (JP7)** —
never cp39. The Python 3.9 floor and GPU acceleration are mutually exclusive on
this hardware. That is the entire case for Decision 2.

### Geneformer is the low-friction path — sequence it first

JetPack 6.2's system Python 3.10 matches `geneformer_worker/.venv` exactly,
NVIDIA ships cp310 CUDA wheels, and the CUDA-fallback patch already landed in
14-01 (`docker/geneformer_cuda_fallback.patch`) so both device paths are covered.
V1-10M is a 10M-parameter model in a 186MB checkout — the one component that
plausibly runs *well* here. It delivers a working GPU path before the scGPT
spike resolves.

### The GPU compose overlay does not work on Jetson

`docker-compose.gpu.yml` uses `deploy.resources.reservations.devices` with
`driver: nvidia`. JetPack exposes the iGPU through `runtime: nvidia` (the older
nvidia-docker path), not the discrete-GPU device-reservation API. Needs a Jetson
overlay variant, and the base must become an L4T/CUDA image
(`nvcr.io/nvidia/l4t-base` or a `dustynv/l4t-*` derivative) —
`python:3.13-slim` carries no CUDA at all.

### 8GB unified memory is the real ceiling, not the GPU

The 8GB is shared CPU/GPU. After the host OS, call it ~6.5GB for everything.
Nothing today prevents the main process, a scGPT subprocess, and a Geneformer
subprocess being live at once — wasteful on a workstation, an OOM kill here.

- `geneformer_worker/run_geneformer_perturb.py:149` hardcodes
  `forward_batch_size=100` over 2048-token inputs. Needs an env-var knob with a
  measured Jetson default.
- The FM subprocess shims need a mutex. `annotation/fm_client.py` and
  `perturbation/geneformer_client.py` both shell out today with no coordination
  whatsoever.
- **The FM client timeouts are wrong for this hardware and will fail expensively.**
  `call_geneformer_perturb()` defaults to 7200s and `call_scgpt_annotate()` to
  3600s — both sized for a workstation. On a slower device with a reduced batch
  size, a run that would have succeeded gets killed at the 2h mark *after
  burning two hours*. Measure real device wall-clock first, then set these, and
  surface progress before the timeout rather than after.
- `build_reference_index()` (census slice) must **not** run on device — bake it
  off-device. It is 29MB of `reference.h5ad` plus 5.9MB of embeddings: cheap to
  ship, expensive to compute.
- zram/swap sizing needs a recommendation, with the caveat that swapping a GPU
  workload is a performance cliff, not a safety net.

### Disk

The partially-built amd64 image is already **8.3GB** (`bioclaw:latest`), before
14-03 bakes in the 1.2GB scGPT venv, 1.7GB Geneformer venv, 197MB scGPT
checkpoint, and 186MB Geneformer checkout. Expect **12-16GB**. The dev kit boots
from microSD by default; NVMe is a prerequisite, not an optimization, and
docker's data-root must be relocated onto it.

---

## The appliance threshold

Everything above is a port. This section is a different kind of work, which is
why it gets its own phase.

**Phases 7-10 explicitly scoped the webapp to localhost, no deployment.** An
appliance on a lab LAN is the first time BioClaw is reachable from another
machine. The auth surface is young — the blank-`BIOCLAW_WEB_PASSWORD` bypass
found in 14-04 and fixed on 2026-09-18 was a shared-password cookie check that
authenticated an empty credential. That was acceptable risk at localhost scope.
It is not, unexamined, at LAN scope.

### Provisioning is a chicken-and-egg problem

`docker-compose.yml` uses `${ANTHROPIC_API_KEY:?...}` and
`${BIOCLAW_WEB_PASSWORD:?...}`, so **Compose refuses to start when either is
unset or empty** — deliberately, as the fix for that same auth bypass. On a
headless appliance that means a box that boots into a permanently failed state
with no way to tell you why.

Two options, and the appliance goal forces the second:
- **(a) Provision at flash time** — write `.env` during imaging. Simple, but
  every unit needs individual prep and the API key is baked in before the
  researcher ever sees it.
- **(b) First-run setup mode (recommended)** — appliance boots into a minimal
  setup service that collects the API key and a chosen password over the
  network, writes `.env` with restrictive permissions, then starts the main
  stack. New code, but it is the difference between an appliance and a
  pre-configured server.

Either way the health endpoint must distinguish *unprovisioned* from *broken* —
`/api/health` exists unauthenticated since 14-01 and is the natural surface.

### Network exposure and credentials

- A shared password over plain HTTP on a LAN is cleartext credentials on the
  wire. Options: reverse proxy with an internal CA (Caddy `tls internal`), a
  self-signed cert with a documented fingerprint, or an explicit
  trusted-LAN-only statement. **Recommend TLS via a local proxy** — the browser
  warning is a one-time documented step, and this is a research appliance
  handling unpublished data.
- Docs must say plainly: **do not port-forward this to the internet.** Single
  shared password, no rate limiting, no account model.
- `ANTHROPIC_API_KEY` sits in `.env` on a physically portable box. A stolen
  appliance is a stolen key. Recommend a dedicated key per appliance with its own
  spend limit, and restrictive file permissions on `.env`.
- Login rate-limiting is currently absent and matters once the box is reachable.

### Discovery

Headless means the researcher needs to find it. mDNS via avahi (`bioclaw.local`)
with a documented static-IP fallback for networks that block mDNS. This is also
what makes the TLS cert's hostname stable.

### Boot, recovery, power loss

- `restart: unless-stopped` is already in `docker-compose.yml`; combined with an
  enabled docker service that covers reboot, *provided* a first `compose up` has
  run. A systemd unit is the deterministic version. **Inspect and merge existing
  units — never replace wholesale.**
- No UPS. SQLite WAL survives power loss reasonably; the `.h5ad` dataset store is
  not transactional and a yanked cord mid-ingest can leave a partial dataset.
  Needs a documented recovery path and ideally an integrity check on boot.
- Thermals and power mode: the Super dev kit's `nvpmodel` modes (7W/15W/MAXN)
  trade clocks against heat. Recommend MAXN for FM throughput and document
  sustained-load thermal behaviour rather than assuming the stock fan copes.

### Updates

The image is 12-16GB, so initial install and updates want different mechanisms:
`docker save`/`load` for the first install (no registry infrastructure needed),
registry pull for updates (layer reuse makes incremental updates tractable).
Both paths need documenting, plus a rollback story — a bricked appliance with no
monitor is a support call.

### Headless observability

No monitor means the box must be able to explain itself over the network.
Extend `/api/health` with device state — GPU availability, power mode,
thermals, free memory, provisioning status. Small code, and it is the only
diagnostic channel a researcher has.

---

## Proposed phase shape (not yet plans)

Split into two phases because "runs on arm64 with GPU" and "behaves like an
appliance" are separable goals with different risk, and the first must be true
before the second means anything. Phase 15 is verifiable with a keyboard and
monitor attached; Phase 16 is verifiable only with them unplugged.

### Phase 15: Jetson arm64 + GPU Port

- **15-01 (spike, blocking):** torchtext-free `GeneVocab`. Pass condition and
  timebox per Decision 2. Resolves Track A vs Track C with evidence. If it
  passes, upstream to amd64 in this plan, not a later one.
- **15-02:** De-pin `--platform`; prove the main venv resolves natively on arm64.
  **First task is verifying aarch64 wheel availability for `tiledbsoma`
  (via `cellxgene-census`) and `cell-eval` — currently unverified and a
  potential repeat of the torchtext problem.** Backend + frontend serve on
  device; `/api/health` returns 200 on the Orin.
- **15-03:** Geneformer arm64 + CUDA worker on an L4T r36 base; Jetson GPU
  compose overlay (`runtime: nvidia`); on-device gate asserting
  `torch.cuda.is_available()` *inside* the container plus a real ranked-gene
  result from the V1-10M checkpoint.
- **15-04:** scGPT per the 15-01 outcome.
- **15-05:** 8GB envelope — FM mutex, batch-size knobs with measured defaults,
  **re-derived client timeouts from measured device wall-clock**, pre-baked
  reference index, documented worst-case RSS, no OOM kill across the full
  researcher workflow.
- **15-06:** Off-device cross-build on Apple Silicon → `docker save` → load on
  Orin; on-device smoke test; `docker/README.md` Jetson section.

### Phase 16: Appliance Hardening

- **16-01:** Storage provisioning — NVMe, relocated docker data-root, state
  volume placement, boot-time integrity check for the dataset store.
- **16-02:** First-run setup mode — provisioning service, `.env` writing with
  restrictive permissions, `/api/health` reporting unprovisioned vs broken.
- **16-03:** Network identity and TLS — avahi/mDNS `bioclaw.local`, static-IP
  fallback, local-CA TLS termination, login rate limiting, documented
  do-not-expose-to-WAN boundary.
- **16-04:** Boot and recovery — systemd unit (merged, not replacing existing
  units), power-loss recovery path, `nvpmodel` power mode, sustained-load
  thermal verification.
- **16-05:** Update and rollback path — `save`/`load` install, registry-pull
  update, documented rollback.
- **16-06:** Headless acceptance — device-state fields on `/api/health`, then
  the real test: full researcher workflow from a cold power-on with no monitor,
  no keyboard, and no shell access to the box.

### Draft success criteria — Phase 15

1. `docker compose up` on a JetPack 6.2 Orin Nano 8GB, from a clean checkout,
   starts backend and frontend **natively on arm64** (no QEMU) serving
   `/api/health` 200, with `--workers 1` still non-overridable.
2. Geneformer perturbation runs on the Orin GPU — `torch.cuda.is_available()`
   true inside the container, CUDA actually used — returning non-empty
   `ranked_genes` with non-zero cosine shifts within a measured, documented
   wall-clock budget that the client timeouts respect.
3. Cell-type annotation on device is verified equivalent to the amd64 build
   (identical vocab mapping, embeddings within stated tolerance), or the phase
   documents that Track C shipped and annotation runs baseline-only — never a
   silent behavioural difference.
4. The complete researcher workflow (census fetch → analysis → FM inference →
   CSV export → script export) completes on device with no OOM kill, worst-case
   resident memory measured and recorded.
5. Total on-device disk footprint is documented and fits the storage
   configuration, with the image built off-device.

### Draft success criteria — Phase 16

1. From cold power-on with no monitor, keyboard, or shell access, an
   unprovisioned appliance reaches a reachable setup surface, accepts an API key
   and password, and transitions to a working stack.
2. A researcher on the same LAN reaches the appliance by name over TLS, logs in,
   and completes the full workflow.
3. Pulling the power mid-session and restoring it returns the appliance to a
   working, consistent state with no manual intervention and no corrupted
   dataset store.
4. Sustained FM inference holds the chosen power mode without thermal throttling
   that breaches the Phase 15 wall-clock budgets.
5. An image update and a rollback both complete over the network without a
   monitor.
6. `/api/health` alone is sufficient to distinguish unprovisioned, starting,
   healthy, and degraded states.

---

## Evidence trail

- `Dockerfile:3-14` — the amd64 pin and its stated rationale.
- `Dockerfile:161-171` — runtime-stage import assertions that must survive the
  arch change (they exist because a green builder stage once shipped a broken
  image).
- `bio_fm_worker/README.md` — why torch 2.3.0 / torchtext 0.18.0 are paired.
- `scgpt/tokenizer/gene_tokenizer.py:11-12,20` — the entire torchtext surface.
- `geneformer_worker/run_geneformer_perturb.py:149` — `forward_batch_size=100`.
- `perturbation/geneformer_client.py` timeout=7200 / `annotation/fm_client.py`
  timeout=3600 — workstation-sized, unvalidated on this hardware.
- `docker/geneformer_cuda_fallback.patch` — the CPU fallback already committed.
- `docker-compose.yml` — the `:?` guards that make provisioning a hard gate.
- `.planning/phases/14-docker-compose-deployment/deferred-items.md` — the auth
  bypass that motivates the LAN-exposure hardening.
- PyPI JSON API, queried 2026-09-18 — wheel availability table above.
- `docker images` — `bioclaw:latest` at 8.3GB pre-14-03.
