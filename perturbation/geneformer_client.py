"""Subprocess shim to the isolated Geneformer geneformer_worker/ environment (FM-02).

`call_geneformer_perturb()` never imports `geneformer`/`torch` directly -- it
shells out to `geneformer_worker/run_geneformer_perturb.py`, which runs
inside the isolated `geneformer_worker/.venv` (see geneformer_worker/README.md
and 13-RESEARCH.md's Isolation Boundary). This mirrors
`annotation/fm_client.py::call_scgpt_annotate()`'s exact subprocess/JSON-over-
stdout dispatch contract for scGPT -- reused rather than reinvented, per
13-RESEARCH.md Pattern 3.

The subprocess contract: `run_geneformer_perturb.py` prints a single JSON
*object* (not an array -- one target gene per call, unlike scGPT's
per-cluster array) to stdout on success (exit 0), matching
`GeneformerPerturbationCall`'s field names exactly, or prints a one-line
error message to stderr and exits non-zero on failure. A stuck/slow real
inference call surfaces as a `RuntimeError` naming the timeout used, never
an indefinite hang.
"""

import json
import subprocess

from perturbation.summary import GeneformerPerturbationCall, GeneShift


def call_geneformer_perturb(
    query_h5ad_path,
    target_gene,
    target_ensembl_id,
    worker_python="geneformer_worker/.venv/bin/python",
    script_path="geneformer_worker/run_geneformer_perturb.py",
    model_dir="geneformer_worker/src/Geneformer-V1-10M",
    timeout: float = 7200.0,
) -> GeneformerPerturbationCall:
    """Run Geneformer's real four-step in-silico-perturbation pipeline against
    `query_h5ad_path`, deleting `target_ensembl_id` and ranking every other
    gene by the resulting cosine embedding shift, inside the isolated
    `geneformer_worker/.venv` environment.

    Returns one `GeneformerPerturbationCall`. Raises `RuntimeError` (never
    lets a subprocess failure or timeout propagate as an uncaught exception)
    if the subprocess exits non-zero or exceeds `timeout` seconds.

    `timeout` defaults to 7200s (2 hours), not scGPT's 3600s (1 hour): per
    13-RESEARCH.md Pitfall 3, Geneformer's four-step pipeline (tokenize +
    baseline embed + a full forward pass per perturbed gene + stats
    aggregation) has a longer wall-clock ceiling than scGPT's single
    embedding call, with real disk I/O between every stage.
    """
    try:
        result = subprocess.run(
            [
                str(worker_python),
                str(script_path),
                "--query",
                str(query_h5ad_path),
                "--target-gene",
                str(target_gene),
                "--target-ensembl-id",
                str(target_ensembl_id),
                "--model-dir",
                str(model_dir),
            ],
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError(
            f"Geneformer perturbation subprocess exceeded timeout={timeout}s"
        ) from exc

    if result.returncode != 0:
        raise RuntimeError(
            f"Geneformer perturbation subprocess failed (exit {result.returncode}): "
            f"{result.stderr}"
        )
    # Geneformer/torch write log lines to stdout before the JSON output, like
    # run_scgpt_embed.py -- extract the last line that looks like a JSON
    # object (not array: this client returns one object, not a list).
    json_line = next(
        (ln for ln in reversed(result.stdout.splitlines()) if ln.strip().startswith("{")),
        None,
    )
    if not json_line:
        raise RuntimeError(
            f"Geneformer subprocess produced no JSON output.\n"
            f"stdout: {result.stdout[:500]!r}\n"
            f"stderr: {result.stderr[:500]!r}"
        )
    obj = json.loads(json_line)
    return GeneformerPerturbationCall(
        method="geneformer",
        target_gene=obj["target_gene"],
        target_ensembl_id=obj["target_ensembl_id"],
        match_rate=obj["match_rate"],
        ranked_genes=[GeneShift(**g) for g in obj["ranked_genes"]],
    )
