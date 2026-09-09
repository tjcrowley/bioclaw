"""build_benchmark_report() / run_full_benchmark() -- Phase 5, Plan 05-05 (VCC-03).

This module provides two public functions:

1. ``build_benchmark_report(predictor_metrics, baseline_metrics, ...)``
   Formats a predictor + naive-baseline side-by-side benchmark report.  Raises
   ``ValueError`` if either metrics dict is falsy or missing any of the three
   required VCC metric keys (``mae``, ``pds``, ``des``), making it structurally
   impossible to produce a predictor-only or incomplete-baseline report.

2. ``run_full_benchmark(name, target_genes, ...)``
   Top-level single-call orchestration: calls ``benchmark.vcc_eval.run_vcc_eval()``
   then passes its output straight into ``build_benchmark_report()``.  Plan 05-06's
   real-data smoke test calls this function directly -- no additional wiring needed.

Report structure (plain dict)
------------------------------
The returned dict has the following guaranteed keys:

    {
        "dataset_id": str,              # e.g. "my-dataset@1" or "my-dataset@(latest)"
        "target_genes": list[str],      # as provided to build_benchmark_report / run_full_benchmark
        "predictor": {                  # validated predictor metrics (all three required)
            "mae": float,               # Mean Absolute Error (lower = better, 0.0 = perfect)
            "pds": float,               # Perturbation Discrimination Score (higher = better, 1.0 = perfect)
            "des": float,               # Differential Expression Score (higher = better)
        },
        "baseline": {                   # validated naive-baseline metrics (same shape)
            "mae": float,
            "pds": float,
            "des": float,
        },
        "qc_provenance_note": str,      # QC-state attribution note (see DEFAULT_QC_PROVENANCE_NOTE)
    }

Design choice: plain ``dict`` (not a dataclass).
Rationale: downstream plans (05-06 checkpoint, agent tool layer) only access
fields by key; a plain dict serializes trivially to JSON for display in the
checkpoint table and avoids the dependency on a separate class import at call
sites that only format or log the report.

Per 05-RESEARCH.md Anti-Patterns and Pitfall 5: ``qc_provenance_note`` is always
present, never optional, so "which QC state these scores reflect" is structurally
attached to every report produced by this module.

Downstream imports:
    from benchmark.report import build_benchmark_report, run_full_benchmark, to_markdown
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    pass


# ---------------------------------------------------------------------------
# Public constant: default QC provenance note (importable by tests)
# ---------------------------------------------------------------------------

DEFAULT_QC_PROVENANCE_NOTE: str = (
    "Metrics computed against this project's own QC'd/ingested dataset "
    "state, not Arc Institute's original unfiltered public release -- "
    "see 05-RESEARCH.md Pitfall 5."
)

# The three metric keys that compute_vcc_metrics() produces and that
# build_benchmark_report() requires in both predictor and baseline dicts.
_REQUIRED_METRIC_KEYS: frozenset[str] = frozenset({"mae", "pds", "des"})


# ---------------------------------------------------------------------------
# build_benchmark_report()
# ---------------------------------------------------------------------------

def build_benchmark_report(
    predictor_metrics: dict | None,
    baseline_metrics: dict | None,
    dataset_id: str,
    target_genes: list[str],
    qc_provenance_note: str = DEFAULT_QC_PROVENANCE_NOTE,
) -> dict:
    """Build a VCC-03 benchmark report from predictor and baseline metrics.

    Validates both metrics dicts before constructing the report -- raises
    ``ValueError`` with a descriptive message if either is falsy or is missing
    any of the three required keys (``mae``, ``pds``, ``des``).  This makes it
    structurally impossible to produce a predictor-only report or one where the
    baseline is silently omitted or incomplete.

    Per 05-RESEARCH.md Anti-Pattern (Pitfall 5): the ``qc_provenance_note``
    field is always included in the returned report so that every report
    produced by this module carries "which QC state these scores reflect."

    Args:
        predictor_metrics: Metrics dict from the LinearAdditivePerturbationModel
            predictor.  Must be a non-empty dict with keys ``mae``, ``pds``,
            ``des`` (the normalised output of ``compute_vcc_metrics()``).
        baseline_metrics: Metrics dict from the naive baseline predictor.  Must
            have the same structure as ``predictor_metrics``.
        dataset_id: Dataset identifier string (e.g. ``"my-dataset@1"``).
        target_genes: List of perturbation target gene names evaluated.
        qc_provenance_note: Human-readable note describing which QC state the
            metrics reflect.  Defaults to ``DEFAULT_QC_PROVENANCE_NOTE``.

    Returns:
        A plain dict with keys: ``dataset_id``, ``target_genes``, ``predictor``,
        ``baseline``, ``qc_provenance_note``.  See module docstring for the
        full shape.

    Raises:
        ValueError: if ``predictor_metrics`` is ``None``, empty, or missing any
            of the three required metric keys.
        ValueError: if ``baseline_metrics`` is ``None``, empty, or missing any
            of the three required metric keys.
    """
    _validate_metrics(predictor_metrics, "predictor_metrics")
    _validate_metrics(baseline_metrics, "baseline_metrics")

    return {
        "dataset_id": dataset_id,
        "target_genes": list(target_genes),
        "predictor": dict(predictor_metrics),
        "baseline": dict(baseline_metrics),
        "qc_provenance_note": qc_provenance_note,
    }


# ---------------------------------------------------------------------------
# run_full_benchmark()
# ---------------------------------------------------------------------------

def run_full_benchmark(
    name: str,
    target_genes: list[str],
    version: int | None = None,
    store_root: str = "data",
) -> dict:
    """Single top-level entrypoint: run VCC eval and build the benchmark report.

    Calls ``benchmark.vcc_eval.run_vcc_eval()`` to get predictor and baseline
    metrics, then passes them straight into ``build_benchmark_report()``.

    This is the function Plan 05-06's real-data smoke test calls against the
    downloaded VCC dataset -- no additional orchestration wiring is needed
    beyond ``store.save(name, adata)`` followed by this call.

    Args:
        name: Dataset name in the ``DatasetStore``.
        target_genes: List of perturbation target gene names to evaluate.
        version: Dataset version (int), or ``None`` for latest.
        store_root: Root directory of the ``DatasetStore``.

    Returns:
        A complete benchmark report dict (see ``build_benchmark_report()``
        and module docstring for the exact shape).
    """
    from benchmark.vcc_eval import run_vcc_eval

    eval_result = run_vcc_eval(
        name=name,
        target_genes=target_genes,
        version=version,
        store_root=store_root,
    )

    return build_benchmark_report(
        predictor_metrics=eval_result["predictor_metrics"],
        baseline_metrics=eval_result["baseline_metrics"],
        dataset_id=eval_result["dataset_id"],
        target_genes=eval_result["target_genes"],
    )


# ---------------------------------------------------------------------------
# to_markdown()
# ---------------------------------------------------------------------------

def to_markdown(report: dict) -> str:
    """Render a benchmark report as a human-readable Markdown string.

    Produces a small table with predictor vs. baseline scores for each metric
    (MAE, PDS, DES), followed by the QC provenance note.  This is what Plan
    05-06's checkpoint task will show to the user.

    Args:
        report: A benchmark report dict as returned by ``build_benchmark_report()``
            or ``run_full_benchmark()``.

    Returns:
        A Markdown-formatted string with a comparison table and provenance note.
    """
    pred = report["predictor"]
    base = report["baseline"]
    dataset_id = report.get("dataset_id", "unknown")
    target_genes = report.get("target_genes", [])
    note = report.get("qc_provenance_note", "")

    # Format metric rows: (metric, label, predictor_value, baseline_value)
    rows = [
        ("MAE", "Mean Absolute Error (lower = better)", pred["mae"], base["mae"]),
        ("PDS", "Perturbation Discrimination Score (higher = better)", pred["pds"], base["pds"]),
        ("DES", "Differential Expression Score (higher = better)", pred["des"], base["des"]),
    ]

    genes_str = ", ".join(target_genes) if target_genes else "(none)"

    lines = [
        f"## VCC Benchmark Report: {dataset_id}",
        f"",
        f"**Target genes evaluated:** {genes_str}",
        f"",
        f"| Metric | Description | Predictor | Naive Baseline |",
        f"| ------ | ----------- | --------- | -------------- |",
    ]
    for metric, desc, pval, bval in rows:
        lines.append(f"| {metric} | {desc} | {pval:.4f} | {bval:.4f} |")

    lines += [
        f"",
        f"> **QC Provenance:** {note}",
    ]

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Internal helper
# ---------------------------------------------------------------------------

def _validate_metrics(metrics: dict | None, name: str) -> None:
    """Validate a metrics dict -- raises ValueError with a descriptive message.

    Args:
        metrics: The metrics dict to validate.
        name: Human-readable name (``"predictor_metrics"`` or
            ``"baseline_metrics"``) for the error message.

    Raises:
        ValueError: if ``metrics`` is ``None``, empty, or missing any of the
            three required keys (``mae``, ``pds``, ``des``).
    """
    if not metrics:
        raise ValueError(
            f"build_benchmark_report: {name} must be a non-empty dict with keys "
            f"{sorted(_REQUIRED_METRIC_KEYS)!r} -- got {metrics!r}. "
            f"A report cannot be produced without both predictor and baseline metrics."
        )

    missing = _REQUIRED_METRIC_KEYS - set(metrics.keys())
    if missing:
        raise ValueError(
            f"build_benchmark_report: {name} is missing required metric key(s) "
            f"{sorted(missing)!r}. Required keys are {sorted(_REQUIRED_METRIC_KEYS)!r}. "
            f"Provided keys: {sorted(metrics.keys())!r}. "
            f"All three VCC metrics (MAE, PDS, DES) must be present in both "
            f"predictor and baseline metric dicts."
        )
