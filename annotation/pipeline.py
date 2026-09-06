"""Composed cell-type annotation pipeline (ANNOT-01/03).

Wires annotation/baseline.py's decoupler ORA baseline (unconditional) and
annotation/fm_client.py's scGPT subprocess call (best-effort, never crashes
the pipeline) into one bounded `AnnotationSummary`. Mirrors
analysis/pipeline.py::analyze()'s load-from-store entrypoint shape.

Per ANNOT-02, the baseline call runs unconditionally regardless of whether
the FM call succeeds -- "every FM-backed annotation call is accompanied by"
the baseline is that requirement's literal wording. `annotate()` does not
persist a new store version: annotation adds no data worth persisting
beyond the returned summary, and it operates read-only on an
already-clustered dataset. The returned `dataset_id` is the SAME id it
loaded (mirroring `analyze()`'s `loaded_id` display convention), so
`agent/session.py`'s existing `record_dataset_reference()` hook still
records it into session memory with no new wiring needed.
"""

from __future__ import annotations

import tempfile
from dataclasses import asdict
from pathlib import Path

from ingest.store import DatasetStore

from annotation.baseline import baseline_annotate
from annotation.fm_client import call_scgpt_annotate
from annotation.summary import AnnotationSummary


def annotate(
    name: str,
    version: int | None = None,
    store_root: str | Path = "data",
    reference_index_path: str | Path = "bio_fm_worker/reference/reference.h5ad",
    worker_python: str | Path = "bio_fm_worker/.venv/bin/python",
    script_path: str | Path = "bio_fm_worker/run_scgpt_embed.py",
    model_dir: str | Path = "bio_fm_worker/checkpoints/scGPT_human",
) -> tuple[str, dict]:
    """Load `name`/`version` from the store, run both baseline and FM
    annotation, and return `(dataset_id, summary_dict)`.

    Raises `KeyError` if `name`/`version` is not found in the store
    (propagated from `DatasetStore.load`, not swallowed). Never raises on
    an FM (scGPT) call failure -- that path falls back to an empty
    `fm_calls` list with `baseline_calls` fully populated.
    """
    store = DatasetStore(root=store_root)
    adata = store.load(name, version)
    dataset_id = f"{name}@{version if version is not None else '(latest)'}"

    baseline_calls = baseline_annotate(adata, groupby="leiden")

    try:
        with tempfile.NamedTemporaryFile(suffix=".h5ad", delete=False) as tmp:
            adata.write_h5ad(tmp.name)
            fm_calls = call_scgpt_annotate(
                tmp.name,
                reference_index_path,
                worker_python=worker_python,
                script_path=script_path,
                model_dir=model_dir,
            )
    except Exception:
        fm_calls = []

    summary = AnnotationSummary(
        dataset_id=dataset_id,
        fm_calls=fm_calls,
        baseline_calls=baseline_calls,
        fm_model="scGPT (whole-human checkpoint, zero-shot reference mapping)",
        baseline_method="decoupler ORA vs PanglaoDB (human, canonical markers)",
    )
    return dataset_id, asdict(summary)
