# Deferred Items — Phase 13

Out-of-scope discoveries logged per execution scope-boundary rule (not fixed,
not caused by the plans that found them).

## 13-02: Pre-existing test-order pollution in tests/test_vcc_eval.py / tests/test_vcc_report.py

**Found during:** Task 1 verification (full-suite run per plan's `<verification>` block).

**Symptom:** 14 tests across `tests/test_vcc_eval.py` and `tests/test_vcc_report.py` fail
when run as part of the full `uv run pytest tests/ -q -m "not live_llm and not
bio_fm_smoke and not vcc_data and not census_data"` suite, but all 25 pass when
those two files are run in isolation.

**Confirmed pre-existing and unrelated to 13-02's changes:** Reproduced with
`--ignore=tests/test_perturbation_ensembl.py` (i.e. with none of this plan's new
test file in the run) — same 14 failures. Also reproduced with this plan's
`perturbation/summary.py`/`perturbation/ensembl.py` changes stashed away. This is
a pre-existing full-suite test-isolation issue (likely polars `pl.StringCache()`/
`pl.enable_string_cache()` global-state interaction visible in the warnings
output), not something introduced by 13-02 or 13-01.

**Action:** Not fixed — out of scope for 13-02 (files not in this plan's
`files_modified` list: `tests/test_vcc_eval.py`, `tests/test_vcc_report.py`,
`analysis/vcc_eval.py` or similar). Flagging for a future plan/cleanup pass.

## 13-03: Same full-suite flake — precise root cause identified

**Found during:** Task 2 verification (full-suite run).

**Confirmed still present and still unrelated:** Reproduced with
`--ignore=tests/test_perturbation_geneformer_client.py` (i.e. with none of
13-03's new test file in the run) — same 14 failures.

**Root cause (isolated via `-x -k`):** Not a polars string-cache issue as
13-02 speculated. The real traceback is
`numba.np.ufunc.parallel.set_num_threads` raising `ValueError: The number of
threads must be between 1 and 10` with `n=0`, inside
`cell_eval._evaluator.MetricsEvaluator.__init__` -> `pdex.pdex() ->
set_numba_threadpool(threads)`. Some earlier test in the full suite mutates
global thread-count state (e.g. `os.sched_getaffinity` monkeypatching in
`bio_fm_worker`/scGPT-related tests, which `pdex` likely reads via
`len(os.sched_getaffinity(0))` to size its numba threadpool) down to 0, and
it leaks across test modules since pytest runs in one process.

**Action:** Still not fixed — out of scope for 13-03 (none of the involved
files — `tests/test_vcc_eval.py`, `tests/test_vcc_report.py`,
`bio_fm_worker/run_scgpt_embed.py`, `cell_eval`/`pdex` — are in this plan's
`files_modified` list). A future cleanup plan should either restore
`os.sched_getaffinity` after the scGPT worker tests that monkeypatch it, or
have `test_vcc_eval.py`/`test_vcc_report.py` explicitly set numba's thread
count before running.
