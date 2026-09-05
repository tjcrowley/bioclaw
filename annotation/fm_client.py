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
"""

import json
import subprocess

from annotation.summary import AnnotationCall


def call_scgpt_annotate(
    query_h5ad_path,
    reference_index_path,
    worker_python="bio_fm_worker/.venv/bin/python",
    script_path="bio_fm_worker/run_scgpt_embed.py",
    model_dir="bio_fm_worker/checkpoints/scGPT_human",
    timeout: float = 600.0,
) -> list[AnnotationCall]:
    """Reference-map `query_h5ad_path`'s clusters against `reference_index_path`
    via scGPT, run inside the isolated `bio_fm_worker/.venv` environment.

    Returns one `AnnotationCall` per query cluster. Raises `RuntimeError`
    (never lets a subprocess failure or timeout propagate as an uncaught
    exception) if the subprocess exits non-zero or exceeds `timeout`
    seconds.
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
    return [AnnotationCall(**obj) for obj in json.loads(result.stdout)]
