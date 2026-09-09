"""compute_vcc_metrics() / run_vcc_eval() -- Phase 5, Plan 05-05 (VCC-02).

This module is a documented stub. Plan 05-05 implements compute_vcc_metrics()
and run_vcc_eval() here: wraps cell_eval.MetricsEvaluator (Arc Institute's
official VCC metric computation) to produce PDS/DES/MAE scores. These are
NEVER hand-rolled -- cell-eval's MetricsEvaluator is the reference
implementation for VCC benchmark compatibility.

Downstream plans (05-05) also implements build_benchmark_report()
in benchmark/report.py, which consumes this module's output.

Import path:
    from benchmark.vcc_eval import compute_vcc_metrics, run_vcc_eval
"""
