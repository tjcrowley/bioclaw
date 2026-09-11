---
phase: 06-natural-language-qa-capstone
plan: 02
subsystem: qa
tags: [system-prompt, citation-protocol, uncertainty-protocol, anti-hallucination, tdd]

requires:
  - phase: 06-natural-language-qa-capstone
    plan: 01
    provides: qa/session.py stub (ask_question surface + QA_SYSTEM_PROMPT placeholder), qa/citations.py verify_answer_citations, agent/session.py system_prompt kwarg
provides:
  - qa/session.py fully implemented (ask_question calls run_session with QA_SYSTEM_PROMPT, then verify_answer_citations)
  - QA_SYSTEM_PROMPT with citation + uncertainty + anti-hallucination + mandatory-citation protocols
  - tests/test_qa_session.py (13 unit tests -- prompt structure + wiring + edge cases)
affects: [06-03, phase-6-wave-2]

tech-stack:
  added: []
  patterns:
    - "Structural (unit) verification of a system prompt: assert the LLM-facing string contains required protocol keywords ([ref:, SHA256_PREFIX, MUST, confidence, baseline, pval_adj/p-value) rather than a live-LLM behavior test -- makes prompt drift a hard-fail in CI without requiring an API key"
    - "asyncio.run() inside sync pytest tests + unittest.mock.AsyncMock -- matches tests/test_agent_session_wiring.py's existing pattern; avoids adding pytest-asyncio as a new dependency"
    - "Reporting-not-raising citation verification: verify_answer_citations returns list[(tool, sha, record|None)]; ask_question does not raise on unresolved (None) citations -- policy lives in the caller/test, keeps ask_question a pure wrapper"

key-files:
  created:
    - tests/test_qa_session.py
  modified:
    - qa/session.py

key-decisions:
  - "Kept ask_question a pure wrapper -- no raise/warn on unresolved citations; verify_answer_citations is a reporting function whose caller decides policy. Plan 06-03's live integration test will assert count/quality of citation_results; keeping the wrapper policy-free means the same ask_question can serve both strict tests and a future exploratory CLI."
  - "Added a fourth 'mandatory citation' clause to QA_SYSTEM_PROMPT ('You MUST include at least one [ref:...] citation') and an explicit anti-hallucination clause ('MUST invoke the corresponding tool in this session') -- the plan's must_haves.truths and <action> block both required these on top of 06-RESEARCH.md's Pattern 1 example, which had them softer/implicit."
  - "TDD test file uses asyncio.run() inside sync tests (matching tests/test_agent_session_wiring.py's pattern) rather than adding pytest-asyncio -- keeps the fast/CI suite dependency footprint stable; the async surface of ask_question is still fully exercised via AsyncMock."

patterns-established:
  - "QA_SYSTEM_PROMPT protocol section shape: four labeled blocks (CITATION PROTOCOL / UNCERTAINTY PROTOCOL / ANTI-HALLUCINATION PROTOCOL / mandatory-citation clause) -- Plan 06-03 asserts on 'MUST' + '[ref:' + 'SHA256_PREFIX' + 'confidence' presence, so future edits to the prompt keep these labels/keywords or the fast-suite unit tests break loudly."

requirements-completed: [QA-01, QA-02, QA-03]

# Metrics
duration: 4min
completed: 2026-09-10
---

# Phase 6 Plan 02: ask_question() + QA_SYSTEM_PROMPT Summary

**Wired the Phase 6 Q&A entry point: `ask_question()` in `qa/session.py` now delegates to `run_session()` with a citation- and uncertainty-enforcing `QA_SYSTEM_PROMPT`, then post-processes the answer through `verify_answer_citations()` and returns `(answer, session_id, citation_results)` -- closing QA-01/02/03 structurally so Plan 06-03's live integration test can drive it end-to-end.**

## Performance

- **Duration:** ~4 min
- **Started:** 2026-09-11T01:47:41Z
- **Completed:** 2026-09-11T01:51:18Z
- **Tasks:** 1 (TDD: RED + GREEN)
- **Files modified:** 2 (1 created, 1 modified)

## Accomplishments
- `qa/session.py`: `ask_question()` fully implemented -- no more `NotImplementedError`. Calls `run_session(system_prompt=QA_SYSTEM_PROMPT)`, extracts `texts[0]` (or `""` on empty), calls `verify_answer_citations(answer, log_path)`, returns `(answer, session_id, citation_results)`.
- `QA_SYSTEM_PROMPT`: full four-protocol string constant -- citation format (`[ref:TOOL_NAME:SHA256_PREFIX]`), uncertainty (names `pval_adj`/`logfoldchange`/`n_significant` for DE, `confidence` for annotation, `model_call` vs `baseline_call` for perturbation), anti-hallucination (`MUST invoke the corresponding tool ... in this session`), mandatory citation (`MUST include at least one [ref:...]`).
- `tests/test_qa_session.py`: 13 unit tests, all green -- prompt-structure assertions (5), signature assertions (4), wiring assertions with `AsyncMock` (4). No API key or LLM required.
- Full fast suite: 156/156 passing (3 deselected: live_llm/bio_fm_smoke/vcc_data).

## Task Commits

Each task step was committed atomically per the TDD workflow:

1. **Task 1 RED: add failing tests for ask_question and QA_SYSTEM_PROMPT** - `6ce968d` (test)
2. **Task 1 GREEN: implement ask_question and QA_SYSTEM_PROMPT** - `2367d80` (feat)

No REFACTOR commit was needed -- the GREEN implementation matched the plan's `<action>` block exactly and no cleanup was warranted.

**Plan metadata:** _pending_ (final docs commit below)

## Files Created/Modified
- `qa/session.py` - `QA_SYSTEM_PROMPT` promoted from `""` placeholder to full four-protocol string; `ask_question()` promoted from `NotImplementedError` stub to full implementation (calls `run_session` with `system_prompt=QA_SYSTEM_PROMPT` then `verify_answer_citations`, returns 3-tuple)
- `tests/test_qa_session.py` - 13 unit tests in three classes: `TestQASystemPrompt` (5 tests: nonempty, citation-format keywords, uncertainty-fields-named, anti-hallucination keywords, MUST present), `TestAskQuestionSignature` (4 tests: coroutine, required params, `log_path` default is `Path`, `session_memory` default is `None`), `TestAskQuestionWiring` (4 tests: `run_session` called with `system_prompt=QA_SYSTEM_PROMPT`, returns 3-tuple, `verify_answer_citations` called with answer + log_path, empty-texts fallback)

## Decisions Made
- **`ask_question` does NOT raise on unresolved citations.** `verify_answer_citations` returns a list where `record is None` marks a hallucinated citation, but the plan explicitly instructs "Do NOT raise or hard-block on citation failures -- verify_answer_citations is a reporting function; assertions happen in tests." Plan 06-03's live integration test will inspect `citation_results` and assert its shape/count; this wrapper remains policy-free so a future exploratory CLI can use the same function without different behavior.
- **Added mandatory-citation + anti-hallucination clauses beyond 06-RESEARCH.md's Pattern 1 example.** The RESEARCH file's Pattern 1 example only had CITATION PROTOCOL + UNCERTAINTY PROTOCOL. The plan's `must_haves.truths` required (c) an explicit anti-hallucination instruction and (d) mandatory-citation language ("You MUST include at least one [ref:...] citation") -- both added as distinct sections in the final `QA_SYSTEM_PROMPT` so the fast-suite unit tests fail loudly if either is dropped in a future edit.
- **Used `asyncio.run()` in sync tests instead of adding `pytest-asyncio`.** The existing codebase (`tests/test_agent_session_wiring.py`) drives async code via `asyncio.run()` inside sync test functions; matching that pattern keeps the dev-dependency surface stable and the test file works out-of-the-box with the current `pytest>=8` pin.

## Deviations from Plan

None -- plan executed exactly as written. Adding a fourth "mandatory citation" clause and a distinct anti-hallucination section beyond the RESEARCH.md Pattern 1 example is what the plan's `<action>` block explicitly required (must_haves.truths items (c) and (d)), not a deviation.

## Issues Encountered

None. RED failed on the first assertion as expected (`len('') > 100`); GREEN passed all 13 new tests + 7 existing citation tests + 156 total fast-suite tests on first run.

## User Setup Required
None -- no external service configuration required. The live end-to-end test in `tests/test_qa_integration.py` (Plan 06-03) requires `ANTHROPIC_API_KEY`, but nothing in Plan 06-02's deliverables does.

## Next Phase Readiness
- **Plan 06-03 (live integration test):** `qa.session.ask_question` is now importable, awaitable, and returns the exact 3-tuple shape the integration test needs to assert against (`answer_text`, `session_id`, `citation_results`). Plan 06-03 replaces `tests/test_qa_integration.py::test_qa_multi_tool_compose_with_citations`'s `pytest.skip("Implemented in Plan 06-03")` with a real body that calls `ask_question`, then asserts on `citation_results` shape and content.
- No blockers for Phase 6 Wave 3 (Plan 06-03).

## Self-Check

- FOUND: qa/session.py (modified, full implementation)
- FOUND: tests/test_qa_session.py (created, 13 tests)
- FOUND: commit 6ce968d (Task 1 RED)
- FOUND: commit 2367d80 (Task 1 GREEN)
- VERIFIED: all 13 tests in tests/test_qa_session.py pass
- VERIFIED: all 7 tests in tests/test_qa_citations.py still pass (no regression)
- VERIFIED: full fast suite 156/156 pass with `-m "not live_llm and not bio_fm_smoke and not vcc_data"`
- VERIFIED: plan's inline `python -c` verification block prints "OK: ask_question signature and QA_SYSTEM_PROMPT content verified"

## Self-Check: PASSED

---
*Phase: 06-natural-language-qa-capstone*
*Completed: 2026-09-10*
