---
phase: 06-natural-language-qa-capstone
plan: 01
subsystem: qa
tags: [citations, regex, jsonl, agent-sdk, test-scaffolds, tdd]

requires:
  - phase: 03-agent-orchestration-wiring
    provides: agent/session.py run_session/build_options, agent/logging.py JSONL log schema (result_sha256 anchor)
provides:
  - qa/ package skeleton (empty __init__.py, citations.py, session.py stub)
  - parse_citation_ids() and verify_answer_citations() fully implemented
  - agent/session.py build_options() and run_session() accept system_prompt kwarg (additive, zero behavioral change)
  - tests/test_qa_citations.py (7 passing unit tests)
  - tests/test_qa_integration.py (live_llm-marked scaffold, skips cleanly)
affects: [06-02, 06-03, phase-6-wave-1, phase-6-wave-2]

tech-stack:
  added: []
  patterns:
    - "Citation tag regex: r'\\[ref:([^:\\]]+):([0-9a-f]{12})\\]' -- 12 lowercase hex chars, matches agent/logging.py's result_sha256 prefix"
    - "System-prompt injection via additive kwarg on build_options()/run_session() -- no reimplementation of session internals"
    - "Two-tier testing: pure-Python citation unit tests (fast, no LLM) + live_llm-marked integration scaffold (Plan 06-03 target)"

key-files:
  created:
    - qa/__init__.py
    - qa/citations.py
    - qa/session.py
    - tests/test_qa_citations.py
    - tests/test_qa_integration.py
  modified:
    - agent/session.py

key-decisions:
  - "Task 1's qa/citations.py is fully implemented (not stubbed) since it is pure Python with no LLM dependency -- Plan 06-02 uses these functions as-is, no rework needed"
  - "System-prompt injection is additive (kwarg with existing SYSTEM_PROMPT constant as default) so all Phase-3 callers of run_session/build_options continue to work unchanged -- verified by tests/test_agent_session_wiring.py still passing (8 tests)"
  - "Integration test in tests/test_qa_integration.py deliberately imports ask_question at module top-level so the qa/ skeleton's existence is asserted even when the live body is skipped -- catches broken package layout without needing an API key"

patterns-established:
  - "Citation format: [ref:TOOL_NAME:SHA256_PREFIX] where SHA256_PREFIX is the first 12 lowercase hex chars of the JSONL record's result_sha256 -- 12 is enough for uniqueness across a single session's tool calls, short enough to remain readable inline"
  - "verify_answer_citations() returns list[tuple[tool_name, sha_prefix, record_or_None]] preserving parse order -- callers iterate and count None entries to detect hallucinated citations"

requirements-completed: []

# Metrics
duration: 3min
completed: 2026-09-10
---

# Phase 6 Plan 01: Q&A Module Skeleton + system_prompt Wiring Summary

**qa/ package with fully-implemented parse_citation_ids()/verify_answer_citations() (regex + JSONL resolution), a session.py stub for Plan 06-03, and agent/session.py extended with an additive system_prompt kwarg on build_options()/run_session() -- Wave 0 contracts for Phase 6 all in place.**

## Performance

- **Duration:** ~3 min
- **Started:** 2026-09-11T01:42:04Z
- **Completed:** 2026-09-11T01:44:31Z
- **Tasks:** 2
- **Files modified:** 6 (5 created, 1 modified)

## Accomplishments
- agent/session.py: `build_options()` and `run_session()` accept `system_prompt: str = SYSTEM_PROMPT` kwarg -- Plan 06-03 can inject `QA_SYSTEM_PROMPT` without reimplementing session internals
- qa/citations.py: `parse_citation_ids()` + `verify_answer_citations()` fully working (not stubbed), backed by a 7-test unit suite
- qa/session.py: `ask_question()` stub raises NotImplementedError with a pointer to Plan 06-03 -- reserves the surface Wave 2 fills in
- tests/test_qa_integration.py: live_llm-marked scaffold reserving QA-01/02/03 target for Plan 06-03; skips cleanly under `-m "not live_llm"`

## Task Commits

Each task was committed atomically:

1. **Task 1: Add system_prompt kwarg to agent/session.py and create qa/ skeleton** - `9238d22` (feat)
2. **Task 2: Write test scaffolds for QA citations (unit) and Q&A integration (live_llm)** - `8b2a79c` (test)

**Plan metadata:** _pending_ (final docs commit below)

_Note: Task 2 marked tdd="true" in the plan, but Task 1 pre-implemented qa/citations.py (pure Python, no LLM dependency), so the RED/GREEN cycle collapsed to a single test-authoring commit -- tests were written to reflect the exact behavior of the already-implemented functions, all 7 passing on first run. Documented as intentional in Decisions Made._

## Files Created/Modified
- `agent/session.py` - Added `system_prompt` kwarg to `build_options()` and `run_session()`; kwarg defaults to existing `SYSTEM_PROMPT` constant (zero behavioral change for existing callers)
- `qa/__init__.py` - Empty package marker
- `qa/citations.py` - CITATION_RE regex + `parse_citation_ids()` + `verify_answer_citations()` (fully implemented)
- `qa/session.py` - `ask_question()` stub raising NotImplementedError; `QA_SYSTEM_PROMPT = ""` placeholder for Plan 06-03
- `tests/test_qa_citations.py` - 7 unit tests: finds/empty/ignores-malformed for parse; resolves/unresolved/empty-log/empty-answer for verify
- `tests/test_qa_integration.py` - live_llm-marked scaffold with module-level `ask_question` import (fails loudly if qa/ layout breaks); body is `pytest.skip("Implemented in Plan 06-03")`

## Decisions Made
- **Fully implement qa/citations.py in Task 1 rather than stub:** The plan's `<action>` block for Task 1 already contains the complete pure-Python implementation, and Task 2's tdd="true" cycle would otherwise be theatrical (write tests, write already-provided code). Instead, tests were authored in Task 2 against the real implementation and all 7 passed immediately. This preserves the Wave 0 contract (Wave 1 has stable citation semantics to build on) without redoing work.
- **Import `ask_question` at test module top level:** In `tests/test_qa_integration.py`, `from qa.session import ask_question` runs even under `-m "not live_llm"`, so a broken qa/ package layout fails collection loudly instead of silently at Plan 06-03 execution time.
- **Regex uses `[^:\\]]+` for tool name:** Allows the double-underscore MCP naming convention (`mcp__bioclaw__ingest_10x`) while rejecting a stray `]` or `:` inside the tool-name segment. Verified against real tool names logged by agent/logging.py.

## Deviations from Plan

None - plan executed exactly as written. (Fully-implementing qa/citations.py in Task 1 rather than stubbing it is what the plan's `<action>` block explicitly instructs -- "Implement the full citation module (not a stub -- this is pure Python, no LLM required)".)

## Issues Encountered
None.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- Plan 06-02 (citation-tagging system prompt + first live_llm citation-verification test): can now import `parse_citation_ids`/`verify_answer_citations` directly and inject a citation-enforcing system prompt via `run_session(..., system_prompt=...)` without touching agent/session.py internals
- Plan 06-03 (ask_question implementation): has a concrete `qa/session.py::ask_question` signature to fill in and a concrete `tests/test_qa_integration.py::test_qa_multi_tool_compose_with_citations` test body to complete
- No blockers for Phase 6 Wave 1/2

## Self-Check

- FOUND: agent/session.py (modified)
- FOUND: qa/__init__.py
- FOUND: qa/citations.py
- FOUND: qa/session.py
- FOUND: tests/test_qa_citations.py
- FOUND: tests/test_qa_integration.py
- FOUND: commit 9238d22 (Task 1)
- FOUND: commit 8b2a79c (Task 2)

## Self-Check: PASSED

---
*Phase: 06-natural-language-qa-capstone*
*Completed: 2026-09-10*
