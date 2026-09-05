---
phase: 3
slug: agent-orchestration-wiring
status: draft
nyquist_compliant: true
wave_0_complete: false
created: 2026-09-05
---

# Phase 3 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest (already configured) |
| **Config file** | `pyproject.toml` `[tool.pytest.ini_options]` (`testpaths=["tests"]`, `pythonpath=["."]`); Wave 0 adds a `live_llm` custom marker |
| **Quick run command** | `uv run pytest tests/test_agent_tools.py tests/test_agent_logging.py tests/test_agent_memory.py -x` |
| **Full suite command** | `uv run pytest tests/ -q -m "not live_llm"` |
| **Estimated runtime** | ~15 seconds (fast tier, excludes any live Anthropic API call) |

---

## Sampling Rate

- **After every task commit:** Run `uv run pytest tests/test_agent_tools.py tests/test_agent_logging.py tests/test_agent_memory.py -x` (fast tier only)
- **After every plan wave:** Run `uv run pytest tests/ -q -m "not live_llm"`
- **Before `/gsd:verify-work`:** Fast-tier full suite must be green; at least one manual/nightly `live_llm` run demonstrated with its `agent/logs/tool_calls.jsonl` output inspected as the actual AGENT-01/02 acceptance evidence (no unit test can assert real Claude tool-selection behavior — see Research Pitfall 4)
- **Max feedback latency:** 15 seconds (fast tier)

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 03-01 | 01 | 0 | (infra) | unit | `uv run pytest tests/ -q -m "not live_llm"` | ❌ W0 | ⬜ pending |
| 03-02 | 02 | 1 | AGENT-01 | unit | `uv run pytest tests/test_agent_tools.py -x` | ❌ W0 | ⬜ pending |
| 03-03 | 03 | 1 | AGENT-02 | unit | `uv run pytest tests/test_agent_logging.py -x` | ❌ W0 | ⬜ pending |
| 03-04 | 04 | 1 | AGENT-03 | unit | `uv run pytest tests/test_agent_memory.py -x` | ❌ W0 | ⬜ pending |
| 03-05 | 05 | 2 | AGENT-01/02/03 (integration) | integration + smoke (`live_llm`, manual) | `uv run pytest tests/test_agent_integration.py -m live_llm -x` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*
*Exact plan count/wave grouping is TBD until the planner runs — this table will be reconciled against the actual PLAN.md files the planner produces, same non-blocking doc-drift risk flagged in Phase 2's 02-VALIDATION.md.*

---

## Wave 0 Requirements

- [ ] `uv add claude-agent-sdk` — required before any `@tool`/`create_sdk_mcp_server`/`ClaudeSDKClient` import can succeed
- [ ] `pyproject.toml`: register `live_llm` as a custom pytest marker so the fast tier can reliably exclude it via `-m "not live_llm"`
- [ ] `tests/test_agent_tools.py` — new file; stub for AGENT-01 tool-handler correctness (call `@tool`-decorated async functions directly, bypassing the SDK/LLM entirely)
- [ ] `tests/test_agent_logging.py` — new file; stub for AGENT-02 hook-logging behavior in isolation
- [ ] `tests/test_agent_memory.py` — new file; stub for AGENT-03 `SessionMemory` store in isolation (mirrors `tests/test_store.py`'s existing `DatasetStore` pattern)
- [ ] `tests/test_agent_integration.py` — new file, `@pytest.mark.live_llm`; one smoke test driving a real `ClaudeSDKClient` turn, requires `ANTHROPIC_API_KEY`, not part of the fast default suite

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Real Claude Agent SDK session drives an actual plan→tool-call→observe→continue loop against the in-process MCP server, selecting and invoking the correct tool from a natural-language request | AGENT-01 | Tool-selection and exact model phrasing are not deterministic even with a fixed prompt — cannot be asserted as an exact-match unit test (per 03-RESEARCH.md Pitfall 4); the `live_llm`-marked integration test only proves the loop *runs* end-to-end, not that Claude's specific tool choice is invariant across runs | Run `uv run pytest tests/test_agent_integration.py -m live_llm -x` with `ANTHROPIC_API_KEY` set; separately, run one interactive session manually (e.g. "Ingest the 10x dataset at data/raw/sample1 and name it 'pilot', then cluster it") and inspect `agent/logs/tool_calls.jsonl` to confirm both `ingest_10x` and `analyze_dataset` tool calls appear with matching result hashes |

---

## Validation Sign-Off

- [x] All tasks have `<automated>` verify or Wave 0 dependencies
- [x] Sampling continuity: no 3 consecutive tasks without automated verify
- [x] Wave 0 covers all MISSING references
- [x] No watch-mode flags
- [x] Feedback latency < 15s
- [x] `nyquist_compliant: true` set in frontmatter

**Approval:** approved 2026-09-05
