---
phase: 06-natural-language-qa-capstone
verified: 2026-09-11T15:40:37Z
status: passed
score: 5/5 must-haves verified (aggregated across 06-01/06-02/06-03)
---

# Phase 6: Natural-Language Q&A Capstone Verification Report

**Phase Goal:** A researcher can ask a plain-language question about single-cell data and get back an interpreted, citation-backed, uncertainty-aware answer without writing code — the capstone that ties together ingest/analysis/annotation/perturbation tools from earlier phases via a real LLM-driven Q&A session.
**Verified:** 2026-09-11T15:40:37Z
**Status:** passed
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | A researcher can ask a natural-language question and receive an interpreted prose answer (not raw JSON) | ✓ VERIFIED | `qa/session.py::ask_question()` returns `texts[0]` from `run_session()` as `answer_text`. Live human-run of `test_qa_multi_tool_compose_with_citations` (54.43s, human-executed, ANTHROPIC_API_KEY present) confirmed a real prose answer was produced, not raw tool JSON, with 10/10 citations resolved and real DE results (32 significant genes). |
| 2 | Every factual claim carries an inline `[ref:TOOL_NAME:SHA256_PREFIX]` citation tag, and every citation resolves to a real JSONL log record | ✓ VERIFIED | `qa/citations.py::CITATION_RE` implements the exact tag format; `QA_SYSTEM_PROMPT` in `qa/session.py` mandates the format and forbids zero-citation answers. `agent/session.py`'s `_make_log_hook` forwards `result_sha256[:12]` back to the model in-band via `hookSpecificOutput.additionalContext` (fix from 06-03), making the protocol satisfiable rather than aspirational. Live run: 10/10 citation tags resolved, zero hallucinated. |
| 3 | Quantitative claims carry uncertainty (p-values, confidence scores, baseline comparisons) | ✓ VERIFIED | `QA_SYSTEM_PROMPT`'s UNCERTAINTY PROTOCOL names the exact fields (`pval_adj`, `logfoldchange`, `n_significant`, `confidence`, `model_call` vs `baseline_call`) per tool. Live run: 32 significant DE genes returned with a decimal value paired with a resolved citation (QA-03 assertion passed). |
| 4 | Caller receives `(answer_text, session_id, citation_results)` from `ask_question()` with no further parsing of raw tool output required | ✓ VERIFIED | `qa/session.py::ask_question()` signature and body return exactly this 3-tuple; `citation_results = verify_answer_citations(answer, log_path)` is always computed before return. Confirmed via `tests/test_qa_session.py` wiring tests (`TestAskQuestionWiring`, 4 tests, all passing) using `AsyncMock`. |
| 5 | Multi-tool composition: the answer required composing at least two distinct prior-phase tools (ingest + analyze), not a single-tool shortcut | ✓ VERIFIED | `tests/test_qa_integration.py` question explicitly requires ingest→analyze; live run logged 2 distinct tool_names, assertion `len(distinct_tools) >= 2` passed. |

**Score:** 5/5 truths verified

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `qa/__init__.py` | qa module package marker | ✓ VERIFIED | Exists, empty (0 lines) as designed — package marker only. |
| `qa/citations.py` | `parse_citation_ids()`, `verify_answer_citations()` | ✓ VERIFIED | Both functions implemented exactly per plan spec; regex `r'\[ref:([^:\]]+):([0-9a-f]{12})\]'` matches 12-lowercase-hex requirement; `verify_answer_citations` reads JSONL, resolves by `tool_name` + `result_sha256` prefix match. |
| `qa/session.py` | `ask_question()`, `QA_SYSTEM_PROMPT` | ✓ VERIFIED | No `NotImplementedError` remains. `QA_SYSTEM_PROMPT` contains all four protocol sections (CITATION, UNCERTAINTY, ANTI-HALLUCINATION, mandatory-citation clause). `ask_question()` calls `run_session(..., system_prompt=QA_SYSTEM_PROMPT)` then `verify_answer_citations()`. |
| `tests/test_qa_citations.py` | 7 unit tests for citation parsing/verification | ✓ VERIFIED | 7 tests present and passing (`test_parse_citation_ids_finds_tags`, `_empty`, `_ignores_malformed`, `test_verify_answer_citations_resolves_match`, `_unresolved`, `_empty_log`, `_empty_answer`). |
| `tests/test_qa_session.py` | Unit tests for ask_question wiring (not in original must_haves but delivered in 06-02) | ✓ VERIFIED | 13 tests present and passing: prompt-structure (5), signature (4), wiring via AsyncMock (4). |
| `tests/test_qa_integration.py` | live_llm end-to-end test covering QA-01/02/03 | ✓ VERIFIED | Full test body present (no `pytest.skip` stub); collects and skips cleanly under `-m "not live_llm"`; human-executed live run PASSED in 54.43s (evidence provided, not re-executed in this environment per no-API-key constraint). |
| `agent/session.py` (modified) | `system_prompt` kwarg on `build_options()`/`run_session()`; `permission_mode` + citation-hash forwarding fixes | ✓ VERIFIED | `system_prompt: str = SYSTEM_PROMPT` present on both functions (additive, default preserves existing behavior). `permission_mode="bypassPermissions"` present (06-03 fix for headless hang). `_make_log_hook` forwards `result_sha256` via `additionalContext` (06-03 fix for uncitable hash). |
| `agent/logging.py` (modified) | `log_tool_call()` returns computed sha256 | ✓ VERIFIED | `log_tool_call()` returns `result_sha256` (line 55), enabling the hash-forwarding fix in `agent/session.py`. |
| `agent/tools.py` (modified) | `analyze_dataset_tool` passes through DE args | ✓ VERIFIED | `run_de`, `de_groupby`, `de_group1`, `de_group2`, `de_n_genes` all forwarded from tool args to `AnalysisConfig`/`analyze()`. |

### Key Link Verification

| From | To | Via | Status | Details |
|------|-----|-----|--------|---------|
| `qa/session.py` | `agent/session.py::run_session()` | `system_prompt=QA_SYSTEM_PROMPT` kwarg | ✓ WIRED | Line 108-113 of `qa/session.py`: `run_session(question, session_memory=session_memory, log_path=log_path, system_prompt=QA_SYSTEM_PROMPT)`. |
| `tests/test_qa_integration.py` | `qa/session.py::ask_question()` | `asyncio.run(ask_question(...))` | ✓ WIRED | Line 53-55 of test file, exact pattern present. |
| `qa/citations.py` | `agent/logging.py` JSONL log schema | `verify_answer_citations` reads `log_path` | ✓ WIRED | `log_path.read_text().splitlines()` + `json.loads`; schema fields (`tool_name`, `result_sha256`) match `agent/logging.py`'s record shape exactly. |
| `qa/session.py::ask_question()` | `qa/citations.py::verify_answer_citations()` | called after `run_session()` returns | ✓ WIRED | Line 115: `citation_results = verify_answer_citations(answer, log_path)`. |
| `tests/test_qa_integration.py` | `qa/citations.py::verify_answer_citations()` | direct import + assertion on `citation_results` | ✓ WIRED | `from qa.citations import parse_citation_ids` + assertions on `citation_results` returned by `ask_question()`. |
| `agent/session.py` PostToolUse hook | model context | `hookSpecificOutput.additionalContext` carrying `result_sha256[:12]` | ✓ WIRED | Confirmed present; this is the critical fix (06-03) that makes the citation protocol achievable — without it the model has no way to know the hash it must cite. |

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|-------------|-------------|--------|----------|
| QA-01 | 06-01, 06-02, 06-03 | Researcher asks NL question, gets interpreted answer composing tools automatically | ✓ SATISFIED | `ask_question()` API + `QA_SYSTEM_PROMPT` steer the LLM to use tools; live test requires and confirms ≥2 distinct tool calls (ingest + analyze) in a single answer. REQUIREMENTS.md marks QA-01 Complete, mapped to Phase 6. |
| QA-02 | 06-01, 06-02, 06-03 | Every answer links back to specific logged tool-call result(s); no prose-only answers | ✓ SATISFIED | `[ref:TOOL_NAME:SHA256_PREFIX]` protocol + `verify_answer_citations()` resolution mechanism; live run showed 10/10 citations resolved, zero hallucinated. REQUIREMENTS.md marks QA-02 Complete. |
| QA-03 | 06-01, 06-02, 06-03 | Quantitative claims carry surfaced confidence/uncertainty, not bare fact | ✓ SATISFIED | UNCERTAINTY PROTOCOL in `QA_SYSTEM_PROMPT` names exact fields per tool type; live test asserts decimal value + non-empty `citation_results` together (proxy for "uncertainty-backed, not hallucinated"). REQUIREMENTS.md marks QA-03 Complete. |

No orphaned requirements: REQUIREMENTS.md maps only QA-01/02/03 to Phase 6, and all three appear in every plan's `requirements` frontmatter field.

### Anti-Patterns Found

None. Scanned `qa/__init__.py`, `qa/citations.py`, `qa/session.py`, `tests/test_qa_citations.py`, `tests/test_qa_session.py`, `tests/test_qa_integration.py`, `agent/session.py`, `agent/logging.py`, `agent/tools.py` for TODO/FIXME/XXX/HACK/PLACEHOLDER/`NotImplementedError`/empty-return stubs. Only match was the string `"not a stub / placeholder"` inside a test assertion comment in `tests/test_qa_session.py` (not an anti-pattern — it's a comment describing what the test checks for).

### Automated Verification Performed

- `uv run pytest tests/test_qa_citations.py tests/test_qa_session.py tests/test_qa_integration.py -q -m "not live_llm"` → 20 passed, 1 deselected (the live_llm test, correctly skipped without ANTHROPIC_API_KEY).
- `uv run pytest tests/ -q --ignore=tests/test_vcc_smoke.py -m "not live_llm and not bio_fm_smoke and not vcc_data"` → 156 passed, 3 deselected — full fast suite green, no regressions from Phase 6 changes to `agent/session.py`, `agent/logging.py`, `agent/tools.py`.
- Verified all commit hashes referenced in the three SUMMARY.md files exist in `git log` (9238d22, 8b2a79c, 6ce968d, 2367d80, 587b673, 52778b4, 63c77f6, plus docs commits).
- Cross-checked code content of `qa/session.py`, `qa/citations.py`, `agent/session.py`, `tests/test_qa_integration.py` line-by-line against SUMMARY claims — no discrepancies found; SUMMARYs accurately describe what exists.

### Human Verification Required

None outstanding. The one live_llm-gated item (`tests/test_qa_integration.py::test_qa_multi_tool_compose_with_citations`) was already executed by the human just prior to this verification call: PASSED in 54.43s, 10/10 citations resolved, 2 distinct tools logged (ingest + analyze), real DE results (32 significant genes). This is treated as accepted human evidence per the verification instructions and was not re-executed in this environment (no ANTHROPIC_API_KEY available here).

### Gaps Summary

No gaps found. All three plans (06-01, 06-02, 06-03) deliver exactly what their frontmatter `must_haves` specify, the code is substantive (no stubs remaining), all key links are wired, the full non-live test suite is green (156/156), and the live end-to-end test — the only artifact that structurally cannot be verified without a real API key — has documented, credible human-executed evidence of passing with the exact assertions (QA-01/02/03) the phase goal requires. Two production-path bugs (headless permission hang, citation-hash-computed-after-model-saw-response) were found and fixed during the 06-03 checkpoint, which is exactly the kind of gap a live_llm-gated checkpoint is designed to catch — both fixes are present in the current codebase and covered by the passing fast suite plus the live run.

Note (non-blocking, informational): `ask_question()` has no CLI/script entry point exposing it directly to an end user outside of tests — consistent with the existing project pattern (`agent/session.py::run_session()` from Phase 3 is similarly only invoked from tests, not a user-facing script). The phase's Success Criteria and must_haves define the researcher-facing contract as the `ask_question()` API function signature itself, which is what was verified; this does not block phase completion but is worth noting if a future phase intends an actual CLI/UI for researchers.

---

*Verified: 2026-09-11T15:40:37Z*
*Verifier: Claude (gsd-verifier)*
