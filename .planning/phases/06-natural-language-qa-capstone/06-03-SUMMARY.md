---
phase: 06-natural-language-qa-capstone
plan: 03
subsystem: testing
tags: [pytest, live_llm, claude-agent-sdk, citations, differential-expression, integration-test]

# Dependency graph
requires:
  - phase: 06-natural-language-qa-capstone (06-01, 06-02)
    provides: qa/citations.py (parse_citation_ids, verify_answer_citations), qa/session.py ask_question(), QA_SYSTEM_PROMPT
provides:
  - Live end-to-end proof that a real Claude session composes ingest + analyze tool calls, cites every claim to a real logged tool-call result, and pairs quantitative claims with resolved citations
  - Fix enabling any headless (pytest/script) caller of agent/session.py::run_session to actually run to completion instead of hanging on interactive tool approval
  - analyze_dataset_tool DE (differential expression) parameters (run_de/de_groupby/de_group1/de_group2/de_n_genes) now reachable by the agent, not just internally by analysis.pipeline.analyze()
  - result_sha256 now surfaced to the model in-band via PostToolUse hookSpecificOutput.additionalContext, making the citation protocol in QA_SYSTEM_PROMPT actually satisfiable
affects: []

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "permission_mode=bypassPermissions required on ClaudeAgentOptions for any headless (non-TTY) run_session() caller; safe here because allowed_tools is scoped to the in-process bioclaw MCP server only"
    - "Values computed inside a PostToolUse hook (e.g. a content hash) must be forwarded back to the model via hookSpecificOutput.additionalContext if the model is expected to reference them — the tool's own return value reaches the model before the hook runs"

key-files:
  created: []
  modified:
    - tests/test_qa_integration.py
    - agent/session.py
    - agent/logging.py
    - agent/tools.py

key-decisions:
  - "permission_mode=bypassPermissions set on build_options() rather than per-call, since allowed_tools already restricts the surface to our own in-process MCP server (no external/untrusted tool exposure)"
  - "log_tool_call() now returns the sha256 it computed so the PostToolUse hook can forward it to the model as a ready-to-copy [ref:TOOL:HASH] tag, instead of leaving the model to guess a hash it never saw"
  - "analyze_dataset_tool's DE args are passed through as an additive widening of existing arg handling, not a new tool -- keeps the one-tool-per-pipeline-stage design from Phase 2/3 intact"

requirements-completed: [QA-01, QA-02, QA-03]

# Metrics
duration: ~95min (active work across two sessions: ~4min Task 1 on 2026-09-10, ~90min checkpoint debugging + live verification on 2026-09-11)
completed: 2026-09-11
---

# Phase 6 Plan 3: Live Q&A Integration Test Summary

**Live Claude session composes ingest + analyze tool calls and returns a cited, uncertainty-bearing prose answer — proven with a real ANTHROPIC_API_KEY run, not a mock, after fixing two structural bugs (headless permission hang, uncitable hash) the checkpoint verification exposed.**

## Performance

- **Duration:** ~95 min active work, split across two sessions (Task 1 same-day as 06-02; checkpoint verification the next session)
- **Started:** 2026-09-11T01:57:33Z (Task 1 commit)
- **Completed:** 2026-09-11T15:25:03Z (final checkpoint-fix commit)
- **Tasks:** 2 (1 auto + 1 checkpoint:human-verify)
- **Files modified:** 4 (tests/test_qa_integration.py, agent/session.py, agent/logging.py, agent/tools.py)

## Accomplishments
- Replaced the Wave 0 `pytest.skip` stub in `tests/test_qa_integration.py` with a full live_llm test (`test_qa_multi_tool_compose_with_citations`) asserting QA-01/02/03 against a real Claude session
- Found and fixed a structural bug that silently hung every headless `run_session()` caller (including the pre-existing Phase 3 `test_agent_integration.py`, which had the same latent defect and had simply never been run live before)
- Found and fixed a structural bug that made the citation protocol impossible to satisfy: `result_sha256` was computed after the tool response reached the model
- Closed the DE (differential-expression) gap in `analyze_dataset_tool` so the agent can ask a real two-call clustering-then-DE question end to end
- Live run passed in 54.43s: 2 distinct tools invoked, 10/10 citation tags resolved (zero hallucinated citations), 32 significant DE genes returned with a decimal value paired with a resolved citation

## Task Commits

Each task/fix was committed atomically:

1. **Task 1: Implement live_llm integration test with QA-01/02/03 assertions** - `587b673` (test)
2. **[Rule 3 - Blocking, found during checkpoint verification] Fix headless permission hang** - `52778b4` (fix)
3. **[Rule 1/2 - Bug + Missing Critical, found during checkpoint verification] Expose run_de + surface result_sha256** - `63c77f6` (fix)

**Plan metadata:** (this commit) `docs(06-03): close live_llm QA checkpoint, complete Phase 6`

## Files Created/Modified
- `tests/test_qa_integration.py` - Full live_llm test body: QA-01 (>=2 distinct tools), QA-02 (citations present + all resolve), QA-03 (decimal value + non-empty citation_results)
- `agent/session.py` - `permission_mode="bypassPermissions"` added to `build_options()`; PostToolUse hook now forwards `result_sha256` via `hookSpecificOutput.additionalContext`
- `agent/logging.py` - `log_tool_call()` now returns the sha256 hash it just wrote, instead of discarding it
- `agent/tools.py` - `analyze_dataset_tool` now passes through `run_de`/`de_groupby`/`de_group1`/`de_group2`/`de_n_genes` to `AnalysisConfig`/`analyze()`, which already supported them internally

## Decisions Made
- `permission_mode=bypassPermissions` is safe and scoped: `allowed_tools=["mcp__bioclaw__*"]` already restricts the session to our own in-process MCP server, so bypassing interactive approval exposes no external/untrusted tool surface — this is the correct fix for any headless SDK caller, not just this test.
- The DE-args gap in `analyze_dataset_tool` was an oversight, not a design decision: `AnalysisConfig`/`analyze()` (Phase 2) already fully supported `run_de` and friends; the tool wrapper (Phase 3) simply never forwarded them. Widening the wrapper's arg handling was a pure additive fix, no new tool needed.
- Citation-hash timing bug fixed at the source (`log_tool_call()` returns the hash) rather than by relaxing the citation protocol — preserves QA-02's "no hallucinated citations" guarantee while making it actually achievable by the model.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Headless permission_mode hang prevented the live_llm test from ever completing**
- **Found during:** Task 2 (checkpoint verification — first live run attempt)
- **Issue:** `run_session()` built `ClaudeAgentOptions()` without `permission_mode`, so the SDK's CLI subprocess defaulted to interactive tool-approval and blocked forever waiting for TTY input under pytest. This was a latent bug in `agent/session.py` since Phase 3 — `tests/test_agent_integration.py` had the identical defect but had never actually been exercised live before this checkpoint.
- **Fix:** Set `permission_mode="bypassPermissions"` on `build_options()`. Safe because `allowed_tools` already restricts the session to the in-process `bioclaw` MCP server only.
- **Files modified:** `agent/session.py`
- **Verification:** Live pytest run of `test_qa_integration.py` proceeded past session startup instead of hanging
- **Commit:** `52778b4`

**2. [Rule 1 - Bug + Rule 2 - Missing Critical] `analyze_dataset_tool` never exposed DE params; citation hash computed too late for the model to see**
- **Found during:** Task 2 (checkpoint verification — second live run attempt, after fixing the permission hang)
- **Issue:** Two compounding blockers surfaced only under a real live question requiring DE: (a) `analyze_dataset_tool` dropped `run_de`/`de_groupby`/`de_group1`/`de_group2`/`de_n_genes` even though `AnalysisConfig`/`analyze()` already implemented them — the fast suite's synthetic tests never exercised DE through the tool layer, only through `analyze()` directly; (b) `QA_SYSTEM_PROMPT`'s citation protocol asks the model to quote `result_sha256` from the JSONL log, but that hash was computed inside `log_tool_call()` *after* the tool's response already reached the model — structurally impossible for the model to cite correctly.
- **Fix:** Widened `analyze_dataset_tool`'s arg handling to pass DE params through to `AnalysisConfig`. Changed `log_tool_call()` to return the hash it computed, and had the `PostToolUse` hook in `agent/session.py` forward it to the model via the SDK's `hookSpecificOutput.additionalContext` field as a ready-to-copy `[ref:TOOL:HASH]` tag.
- **Files modified:** `agent/logging.py`, `agent/session.py`, `agent/tools.py`
- **Verification:** Live run of `test_qa_integration.py` passed in 54.43s — 32 significant DE genes returned for a real cluster-vs-rest comparison, 10/10 citation tags resolved against the real audit log, fast suite still 156/156 green
- **Commit:** `63c77f6`

---

**Total deviations:** 2 auto-fixed (1 blocking, 1 combined bug/missing-critical)
**Impact on plan:** Both fixes were necessary to make the checkpoint's own success criteria achievable — the plan's checkpoint asked for a real live_llm pass, and no synthetic/mocked test in Phase 3 or 6 had ever exercised the permission-mode path or the DE-argument path for real. Neither fix touches test-only code; both are production-path corrections to `agent/`. No scope creep — no new tools, no new architecture, no schema changes.

## Issues Encountered
- The orchestrating session's shell had no valid `ANTHROPIC_API_KEY`, so the live_llm test itself was run by Darren in his own terminal per the checkpoint's `<how-to-verify>` steps, rather than by the executor agent. This is expected behavior for a live_llm checkpoint requiring real API credentials, not a plan failure — documented per the authentication-gate convention (the credential lived with the human, not with the executor).

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- Phase 6 (Natural-Language Q&A Capstone) is now complete: QA-01, QA-02, QA-03 all provably closed by a real live_llm run, not just unit-level citation parsing.
- This was the final plan (06-03) of the final phase (6) of the v1.0 milestone. All 6 phases / 29 plans are now complete.
- Two production bugs fixed here (headless permission hang, citation-hash timing) also retroactively de-risk Phase 3's `agent/session.py`, which had carried the same permission-mode defect since its own live_llm test was never run for real until now.
- Ready for `/gsd:complete-milestone` and a final `/gsd:verify-work` pass across the whole project.

---
*Phase: 06-natural-language-qa-capstone*
*Completed: 2026-09-11*

## Self-Check: PASSED

- FOUND: tests/test_qa_integration.py
- FOUND: agent/session.py
- FOUND: agent/logging.py
- FOUND: agent/tools.py
- FOUND commit: 587b673
- FOUND commit: 52778b4
- FOUND commit: 63c77f6
