# bio_fm_worker/ — isolated scGPT environment

A separate Python environment, deliberately outside the root project's
`.venv` and `pyproject.toml`. `scgpt` pins old/heavy transitive
dependencies (`scvi-tools<1.0`, unpinned `torchtext`, `orbax<0.1.8`,
`cell-gears<0.0.3`) that must never touch the already-tested Phase 1-3
stack. `annotation/fm_client.py` in the main venv talks to this
environment only via `subprocess`, never via a direct import.

## How it was created

```bash
python3 -m venv bio_fm_worker/.venv
bio_fm_worker/.venv/bin/pip install --upgrade pip
bio_fm_worker/.venv/bin/pip install scgpt
```

Python version: the system default `python3` resolved to **3.9.6**
(Xcode Command Line Tools' `/usr/bin/python3`), not the 3.12+ the root
project requires. This is fine and expected — this venv is fully
isolated, so its interpreter version has no bearing on the root
project's `>=3.12` floor. `scvi-tools<1.0`, one of `scgpt`'s pins,
would likely not have resolved on 3.12+ anyway.

## Install outcome: `pip install` succeeded, `import scgpt` fails

`pip install scgpt` completed successfully — `scgpt==0.2.4` and all
its transitive dependencies (`torch`, `torchtext`, `scvi-tools`,
`cell-gears==0.0.2`, etc.) are present in `bio_fm_worker/.venv`.

However, `bio_fm_worker/.venv/bin/python -c "import scgpt"` fails at
import time, inside `torchtext`, not `scgpt` itself:

```
File ".../torchtext/_extension.py", line 58, in _init_extension
    _load_lib("libtorchtext")
...
OSError: dlopen(.../torchtext/lib/libtorchtext.so, 0x0006): Symbol not found:
__ZN3c105ErrorC1ENSt3__112basic_stringIcNS1_11char_traitsIcEENS1_9allocatorIcEEEES7_PKv
Referenced from: .../torchtext/lib/libtorchtext.so
Expected in:     .../torch/lib/libc10.dylib
```

This is a binary ABI mismatch between the `torchtext` and `torch`
wheels that `pip`'s resolver picked for this platform (macOS
arm64) — `torchtext`'s compiled C++ extension (`libtorchtext.so`)
was built against a `torch` C++ ABI that doesn't match the `torch`
version actually installed alongside it. `torchtext` itself has been
unmaintained/archived upstream since 2023, which is consistent with
this kind of staleness. It is not a code bug in this repo.

Per 04-03-PLAN.md's documented contingency, this is a **real,
documented gap for Plan 04-05 to resolve**, not a blocker for Wave 1:
this plan's fast-tier tests (`tests/test_annotation_fm_client.py`)
mock the subprocess boundary entirely and never import `scgpt` or
touch this environment.

## How to reproduce / repair

Reproduce the failure:
```bash
bio_fm_worker/.venv/bin/python -c "import scgpt"
```

Repair candidates for Plan 04-05 (untried, in likely-cheapest-first order):
1. Pin a matching `torch`/`torchtext` release pair explicitly (e.g.
   `pip install torch==2.1.* torchtext==0.16.*` — matched minor
   versions are far less likely to hit an ABI skew) before installing
   `scgpt`, then re-run `pip install scgpt --no-deps` so it doesn't
   re-resolve and clobber the pin.
2. If scGPT's own embedding path (`scgpt.tasks.embed_data`, per
   04-RESEARCH.md Pattern 1) doesn't actually need `torchtext`
   (`torchtext` is used for its `vocab` module inside
   `scgpt/tokenizer/gene_tokenizer.py`), a stub/dummy `torchtext`
   package installed ahead of `scgpt` may satisfy the import without
   ever executing the broken extension-loading path.
3. Rebuild the venv with an older, mutually-compatible `torch==1.13.*`
   / `torchtext==0.14.*` pair, matching versions `scgpt`'s own
   `setup.py`-era pins likely targeted originally.

## What `run_scgpt_embed.py` implements

`run_scgpt_embed.py` is written against 04-RESEARCH.md Pattern 1's
documented (LOW-MEDIUM confidence) `scgpt.tasks.embed_data(...)` API
shape, since the import failure above blocks the plan's intended
`help(scg.tasks)` introspection step. **This has not been run against
real `scgpt` code and its exact call signature is unverified** — Plan
04-05, once a working `scgpt` import is available (see repair
candidates above) and a real checkpoint is acquired, must re-verify
this script's embedding calls against the actual installed API before
relying on its output.
