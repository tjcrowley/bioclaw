"""Subprocess shim to the isolated scGPT bio_fm_worker/ environment (ANNOT-01).

`call_scgpt_annotate()` never imports `scgpt`/`torch` directly -- it shells
out to `bio_fm_worker/run_scgpt_embed.py`, which runs inside the isolated
`bio_fm_worker/.venv` (see 04-RESEARCH.md's Isolation Boundary). This keeps
scGPT's heavy/old dependency pins (`scvi-tools<1.0`, unpinned `torchtext`,
`orbax<0.1.8`) completely out of the main project venv and root
pyproject.toml.

The subprocess contract: `run_scgpt_embed.py` prints a JSON array of
per-cluster annotation objects to stdout on success (exit 0), matching
`AnnotationCall`'s field names exactly, or prints a one-line error message
to stderr and exits non-zero on failure. A stuck/slow real inference call
surfaces as a `RuntimeError` naming the timeout used, never an indefinite
hang.

Any `.h5ad` crossing into the worker must go through
`ensure_worker_compatible_h5ad()` first (see its docstring) -- the main
venv's pandas 3.0/anndata 0.13 and the worker's anndata==0.10.9 (pinned by
scGPT's Python 3.9 floor -- anndata>=0.11 requires Python>=3.10) disagree
on-disk, not just in API surface.
"""

import json
import subprocess

import pandas as pd

from annotation.summary import AnnotationCall


def ensure_worker_compatible_h5ad(adata):
    """Coerce pandas-3.0-default `StringDtype` index/columns to plain numpy
    `object` dtype, in place, before writing an `.h5ad` for
    `bio_fm_worker/`'s isolated environment to read.

    Discovered 2026-09-07: pandas 3.0 (this project's main venv) defaults
    string `Index`/columns to a PyArrow-backed `StringDtype`, which
    anndata>=0.11 serializes as `IOSpec("nullable-string-array")` -- a
    format anndata==0.10.9 (the newest version installable under the
    worker's Python 3.9 floor) has no reader for at all. This is a wire
    format gap, not a version-skew warning, so it must be fixed at write
    time rather than worked around in the reader.

    Also clears `adata.uns`: the worker never reads it, and the analysis
    pipeline may write values (e.g. DE group results with `null`-encoded NaN
    cells) that anndata==0.10.9 cannot decode.

    Also coerces Categorical columns whose *category* dtype is StringDtype
    (pandas 3.0 defaults new Categoricals to string-backed categories), which
    anndata>=0.11 serializes using the same unreadable encoding.
    """
    adata.uns.clear()
    adata.obs_names = adata.obs_names.astype(object)
    adata.var_names = adata.var_names.astype(object)
    for df in (adata.obs, adata.var):
        for col in df.columns:
            if isinstance(df[col].dtype, pd.StringDtype):
                df[col] = df[col].astype(object)
            elif hasattr(df[col], "cat") and isinstance(
                df[col].cat.categories.dtype, pd.StringDtype
            ):
                df[col] = df[col].cat.rename_categories(
                    df[col].cat.categories.astype(object)
                )


def call_scgpt_annotate(
    query_h5ad_path,
    reference_index_path,
    worker_python="bio_fm_worker/.venv/bin/python",
    script_path="bio_fm_worker/run_scgpt_embed.py",
    model_dir="bio_fm_worker/checkpoints/scGPT_human",
    timeout: float = 3600.0,
) -> list[AnnotationCall]:
    """Reference-map `query_h5ad_path`'s clusters against `reference_index_path`
    via scGPT, run inside the isolated `bio_fm_worker/.venv` environment.

    Returns one `AnnotationCall` per query cluster. Raises `RuntimeError`
    (never lets a subprocess failure or timeout propagate as an uncaught
    exception) if the subprocess exits non-zero or exceeds `timeout`
    seconds.

    `timeout` defaults to a full hour, not something tighter: embedding the
    reference set is a real, CPU-bound scGPT forward pass that took ~38
    minutes end-to-end in verification (2026-09-07, 3000 cells, no GPU). Only
    the first call actually pays that cost -- `run_scgpt_embed.py` caches the
    reference embedding to disk next to the reference file, so every
    subsequent call (same reference + model_dir) only re-embeds the query,
    which finishes in seconds. Lowering this default would make that
    unavoidable first call fail with a spurious timeout.
    """
    try:
        result = subprocess.run(
            [
                str(worker_python),
                str(script_path),
                "--query",
                str(query_h5ad_path),
                "--reference",
                str(reference_index_path),
                "--model-dir",
                str(model_dir),
            ],
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError(
            f"scGPT annotation subprocess exceeded timeout={timeout}s"
        ) from exc

    if result.returncode != 0:
        raise RuntimeError(
            f"scGPT annotation subprocess failed (exit {result.returncode}): "
            f"{result.stderr}"
        )
    # scGPT and PyTorch write log lines to stdout (not stderr) before the JSON
    # output: "WARNING: CUDA is not available." and "scGPT - INFO - match N/M
    # genes...". Extract the last line that looks like a JSON array.
    json_line = next(
        (ln for ln in reversed(result.stdout.splitlines()) if ln.strip().startswith("[")),
        None,
    )
    if not json_line:
        raise RuntimeError(
            f"scGPT subprocess produced no JSON output.\n"
            f"stdout: {result.stdout[:500]!r}\n"
            f"stderr: {result.stderr[:500]!r}"
        )
    return [AnnotationCall(**obj) for obj in json.loads(json_line)]
