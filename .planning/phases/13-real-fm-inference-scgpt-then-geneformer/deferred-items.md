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
