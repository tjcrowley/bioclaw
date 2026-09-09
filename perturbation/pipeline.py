"""predict() -- Phase 5, Plan 05-04 (PERT-01/PERT-02 composition).

This module is a documented stub. Plan 05-04 implements predict() here:
composes LinearAdditivePerturbationModel (perturbation/model.py) and
naive_baseline_predict (perturbation/baseline.py) into a single
PerturbationSummary result. Mirrors annotation/pipeline.py::annotate()'s
established pattern of composing FM + baseline calls into one bounded summary.

Return shape: PerturbationSummary (from perturbation/summary.py).

Downstream plans (05-05/05-06) import this module by path:
    from perturbation.pipeline import predict
"""
