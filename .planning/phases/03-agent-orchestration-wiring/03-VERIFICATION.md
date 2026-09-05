---
phase: 03-agent-orchestration-wiring
verified: 2026-09-05T00:00:00Z
status: human_needed
score: 3/3 must-haves verified at code/wiring level; 0/3 confirmed by live model behavior
human_verification:
  - test: "Run `ANTHROPIC_API_KEY=... uv run pytest tests/test_agent_integration.py -m live_llm -x -q` (or an equivalent manual interactive session: \"Ingest the 10x dataset at data/raw/sample1 and name it 'pilot', then cluster it\")"
    expected: "A real Claude Agent SDK session selects and calls `ingest_10x`/`analyze_dataset` from a natural-language request (AGENT-01); `agent/logs/tool_calls.jsonl` gains one record per real call with a `result_sha256` matching the actual tool result (AGENT-02); a second turn that does not restate the dataset_id answers with the dataset_id recorded during turn 1, proving `_recall_preamble()` is actually consulted by the model, not just present in the code (AGENT-03)."
    why_human: "Tool-selection and whether a live model actually incorporates the recall preamble into its answer are not deterministic and cannot be asserted as an exact-match unit test (03-RESEARCH.md Pitfall 4, 03-VALIDATION.md Manual-Only Verifications). This environment has no `ANTHROPIC_API_KEY` configured, so `tests/test_agent_integration.py` is cleanly skipped (confirmed: `1 skipped`) and has never been executed successfully against a real model, per the phase's own 03-05-SUMMARY.md admission (\"Remaining before Phase 3 is marked complete... running tests/test_agent_integration.py -m live_llm for the actual live acceptance evidence\")."
---

# Phase 3: Agent Orchestration Wiring Verification Report

**Phase Goal:** A Claude-based agent, running an OpenClaw-style agentic loop via Claude Agent SDK + MCP, plans and calls the Phase 1-2 tools with verifiable execution logging and persistent multi-turn memory — proving the tool-calling contract on cheap, deterministic tools before GPU/bio-FM complexity is introduced.
**Verified:** 2026-09-05
**Status:** human_needed
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | A researcher's request drives a plan → tool-call → observe → continue loop against the Phase 1-2 tools via Claude Agent SDK + MCP | ? UNCERTAIN (code path exists, wired correctly; never exercised against a real model) | `agent/session.py::run_session()` opens a `ClaudeSDKClient(options=build_options(...))` and loops `client.query()` / `client.receive_response()`; `build_options()` registers `bioclaw_server` under `mcp_servers`, `allowed_tools=["mcp__bioclaw__*"]`. `tests/test_agent_integration.py` is the only test that would exercise this end to end and is skipped here (`1 skipped`, no `ANTHROPIC_API_KEY`) |
| 2 | Every tool call is logged with request/response detail sufficient to verify real invocation, not simulated text | ✓ VERIFIED (mechanism + wiring), ? UNCERTAIN (live capture) | `agent/logging.py::log_tool_call` writes one JSON-lines record (`ts`, `tool_name`, `tool_input`, `is_error`, `result_sha256`, `result_preview`) per call; 5/5 `tests/test_agent_logging.py` tests pass (append-only, deterministic hash, error path, dir auto-create). `agent/session.py::_make_log_hook` wires it as a `PostToolUse` `HookMatcher`, confirmed structurally by `test_build_options_returns_claude_agent_options`. No test proves a *real* SDK dispatch actually fires this hook (only the skipped live test would) |
| 3 | The agent recalls dataset references and prior findings across multiple turns within the same session | ✓ VERIFIED (write + read-back code and unit tests), ? UNCERTAIN (live recall by the model) | Write half: `record_dataset_reference()` hook parses `dataset_id` from a tool result and calls `SessionMemory.record()` — 4/4 tests pass (valid id, non-JSON, JSON w/o id, malformed response). Read half: `_recall_preamble()` reads `SessionMemory.recent_datasets()` — 2/2 tests pass (empty when nothing recorded, non-empty with content after record). `run_session()` calls `_recall_preamble()` fresh before **every** turn (`agent/session.py:181`) and prepends it to `client.query()`'s prompt — this is the actual fix that closed the earlier write-only-memory gap. No fast-tier test drives `run_session()`'s loop itself (only the skipped live test does), so the turn-2-recalls-turn-1 behavior is unit-verified at the component level but not exercised end to end |

**Score:** 3/3 truths have real, non-stub, correctly-wired supporting code verified by fast-tier tests; 0/3 have been confirmed by an actual live-model run in this environment.

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `agent/tools.py` | `ingest_10x_tool`/`analyze_dataset_tool` `@tool`-decorated handlers calling real `ingest_10x()`/`analyze()` verbatim | ✓ VERIFIED | Both handlers call the Phase 1/2 functions directly (`ingest_10x(args["path"], args["name"], store_root=STORE_ROOT)`, `analyze(args["name"], version=version, store_root=STORE_ROOT)`), no reimplemented logic. `version` correctly omitted from schema, read via `args.get`. 5/5 `tests/test_agent_tools.py` tests pass, including a real ingest→analyze round trip on a structured synthetic dataset |
| `agent/server.py` | `bioclaw_server` in-process MCP server assembling both tools | ✓ VERIFIED | `create_sdk_mcp_server(name="bioclaw", version="1.0.0", tools=[ingest_10x_tool, analyze_dataset_tool])`; import-and-wrap test passes |
| `agent/logging.py` | `log_tool_call` async JSON-lines writer | ✓ VERIFIED | Matches spec exactly (name/input/result-hash/error/timestamp), append-only, `default=str` guards non-JSON-native tool_response. 5/5 tests pass |
| `agent/memory.py` | `SessionMemory` SQLite-backed record/recall store | ✓ VERIFIED | `record()`/`recent_datasets()` present, session-isolated, most-recent-first, disk-persistent across new instances. 6/6 tests pass |
| `agent/session.py` | `build_options()`, `record_dataset_reference()`, `_recall_preamble()`, `run_session()` wiring all three modules together | ✓ VERIFIED (wired), ? UNCERTAIN (only unit-level, no mocked-client test of `run_session()`'s loop itself) | All four functions present and match plan spec; `run_session()` correctly loops `_recall_preamble()` → `client.query()` per turn. 7/7 `tests/test_agent_session_wiring.py` tests pass, but none of them call `run_session()` — the loop-level behavior is only exercised by the skipped live test |

### Key Link Verification

| From | To | Via | Status | Details |
|------|-----|-----|--------|---------|
| `agent/tools.py` | `ingest/pipeline.py:ingest_10x`, `analysis/pipeline.py:analyze` | direct function call in handler body | ✓ WIRED | Confirmed by source read; round-trip test in `test_agent_tools.py` exercises both real functions with real data |
| `agent/server.py` | `agent/tools.py` | `create_sdk_mcp_server(tools=[...])` | ✓ WIRED | Confirmed by source read + import test |
| `agent/session.py` (`build_options`) | `agent/server.py:bioclaw_server`, `agent/logging.py:log_tool_call`, `agent/memory.py:SessionMemory` | `ClaudeAgentOptions(mcp_servers=..., hooks={"PostToolUse": [HookMatcher(hooks=[_make_log_hook(...), record_dataset_reference(...)])]})` | ✓ WIRED | Confirmed by source read and `test_build_options_returns_claude_agent_options` (asserts `HookMatcher` instances present with non-empty `.hooks` lists) |
| `agent/session.py:record_dataset_reference` | `agent/memory.py:SessionMemory.record` | parses `dataset_id` from tool result JSON, calls `.record(session_id, dataset_id, note=...)` | ✓ WIRED | Confirmed by source read + 4 passing unit tests exercising the hook directly with synthetic `PostToolUseHookInput` dicts |
| `agent/session.py:run_session` | `agent/session.py:_recall_preamble` → `agent/memory.py:SessionMemory.recent_datasets` | called fresh before every turn, result prepended to `client.query()`'s prompt string | ✓ WIRED (by source inspection); ? UNCERTAIN (no test exercises `run_session()` itself, mocked or live-passing) | `agent/session.py:179-191` shows `preamble = _recall_preamble(...); await client.query(preamble + prompt)` inside the per-prompt loop, unconditionally on every iteration including turn 1 |

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|------------|-------------|--------|----------|
| AGENT-01 | 03-02, 03-05 | OpenClaw-style agentic loop (plan → tool call → observe → continue) orchestrates ingest/QC/analysis tools via Claude Agent SDK + MCP | ? NEEDS HUMAN | Tool surface + MCP server + SDK client wiring all exist, correctly built, and unit-tested at every seam. The actual "plan → tool call → observe → continue" loop driven by a real model has never been executed in this environment (no `ANTHROPIC_API_KEY`); `03-VALIDATION.md` itself designates this a Manual-Only Verification item, not something a unit test can assert (tool selection is non-deterministic) |
| AGENT-02 | 03-03, 03-05 | Every tool call logged with request/response detail sufficient to verify real invocation | ? NEEDS HUMAN (mechanism ✓ SATISFIED at code level) | `log_tool_call`'s record shape and append-only behavior are fully verified by 5 fast-tier tests, and its registration as a real `PostToolUse` hook is structurally verified. What has not been verified is a real SDK dispatch actually firing the hook against a genuine tool call — only the skipped live test proves that link end to end |
| AGENT-03 | 03-04, 03-05 | Session/memory persists dataset references and prior findings across a multi-turn conversation | ? NEEDS HUMAN (write ✓ + read-back code ✓ SATISFIED at code level) | This is the requirement that previously failed a plan-checker pass for being write-only. That specific gap is now closed in the code: `_recall_preamble()` exists, is unit-tested, and `run_session()` demonstrably calls it before every turn and prepends its output to the outgoing prompt (verified by direct source reading, not just SUMMARY claim). What remains unverified is whether a real Claude model, given that prepended context, actually answers correctly on turn 2+ without the user restating the dataset_id — this is exactly what the skipped `test_run_session_two_turns_ingest_then_recall` would prove |

No orphaned requirements: REQUIREMENTS.md maps only AGENT-01/02/03 to Phase 3, and all three appear in plan frontmatter `requirements` fields (03-02, 03-03, 03-04, 03-05).

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| — | — | none found | — | `grep` for TODO/FIXME/XXX/HACK/PLACEHOLDER/"not implemented"/empty-return stubs across `agent/*.py` found nothing beyond legitimate `return {}` (the SDK's documented empty `HookJSONOutput` return contract for a hook that has no output to give) |

All 8 commits claimed across the 5 plan SUMMARYs (`5099022`, `939fc89`, `73a8c5a`, `48bd7c1`, `c1eef61`, `5d33d75`, `e08da2b`, `59d9168`) were confirmed present in `git log`.

### Human Verification Required

### 1. Live Claude Agent SDK session (AGENT-01/02/03 end-to-end)

**Test:** With `ANTHROPIC_API_KEY` set, run `uv run pytest tests/test_agent_integration.py -m live_llm -x -q`. Optionally also run one interactive session manually (e.g. "Ingest the 10x dataset at `data/raw/sample1` and name it 'pilot', then cluster it") and inspect `agent/logs/tool_calls.jsonl`.

**Expected:** The model selects and calls `ingest_10x`/`analyze_dataset` from natural language (AGENT-01); `tool_calls.jsonl` gains a record per call whose `result_sha256` matches the real tool output (AGENT-02); a follow-up turn that does not restate the dataset_id answers with the dataset_id recorded during turn 1 (AGENT-03 read-back).

**Why human:** Model tool-selection and whether the model actually incorporates injected recall context into its final answer are non-deterministic behaviors that cannot be asserted as an exact-match automated test (per 03-RESEARCH.md Pitfall 4 and 03-VALIDATION.md's own Manual-Only Verifications section). This is also an external-service dependency (`ANTHROPIC_API_KEY`) not present in this verification environment — the test is cleanly `1 skipped`, not failed, but it has never actually passed against a real model per the phase's own SUMMARY.md.

### Gaps Summary

There are no code-level gaps: every artifact required by Phase 3 exists, is substantive (no stubs, no placeholders, no orphaned functions), and is correctly wired end to end by direct source inspection — including the specific fix (`_recall_preamble()` called before every turn in `run_session()`) that closed the earlier write-only-memory blocker on AGENT-03. All 81 fast-tier tests pass (1 deselected `live_llm` test, cleanly skipped for lack of `ANTHROPIC_API_KEY`).

The remaining gap is evidentiary, not structural: the phase's actual goal — "a Claude-based agent... plans and calls the tools" — is a live-model behavior that only `tests/test_agent_integration.py -m live_llm` (or an equivalent manual session) can prove, and that test has never been executed successfully in this project, by the phase's own SUMMARY admission. Until it is run once with a real `ANTHROPIC_API_KEY` and its output (`tool_calls.jsonl` entries + turn-2 recall behavior) inspected, Phase 3's goal is well-built and well-tested but not yet demonstrated.

---

*Verified: 2026-09-05*
*Verifier: Claude (gsd-verifier)*
