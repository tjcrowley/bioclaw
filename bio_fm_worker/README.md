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

## Install outcome: FIXED (2026-09-07) — `import scgpt` now works

`pip install scgpt` originally resolved `torch==2.8.0` alongside
`torchtext==0.18.0`. `torchtext` 0.18 was released paired against
`torch` 2.3 (`torchtext` has been unmaintained/archived upstream
since 2023, so it never got a wheel rebuilt for newer `torch` C++
ABIs) — the version skew caused a `dlopen` symbol-not-found crash
inside `torchtext`'s compiled extension at import time, not a bug in
this repo.

**Repair candidate 1 from the original writeup worked directly:**

```bash
bio_fm_worker/.venv/bin/pip install "torch==2.3.0"
```

This downgrades only `torch` (uninstalling 2.8.0), leaving
`torchtext==0.18.0` in place — now a matched pair. Verified:

```bash
bio_fm_worker/.venv/bin/python -c "import scgpt; print('scgpt OK')"
# -> scgpt OK (only benign flash_attn-not-installed / torchtext-deprecation warnings)
```

If this venv is ever rebuilt from scratch, run the pin step
immediately after `pip install scgpt` and before anything else
imports `scgpt`/`torch`, since re-resolving deps later can silently
re-upgrade `torch` again.

## What `run_scgpt_embed.py` implements

`run_scgpt_embed.py` is written against 04-RESEARCH.md Pattern 1's
documented (LOW-MEDIUM confidence) `scgpt.tasks.embed_data(...)` API
shape. Now that `import scgpt` succeeds, this must still be verified
against the real installed API (`help(scgpt.tasks)`) before the
`bio_fm_smoke` integration test can be trusted — not yet done as of
this fix landing.
