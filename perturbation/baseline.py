"""naive_baseline_predict() -- Phase 5, Plan 05-03 (PERT-02).

This module is a documented stub. Plan 05-03 implements naive_baseline_predict()
here: wraps cell_eval.build_base_mean_adata (Arc Institute's official naive
baseline). This baseline is NEVER hand-rolled -- it must delegate to the
cell-eval package's own implementation so VCC benchmark scores are directly
comparable to Arc Institute's reference numbers.

Per 05-RESEARCH.md Pitfall 4: obs column "target_gene" and control token
"non-targeting" match cell-eval's DEFAULT_PERT_COL/DEFAULT_CTRL -- do not
rename without updating every Phase 5 test.

Downstream plans (05-04/05-05) import this module by path:
    from perturbation.baseline import naive_baseline_predict
"""
