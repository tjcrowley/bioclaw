# Deferred Items — Phase 14

Out-of-scope discoveries logged per execution scope-boundary rule (not fixed,
not caused by the plans that found them).

## 14-04: Empty-string BIOCLAW_WEB_PASSWORD authenticates (auth bypass)

**Found during:** Task 1, while reasoning about what Compose's `${VAR}`
interpolation does with an unset variable.

**Symptom:** `webapp/backend/auth.py::_valid()` guards only the `None` case:

```python
expected = os.environ.get("BIOCLAW_WEB_PASSWORD")
if expected is None or password is None:
    return False
return secrets.compare_digest(password, expected)
```

If `BIOCLAW_WEB_PASSWORD` is set to an empty string, `expected == ""` (not
None), and `secrets.compare_digest("", "")` returns True. A request carrying an
explicitly empty password — `GET /api/...?password=` — authenticates. Confirmed
live.

This is reachable outside Docker too: `BIOCLAW_WEB_PASSWORD="" uv run uvicorn ...`
starts an instance that anyone can log into.

**Mitigated at the Compose layer only:** `docker-compose.yml` uses
`${BIOCLAW_WEB_PASSWORD:?...}`, so Compose refuses to start when the var is
unset or empty. That closes the Docker path — which mattered, because
`.env.example` ships the value blank and the documented flow is "copy and fill
in". It does not fix the underlying function.

**Action:** RESOLVED 2026-09-18, immediately after 14-04, at Darren's direction.
Guard changed to `if not expected or not password:` in `webapp/backend/auth.py`,
with `tests/test_auth_blank_password.py` (15 tests) covering both
`require_password` and `require_password_ws` across every empty-credential
combination, plus a normal-path regression check.

**Correction to the writeup above.** The vector originally named — an empty
`?password=` query param, as stated in 14-04-SUMMARY.md and commit 9920b5a — is
NOT reachable. `candidate = candidate or password or session` returns its LAST
operand when all are falsy, so an empty `?password=` collapses to `None` and was
already rejected. The genuinely reachable vector is an empty **`session` cookie**
(`Cookie: session=`), which survives as `""` (the chain's last operand) and
reached `_valid`. The WebSocket path, `_valid(password or session)`, was
exploitable the same way. Both were confirmed live before the fix and are now
covered by parametrized tests. Severity and remedy unchanged; only the vector
name was wrong. The error came from testing `_valid()` in isolation rather than
through its callers — isolation proved the flaw existed, not that it was
reachable.

## 14-03: Geneformer stage installs torch unconstrained, pulling ~3GB of CUDA 13

**Found during:** Task 2, watching the first full `docker build` of the
geneformer-builder stage.

**Symptom:** `Dockerfile:125` installs the vendored Geneformer checkout with no
torch constraint:

```dockerfile
RUN --mount=type=cache,target=/root/.cache/pip \
    /opt/geneformer_worker_venv/bin/pip install -e /opt/geneformer_src \
 && /opt/geneformer_worker_venv/bin/pip install "transformers==4.46"
```

Geneformer declares a bare `torch` dependency, so pip resolves the newest
release — **torch 2.14.0** — and with it the entire CUDA 13 runtime as separate
wheels. Measured from the build log:

| Component | Size |
|---|---|
| `nvidia_cudnn_cu13` | 553.1 MB |
| `nvidia_cublas` | 423.1 MB |
| `torch` 2.14.0 | 554.6 MB |
| `triton` | 247.8 MB |
| `nvidia_nccl_cu13` | 216.0 MB |
| `nvidia_cufft` | 214.1 MB |
| `nvidia_cusolver` | 200.9 MB |
| `nvidia_cusparselt_cu13` | 170.1 MB |
| `nvidia_cusparse` | 145.9 MB |
| `nvidia_cuda_nvrtc` | 90.2 MB |
| 6 smaller `nvidia_*` + `cuda_bindings` | ~181 MB |
| `bitsandbytes` | 43.1 MB |
| **Total** | **~3.04 GB of wheels** |

Unpacked into the venv this is substantially larger again, and the runtime stage
then `COPY --from=geneformer-builder`s all of it into the final image.

**Why this is waste, not caution.** Nothing in the deployed configuration uses
it. `docker-compose.yml` reserves no GPU; only the optional
`docker-compose.gpu.yml` overlay does. The x86_64 CUDA 13 wheels are useless
on the default CPU path, and Plan 14-01 already had to patch ~15 hardcoded
`device="cuda"` call sites specifically so Geneformer runs on CPU
(`docker/geneformer_cuda_fallback.patch`). We are shipping a 3GB GPU stack into
an image whose Geneformer worker we deliberately taught to avoid the GPU.

**Contrast with the scGPT stage,** which already solves exactly this problem for
exactly this reason — `Dockerfile:24-40` pre-installs `torch==2.3.0` so the
resolver never fetches the newer build, and the comment there explains the
double-download cost in detail. The geneformer stage simply never got the same
treatment.

**Not fixed here.** Out of 14-03's scope: the plan's Task 2 interface says to
install from the README's documented commands, and the README's command is the
unconstrained one. Changing the resolved torch version is a behaviour change to
the Geneformer worker that deserves its own verification (the CPU-fallback patch
was authored against whatever torch resolved at the time, and
`transformers==4.46` is pinned against it downstream).

**Suggested fix when picked up:** mirror the scGPT stage — pre-install a
CPU-only torch from the PyTorch CPU index before `pip install -e`, e.g.
`pip install torch --index-url https://download.pytorch.org/whl/cpu`, then
re-assert it after, and let `docker-compose.gpu.yml` users opt into a CUDA build
separately. Verify `geneformer_worker/`'s real-run path still passes afterward.

**Direct input to Phase 15 (Jetson).** This is not merely a size problem there,
it is a correctness one. The Jetson Orin Nano needs NVIDIA's L4T-specific
aarch64 cp310 wheels built against JetPack 6.2's CUDA 12.6; the generic
`nvidia_*_cu13` x86_64 wheels resolved here do not exist for that platform and
would not work if they did. Phase 15 must constrain this install explicitly
rather than inherit whatever PyPI resolves — see
`.planning/research/JETSON-ORIN-NANO.md`.

## 14-05: Exported scanpy script emits an unrunnable source path (EXPORT-02 defect)

**Found during:** Phase 14 close-out (2026-10-13), exercising the two export
endpoints against the long-running container to close the part of Task 3's
human checkpoint that was never completed.

**Symptom:** `GET /api/export/script?dataset_id=demo_query_blood@4` returns
HTTP 200 and a well-formed 1,550-byte script whose load line is:

```python
adata = sc.read_h5ad("")
```

The script is therefore not runnable, which directly contradicts EXPORT-02's
"self-contained, reproducible" promise. Everything else in the script is
correct — QC thresholds, HVG count, PCA/neighbors/leiden/umap params, seeds.

**Root cause** — `webapp/backend/export_script.py:91-92`:

```python
safe_path = source_path or ""
lines.append(f'adata = sc.read_h5ad("{safe_path}")')
```

`None` is silently degraded to an empty string rather than raising or emitting
a placeholder the user would notice.

**Why `source_path` is None** — confirmed in the live registry
(`/app/state/data/registry.sqlite`, table `datasets`):

| name | version | source_path |
|---|---|---|
| demo_query_blood | 1 | `/tmp/tmpnn9pzv6j/demo_query_blood.h5ad` |
| demo_query_blood | 2 | `None` |
| demo_query_blood | 3 | `None` |
| demo_query_blood | 4 | `None` |

Two distinct failures, so **every version of an uploaded dataset is broken**:

1. **Derived versions (v2+)** record no `source_path` at all → empty string.
2. **v1** records the *temp upload path*, which is deleted as soon as the
   request completes → a script that points at a path guaranteed not to exist.

Census-sourced datasets are unaffected: `is_census` takes the other branch and
emits a real `cellxgene_census` fetch block, which is genuinely reproducible.
This is why no test caught it — the census path is the one with provenance.

**Not fixed here.** Out of scope for a phase close-out, and the right fix is a
design decision rather than a one-liner. Options, roughly in increasing order
of correctness:

- Emit a clearly-marked placeholder (`sc.read_h5ad("<path-to-your-h5ad>")`)
  plus a comment, so the gap is visible instead of silent. Smallest change.
- Resolve derived versions back to their root version's provenance, and for
  uploads record the *stored* dataset path (`/app/state/data/<name>/vN.h5ad`)
  rather than the temp upload path. Makes the script runnable in-place.
- Have the export ship the `.h5ad` alongside the script (the CSV export is
  already a ZIP, so the pattern exists).

Whichever is chosen, add a regression test for the uploaded-dataset path — the
existing EXPORT-02 tests only cover census provenance.

## 14-05: docker/README.md predates the non-root fixes

**Found during:** Phase 14 close-out (2026-10-13).

`docker/README.md` was committed 2026-09-18 (`63d0bf7`), one day *before* the
first real end-to-end run exposed three startup defects (`a78bd1d` non-root
user, `461d1c5` .env baked into the image, `6ec5ff6` /app unreadable). Its
"Known gaps" section therefore does not mention runtime file ownership at all,
even though that is the single thing most likely to break a rebuild.

**Action:** add a short "runtime ownership" note — the container runs as
`bioclaw`, `/app` must be world-readable, and the relocated interpreters under
`/opt/py39`/`/opt/py310` are root-owned by design.
