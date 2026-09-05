# Phase 3: Agent Orchestration Wiring - Research

**Researched:** 2026-09-04
**Domain:** Claude Agent SDK (Python) + Model Context Protocol (MCP) — wiring an OpenClaw-style agentic loop (plan → tool call → observe → continue) to Phase 1/2's deterministic Python functions (`ingest_10x`, `analyze`), with verifiable execution logging and persistent multi-turn session memory.
**Confidence:** HIGH (Claude Agent SDK/MCP mechanics — verified directly against current official docs, not training-data recall) / MEDIUM (testing strategy for the agentic loop and exact execution-log schema — no single canonical external pattern, original synthesis from official building blocks) / LOW (nothing version-sensitive found beyond the general caveat that both `claude-agent-sdk` and MCP are fast-moving — see State of the Art)

## Summary

Phase 3 is explicitly "reuse a proven pattern, don't build a custom agent loop" (already decided in PROJECT.md and re-confirmed in this repo's pre-existing `.planning/research/STACK.md`/`ARCHITECTURE.md`). The concrete mechanics are: `pip install claude-agent-sdk` (PyPI, `>=3.10`, current `0.2.152`), define each Phase 1/2 function as a Python `@tool`-decorated handler, wrap them in an in-process `create_sdk_mcp_server(...)`, pass that server into `ClaudeAgentOptions(mcp_servers=...)`, and drive the loop with `ClaudeSDKClient` (multi-turn, automatic session-state retention across `.query()` calls within one process) rather than the one-shot `query()` function. This is directly confirmed, current, official documentation (`code.claude.com/docs/en/agent-sdk/*`), not training-data guesswork.

The three requirements map cleanly onto specific SDK primitives: **AGENT-01** (plan → tool call → observe → continue) is exactly what the SDK's built-in agent loop already does — Claude emits `AssistantMessage`s containing `ToolUseBlock`s, the SDK executes the matching in-process tool handler, the result comes back as a `UserMessage` tool-result content block, and the cycle repeats until a text-only `AssistantMessage` and a final `ResultMessage`. **AGENT-02** (verifiable execution logging) is best built as a `PreToolUse`/`PostToolUse` hook pair — hooks run in your own process (not inside Claude's context window) and are the SDK's documented mechanism for exactly this ("audit outputs, trigger side effects" is `PostToolUse`'s stated common use). **AGENT-03** (persistent multi-turn memory) has two layers: the SDK already retains full conversation transcript automatically within a `ClaudeSDKClient` session (and can resume/fork across process restarts via `resume`/`session_id`), but the project's own pre-existing pitfalls research (`PITFALLS.md`, Performance Traps) already identified that transcript retention alone is insufficient — the agent needs an explicit, versioned "which dataset are we discussing" pointer that survives automatic context compaction, which argues for a small application-level session/memory store (SQLite, mirroring `DatasetStore`'s own pattern) layered on top of, not instead of, the SDK's native session.

The one genuinely tricky implementation gotcha found this session: the Python `@tool` decorator's in-process handler **only forwards `content` and `is_error` from your return dict — `structuredContent` is silently dropped** unless you run a standalone (non-SDK) MCP server via the separate official `mcp` PyPI package. Since Phase 2's bounded summary dataclasses (`PreprocessSummary`, `ClusterSummary`, `DESummary`) are exactly the kind of structured, machine-readable result `structuredContent` exists for, the recommended pattern is simpler than fighting this: serialize the dataclass to a JSON string via `dataclasses.asdict()` + `json.dumps()` and return it as a single `text` content block — Claude reads JSON text natively, and this sidesteps the dropped-field gotcha entirely without needing a second, heavier standalone-MCP-server architecture just for this phase.

**Primary recommendation:** One in-process `claude_agent_sdk.create_sdk_mcp_server` exposing `ingest_10x` and `analyze` (plus any smaller Phase 1/2 primitives the planner wants separately callable) as `@tool`-decorated handlers that internally call the existing Phase 1/2 functions verbatim and return their bounded-dataclass result as JSON text; a `ClaudeSDKClient`-driven loop (not `query()`) for multi-turn sessions; a `PreToolUse`/`PostToolUse` hook pair that writes one JSON-lines record per tool invocation (tool name, args, result-or-error, wall-clock timestamps, and a hash of the result) to a log file — this is the AGENT-02 verifiable-execution-log deliverable; and a small SQLite-backed session/dataset-reference store (same pattern as `ingest/store.py::DatasetStore`) that the agent's tool handlers read/write explicitly, so "the dataset we're discussing" survives both process restarts and the SDK's own automatic context compaction — this is the AGENT-03 deliverable, layered on top of (not replacing) the SDK's native transcript retention.

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-------------------|
| AGENT-01 | OpenClaw-style agentic loop (plan → tool call → observe → continue) orchestrates ingest/QC/analysis tools via Claude Agent SDK + MCP | Verified against official `code.claude.com/docs/en/agent-sdk/{mcp,custom-tools,agent-loop}` — the SDK's built-in loop (`AssistantMessage` w/ `ToolUseBlock` → SDK executes matching in-process `@tool` handler → result returns as a tool-result content block on the next `UserMessage` → repeat until text-only response + `ResultMessage`) *is* this pattern; no custom loop code needed. See Architecture Pattern 1, Code Examples. |
| AGENT-02 | Every tool call logged with request/response detail sufficient to verify real invocation (not LLM-simulated) | Verified: `PreToolUse`/`PostToolUse` hooks are the SDK's documented mechanism for exactly this ("audit outputs" is `PostToolUse`'s stated common use, per `agent-loop` doc's Hooks table), run in-process outside Claude's context window. Directly addresses this repo's own pre-existing `PITFALLS.md` Pitfall 6 ("tool bypass"/simulated-tool-call risk), which explicitly named this phase as where the mitigation must be built in from day one. See Architecture Pattern 2, Common Pitfalls. |
| AGENT-03 | Session/memory persists dataset references and prior findings across a multi-turn conversation | SDK-native: `ClaudeSDKClient` retains full transcript automatically across `.query()` calls in one process; `resume`/session-store adapter persists across process restarts (verified, official docs). Insufficient alone per this repo's own `PITFALLS.md` Performance Traps ("No dataset versioning across a multi-turn session" — flagged as breaking "as soon as more than one processing run of the same source data exists," which is this MVP's default case) — recommend a small explicit app-level session/dataset-reference store layered on top, mirroring `ingest/store.py::DatasetStore`'s existing pattern. See Architecture Pattern 3, Composition section. |
</phase_requirements>

## Standard Stack

### Core

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|---------------|
| `claude-agent-sdk` | 0.2.152 (current on PyPI as of 2026-09-04; requires Python `>=3.10`) | Python client for the Claude Agent SDK — `ClaudeSDKClient`, `query()`, `@tool`, `create_sdk_mcp_server`, `ClaudeAgentOptions`, hooks | PROJECT.md's own explicit decision ("reuse a proven orchestration pattern instead of building agent infrastructure from scratch"); this repo's Python 3.12 pipeline env is already compatible (`>=3.10` floor). |
| MCP (Model Context Protocol) | Bundled/used implicitly via `claude-agent-sdk`'s in-process "SDK MCP server" mechanism — no separate `mcp` package install needed for this phase's in-process pattern | Tool-calling contract between the agent and the Phase 1/2 tool layer | The SDK's `create_sdk_mcp_server` already speaks MCP's tool schema/naming convention (`mcp__{server}__{tool}`) internally; no separate server process or `mcp` PyPI package required unless the planner later wants a standalone (non-in-process) server (see Alternatives Considered). |

### Supporting

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `mcp` (official Python MCP SDK) | 2.1.1 (current on PyPI) | Standalone (non-SDK-in-process) MCP server, if a tool must run in a separate process/environment | Only needed if a future tool (e.g. Phase 4's GPU-bound bio-FM tools, out of scope for Phase 3) can't share the orchestrator's Python env, **or** if `structuredContent` support is required from Python (the in-process `@tool` decorator silently drops it — see Pitfall 1). Phase 3's tools (`ingest_10x`, `analyze`) already run in-process in the same `venv` as the rest of this repo, so the in-process SDK server is sufficient and simpler for this phase. |
| `sqlite3` (stdlib) | stdlib | App-level session/dataset-reference memory store (AGENT-03) | Mirrors `ingest/store.py::DatasetStore`'s already-established, already-tested pattern in this exact repo — no new dependency, same design language. |
| `pytest` | already a dev dependency (`>=8`) | Unit-testing the tool-handler functions and the logging-hook logic in isolation from any live LLM call | See Validation Architecture — the parts of this phase that are deterministic Python (tool handlers, hook logging, session store) should be unit tested the same way Phase 1/2 were; the parts that require an actual Claude API call are a separate, explicitly-marked integration/smoke tier. |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| In-process `create_sdk_mcp_server` (`@tool` decorator) | Standalone `mcp` Python SDK server (stdio subprocess), configured via `ClaudeAgentOptions(mcp_servers={"bioclaw": {"command": ..., "args": [...]}})` | Standalone servers get real `structuredContent` support and process isolation (relevant for Phase 4's GPU envs), but add subprocess-management complexity and an extra dependency this phase doesn't need — Phase 1/2 tools already live in-process in this repo's own `venv`. Revisit for Phase 4, not Phase 3. |
| `ClaudeSDKClient` (recommended for AGENT-01/03) | One-shot `query()` per turn, manually threading `continue_conversation=True`/`resume=session_id` | `query()` is simpler for single-shot scripts but requires you to manually manage session continuation across calls; `ClaudeSDKClient` does this automatically within one process, which is the more natural fit for AGENT-03's "multi-turn... within the same session" wording. Use `query()` only for one-off, non-conversational invocations (e.g. a CI smoke test that fires a single prompt). |
| `PreToolUse`/`PostToolUse` hooks for logging | Wrapping each `@tool` handler body in a manual try/log/except block | Hooks are the SDK's own documented, first-class mechanism for this ("audit outputs" is `PostToolUse`'s stated purpose) and run centrally for every tool regardless of which handler is called — less repetition and less risk of a handler "forgetting" to log than hand-rolling logging inside each of N tool functions. Both are valid; hooks are recommended as the single source of truth so a missing log entry is structurally impossible, not just a discipline issue. |
| SQLite-backed app-level session/memory store | Rely solely on the SDK's native session-transcript retention/resume | The SDK's transcript retention is real and automatic, but this repo's own pre-existing research (`PITFALLS.md`) already flagged that transcript-only memory doesn't give you an explicit, versioned "current dataset" pointer that's robust to automatic context compaction — an explicit store closes that gap cheaply and mirrors a pattern (`DatasetStore`) already proven in this exact codebase. |

**Installation:**
```bash
uv add claude-agent-sdk
# mcp (standalone SDK) NOT needed for Phase 3's in-process tool pattern —
# only add later if Phase 4 needs a standalone/isolated-env MCP server.
```

## Architecture Patterns

### Recommended Project Structure
```
agent/
├── __init__.py
├── tools.py         # @tool-decorated handlers wrapping ingest_10x/analyze (+ any lower-level Phase 1/2 fns)
├── server.py         # create_sdk_mcp_server(...) assembling agent/tools.py into one in-process MCP server
├── logging.py        # PreToolUse/PostToolUse hook pair -> JSON-lines execution log (AGENT-02)
├── memory.py          # SQLite-backed dataset-reference/finding store (AGENT-03), mirrors ingest/store.py
├── session.py          # ClaudeSDKClient wrapper: system prompt, ClaudeAgentOptions wiring, run-loop entrypoint (AGENT-01)
└── logs/                # JSON-lines execution-log output directory (gitignored)
```
This mirrors the existing `ingest/`/`analysis/` shape (small, independently-testable modules + one composed entrypoint) and matches this repo's own pre-existing `ARCHITECTURE.md` proposal (`agent/{sessions,memory,tool_registry}`), adjusted to the concrete SDK primitives now confirmed available.

### Pattern 1: Wrapping an existing Phase 1/2 function as an SDK tool (AGENT-01)
**What:** A thin `@tool`-decorated handler that validates/forwards args to the existing `ingest_10x`/`analyze` function and serializes its bounded-dataclass result as JSON text — no reimplementation of Phase 1/2 logic.
**When to use:** Every Phase 1/2 entrypoint the agent needs to call.
**Example:**
```python
# Source: code.claude.com/docs/en/agent-sdk/custom-tools (verified, official) +
# this repo's ingest/pipeline.py::ingest_10x, analysis/pipeline.py::analyze
import json
from dataclasses import asdict
from typing import Any

from claude_agent_sdk import tool, create_sdk_mcp_server

from ingest.pipeline import ingest_10x
from analysis.pipeline import analyze, AnalysisConfig


@tool(
    "ingest_10x",
    "Ingest a 10x Genomics .mtx directory or .h5 file into the versioned "
    "dataset store, running standard QC. Returns the new dataset_id.",
    {"path": str, "name": str},
)
async def ingest_10x_tool(args: dict[str, Any]) -> dict[str, Any]:
    dataset_id = ingest_10x(args["path"], args["name"])
    return {"content": [{"type": "text", "text": json.dumps({"dataset_id": dataset_id})}]}


@tool(
    "analyze_dataset",
    "Run preprocess -> cluster -> (optional) differential expression on a "
    "named/versioned dataset from the store. Returns a bounded summary, "
    "never raw matrices.",
    {"name": str},  # 'version' intentionally omitted -> optional, see Pitfall 2
)
async def analyze_dataset_tool(args: dict[str, Any]) -> dict[str, Any]:
    version = args.get("version")  # optional param pattern (Pitfall 2)
    new_id, summary = analyze(args["name"], version=version)
    return {
        "content": [
            {"type": "text", "text": json.dumps({"dataset_id": new_id, **summary})}
        ]
    }


bioclaw_server = create_sdk_mcp_server(
    name="bioclaw",
    version="1.0.0",
    tools=[ingest_10x_tool, analyze_dataset_tool],
)
```

### Pattern 2: Verifiable execution logging via hooks (AGENT-02)
**What:** A `PostToolUse` hook that writes one JSON-lines record per completed tool call — this is the audit trail that lets a researcher (or a test) prove a result came from a real invocation, not simulated text.
**When to use:** Registered once, applies to every tool call for the whole session.
**Example:**
```python
# Source: code.claude.com/docs/en/agent-sdk/agent-loop's Hooks table
# ("PostToolUse... After a tool returns... Audit outputs") + custom-tools doc's
# confirmed content-block/is_error shape for what a tool result actually contains.
# Exact HookMatcher/HookCallback signature not directly quoted in the fetched
# docs this session -- flagged MEDIUM confidence, verify signature against
# `claude_agent_sdk.types` at implementation time (see Open Questions).
import hashlib
import json
import time
from pathlib import Path

LOG_PATH = Path("agent/logs/tool_calls.jsonl")


async def log_tool_call(tool_name, tool_input, tool_response, is_error, **_):
    record = {
        "ts": time.time(),
        "tool_name": tool_name,
        "tool_input": tool_input,
        "is_error": is_error,
        "result_sha256": hashlib.sha256(
            json.dumps(tool_response, sort_keys=True, default=str).encode()
        ).hexdigest(),
        "result_preview": str(tool_response)[:500],
    }
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with LOG_PATH.open("a") as f:
        f.write(json.dumps(record) + "\n")
```
**Verification property this buys you:** any final agent answer that cites a numeric result can be cross-checked against `tool_calls.jsonl` by `result_sha256` — an answer citing a result hash with no matching log line is, by construction, evidence of a simulated/hallucinated tool call (directly closes this repo's own pre-existing `PITFALLS.md` Pitfall 6).

### Pattern 3: Explicit dataset/session memory layered on SDK transcript retention (AGENT-03)
**What:** A small SQLite table (mirrors `DatasetStore`) recording `(session_id, dataset_id, note, created_at)` rows, written by the tool handlers themselves (not by the agent's free-text output) every time a dataset is ingested/analyzed within a session.
**When to use:** Alongside `ClaudeSDKClient`'s native transcript retention — this store is the fallback of record for "what dataset are we discussing" that survives automatic compaction (per this repo's own `PITFALLS.md` Performance Traps finding).
**Example:**
```python
# Source: original synthesis, directly modeled on this repo's own
# ingest/store.py::DatasetStore (same CREATE TABLE / sqlite3 pattern)
import sqlite3
from datetime import datetime, timezone

_CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS session_memory (
    session_id TEXT NOT NULL,
    dataset_id TEXT NOT NULL,
    note TEXT,
    created_at TEXT NOT NULL
)
"""

class SessionMemory:
    def __init__(self, root="agent/memory.sqlite"):
        self.conn = sqlite3.connect(root)
        self.conn.execute(_CREATE_TABLE_SQL)

    def record(self, session_id: str, dataset_id: str, note: str | None = None):
        self.conn.execute(
            "INSERT INTO session_memory VALUES (?, ?, ?, ?)",
            (session_id, dataset_id, note, datetime.now(timezone.utc).isoformat()),
        )
        self.conn.commit()

    def recent_datasets(self, session_id: str, limit: int = 5) -> list[str]:
        rows = self.conn.execute(
            "SELECT dataset_id FROM session_memory WHERE session_id = ? "
            "ORDER BY created_at DESC LIMIT ?",
            (session_id, limit),
        ).fetchall()
        return [r[0] for r in rows]
```
Call `SessionMemory.record(...)` from inside the `ingest_10x_tool`/`analyze_dataset_tool` handlers (Pattern 1) whenever they produce a new `dataset_id` — this makes the memory update a structural side effect of the tool call itself, not something the agent has to remember to do via free text.

### Anti-Patterns to Avoid
- **Building a custom plan/act/observe loop instead of using `ClaudeSDKClient`'s built-in one:** the SDK's loop already implements AGENT-01 exactly; reimplementing it duplicates work this repo's own PROJECT.md explicitly decided against.
- **Logging tool calls only from inside each `@tool` handler body:** works, but is easy to forget on a future Nth tool; a single `PostToolUse` hook applies uniformly and can't be silently skipped by a new handler that forgets to call a logger.
- **Relying only on `ClaudeSDKClient`'s automatic transcript retention for "which dataset are we discussing":** per this repo's own `PITFALLS.md`, this breaks the moment context compaction summarizes older turns or a second processing run of the same source data exists — always resolve "the current dataset" through the explicit `SessionMemory`/dataset-id mechanism, not by re-reading agent free text.
- **Returning a raw Python object or dataclass instance directly from a `@tool` handler:** the handler's return value must be the `{"content": [...], "is_error": ...}` dict shape; forgetting to serialize the bounded-summary dataclass (e.g. via `dataclasses.asdict()` + `json.dumps()`) will raise inside the SDK's content-block validation, not fail gracefully.
- **Assuming `structuredContent` round-trips through the in-process `@tool` decorator:** it doesn't (confirmed in official docs) — always serialize structured results as JSON inside a `text` content block for this phase's in-process pattern (see Pitfall 1).

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|--------------|-----|
| Plan → tool call → observe → continue loop | A custom while-loop calling the Anthropic Messages API directly and parsing tool_use blocks by hand | `ClaudeSDKClient`/`query()`'s built-in agent loop | This is precisely what PROJECT.md already decided to reuse rather than build; the SDK already handles multi-tool-call turns, retries, and message-type dispatch. |
| Tool-call permission/approval gating | A hand-rolled allowlist check before each function call | `ClaudeAgentOptions(allowed_tools=[...])` + `permission_mode` | Already a first-class, documented SDK concept (`mcp__{server}__{tool}` naming, wildcard support) — reinventing it duplicates a solved problem and is easy to get subtly wrong (e.g. forgetting a new tool needs to be added to the allowlist). |
| Tool-call execution auditing | Ad hoc `print`/logging statements scattered across handler bodies | `PreToolUse`/`PostToolUse` hooks writing one canonical JSON-lines log | Centralizes the AGENT-02 guarantee in one place instead of N handler-specific logging implementations that can drift or be forgotten. |
| MCP tool schema definition/validation | Hand-written JSON Schema validators for each tool's input | The `@tool` decorator's dict-schema-to-JSON-Schema conversion (or full JSON Schema dict for enums/optional fields) | Already handles the common case (`{"latitude": float}` style) and the full-JSON-Schema escape hatch for anything more complex (enums, optional fields) — no reason to hand-write a validator. |

**Key insight:** every mechanical piece Phase 3 needs (loop, permissioning, tool schema, hooks) already exists as a first-class Claude Agent SDK primitive, verified against current official documentation. The only code this phase should actually write is: (1) thin tool-handler wrappers around Phase 1/2 functions, (2) the logging-hook body, (3) the session/dataset-memory store, and (4) the top-level session/run-loop wiring — never a reimplementation of any SDK mechanism itself.

## Common Pitfalls

### Pitfall 1: The in-process Python `@tool` decorator silently drops `structuredContent`
**What goes wrong:** Returning `{"content": [...], "structuredContent": {...}}` from a Python `@tool` handler works fine at the type level, but only `content` and `is_error` are actually forwarded to Claude — `structuredContent` is dropped.
**Why it happens:** Confirmed directly in official docs (`custom-tools` page, "Return structured data" section): *"The Python `@tool` decorator forwards only `content` and `is_error` from the handler's return dict. To return `structuredContent` from Python, run a standalone MCP server instead of an in-process SDK server."*
**How to avoid:** For this phase's bounded-summary dataclasses (`PreprocessSummary`/`ClusterSummary`/`DESummary`/etc. from `analysis/summary.py`), serialize with `dataclasses.asdict()` + `json.dumps()` into a single `text` content block (see Pattern 1). Claude reads structured JSON embedded in text natively; there's no practical downside for this phase's scale, and it avoids standing up a standalone MCP server process purely to preserve a field this project doesn't need machine-parsed on the SDK side.
**Warning signs:** A `structuredContent` field set on a tool's return value that the calling code (or a test) expects to see reflected somewhere in the agent's context but never does.

### Pitfall 2: Python `@tool`'s dict schema treats every key as required
**What goes wrong:** `{"name": str, "version": int}` as a tool's input schema makes both `name` and `version` mandatory — there's no way to mark a dict-schema field optional.
**Why it happens:** Confirmed in official docs (`custom-tools` page): *"the dict schema treats every key as required... leave the parameter out of the schema, mention it in the description string, and read it with `args.get()` in the handler"* — this is the documented workaround, not a bug.
**How to avoid:** For `analyze_dataset_tool`'s optional `version` parameter (mirroring `analysis/pipeline.py::analyze`'s `version: int | None = None` signature), omit `version` from the schema dict, mention it in the tool's description string, and read it via `args.get("version")` in the handler (see Pattern 1's `analyze_dataset_tool` example). Alternatively, use the full JSON-Schema-dict form (not the shorthand `{"key": type}` dict) and explicitly control `required`.
**Warning signs:** Claude reports it can't call a tool without a value for a parameter that Phase 2's own function signature treats as optional.

### Pitfall 3: A handler's uncaught exception still reaches Claude as raw text — but the loop itself never crashes
**What goes wrong/right:** If `ingest_10x`/`analyze` raises (e.g. `RuntimeError` from `verify_counts_integrity()` failing, or `KeyError` from `DatasetStore.load()` on an unknown name/version), and the `@tool` handler doesn't catch it, the SDK's in-process MCP server catches the exception itself and converts it to an error tool result carrying the raw exception message — the agent loop continues, it does not crash.
**Why it happens:** Confirmed directly in official docs (`custom-tools` page's "Handle errors" table): *"Handler throws an uncaught exception → The MCP server converts it to an error result carrying the raw exception message. Claude sees that message, and the agent loop continues."*
**How to avoid:** This is actually the *correct* default behavior for AGENT-02's traceability goal (Phase 1/2's exceptions already carry good diagnostic text, e.g. `analyze()`'s `RuntimeError` messages explicitly name the dataset and which integrity checkpoint failed) — no extra try/except is strictly required. Only add an explicit `try/except` + `is_error: True` in a handler where you want to **compose a different, more actionable message than the raw Python exception string** (per the docs' own example, e.g. adding "try re-ingesting from source" context an HTTP status code alone wouldn't carry). Either way, the `PostToolUse` logging hook (Pattern 2) should log the error result the same as a success result — a failed tool call is still evidence the tool was really invoked, and belongs in the audit trail.
**Warning signs:** None if using the default behavior deliberately; a genuine bug would look like the agent loop silently proceeding as if a failed call had succeeded, which the logging hook's `is_error` field is specifically there to catch and make auditable.

### Pitfall 4: Testing an agentic loop that calls a real LLM is not a deterministic unit-test problem — don't try to force it into one
**What goes wrong:** Attempting to write standard `pytest` unit tests that assert exact LLM behavior (which tool it calls, in what order, with what exact phrasing) is inherently flaky — the model's tool-selection and phrasing are not deterministic, even at temperature 0 equivalents on Claude's API.
**Why it happens:** WebSearch-verified (MEDIUM confidence, no single official Anthropic testing-pattern doc found, but consistent across multiple independent community sources): the recommended split is to unit-test the **deterministic parts your code controls** (tool-handler functions, schema validation, hook logging logic, session/memory store) with all LLM calls mocked/excluded, and treat any test that exercises a live `ClaudeSDKClient`/`query()` call as a separate, slower integration/smoke tier — testing "behavioral patterns," not exact transcripts.
**How to avoid:** Structure Phase 3 tests in two tiers (see Validation Architecture below): (1) fast, CI-safe unit tests that call `ingest_10x_tool`/`analyze_dataset_tool`'s handler functions directly (as plain async Python functions, bypassing the SDK/LLM entirely) plus the hook/memory-store logic directly; (2) a small number of explicitly-marked, API-key-gated integration tests that drive one real `ClaudeSDKClient` turn end-to-end and assert on the *presence* of a matching log entry (AGENT-02's actual verification property) rather than on exact model phrasing.
**Warning signs:** A test suite that calls the real Anthropic API in every run (slow, costs money, flaky in CI) versus one with zero live-API coverage at all (never actually validates AGENT-01's real integration, only the mocked pieces around it) — both extremes are wrong; the two-tier split avoids each.

## Composition with Phase 1/2 and the Session/Memory Layer

**Question posed:** should the agent's tool handlers call `ingest_10x`/`analyze` directly, or go through some intermediate abstraction?

**Recommendation: directly, with zero intermediate abstraction** — Pattern 1's handlers are thin pass-throughs. This matches the "coarse-grained tool call" architecture this repo's own pre-existing `ARCHITECTURE.md` already specified ("Deterministic Pipeline Behind a Coarse-Grained Tool Call" — the agent invokes `ingest_10x(path)`/`analyze(name)` as typed tool calls rather than reasoning step-by-step through each pipeline stage) and requires no new abstraction layer between the agent tool surface and Phase 1/2's already-tested, already-composed entrypoints.

**Question posed:** does `SessionMemory` (Pattern 3) need to track anything beyond `dataset_id`?

**Recommendation:** start minimal — `(session_id, dataset_id, note, created_at)` is sufficient for AGENT-03's literal wording ("recalls dataset references and prior findings"). `note` is a free-text field the tool handler can populate with a one-line summary (e.g. `"analyze: 3 clusters, DE vs cluster 0"`) drawn from the bounded summary dataclass already being returned — this gives "prior findings" recall without inventing a second structured-findings schema this phase doesn't strictly need. Treat richer structured-findings storage as a candidate for Phase 6 (the NL Q&A capstone, which needs claim-traceability back to specific tool-call results) rather than over-building it here.

## Code Examples

Verified patterns from official sources:

### Multi-turn session with ClaudeSDKClient (AGENT-01/03)
```python
# Source: code.claude.com/docs/en/agent-sdk/agent-loop, /python (verified, official)
import asyncio
from claude_agent_sdk import ClaudeSDKClient, ClaudeAgentOptions, AssistantMessage, TextBlock, ResultMessage

async def main():
    options = ClaudeAgentOptions(
        mcp_servers={"bioclaw": bioclaw_server},          # Pattern 1's server
        allowed_tools=["mcp__bioclaw__*"],
        hooks={"PostToolUse": [log_tool_call]},             # Pattern 2's hook
        max_turns=30,
    )
    async with ClaudeSDKClient(options=options) as client:
        await client.query("Ingest the 10x dataset at data/raw/sample1 and name it 'pilot'")
        async for message in client.receive_response():
            if isinstance(message, AssistantMessage):
                for block in message.content:
                    if isinstance(block, TextBlock):
                        print(block.text)

        # Second turn -- session context (including which dataset_id resulted) retained automatically
        await client.query("Now cluster that dataset and tell me how many clusters you found")
        async for message in client.receive_response():
            if isinstance(message, ResultMessage) and message.subtype == "success":
                print(message.result)

asyncio.run(main())
```

### Capturing the session id for later resumption (AGENT-03, cross-process)
```python
# Source: code.claude.com/docs/en/agent-sdk/agent-loop (verified, official)
session_id = None
async for message in client.receive_response():
    if isinstance(message, ResultMessage):
        session_id = message.session_id  # save for `resume=session_id` in a later process
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|---------------|--------------------|-----------------|---------|
| Hand-rolled function-calling dispatcher against the raw Anthropic Messages API | `claude-agent-sdk` (`ClaudeSDKClient`/`query()` + `@tool`/`create_sdk_mcp_server`) | Current as of this SDK's `0.2.x` line (weekly-ish releases observed in `.planning/research/STACK.md`'s earlier note) | The SDK already implements the loop, permissioning, hook system, and MCP tool-schema plumbing PROJECT.md wanted to reuse rather than build. |
| Standalone MCP server for every custom tool | In-process "SDK MCP server" (`create_sdk_mcp_server`) for tools that share the orchestrator's Python process | Documented as the current recommended default for same-process tools; standalone servers reserved for cross-process/cross-environment needs | Removes an entire subprocess-management concern for Phase 3's tools, which already live in this repo's own `venv` — no version-conflict reason (unlike Phase 4's bio-FM tools) to isolate them. |

**Deprecated/outdated:**
- Nothing found to be deprecated within the Claude Agent SDK/MCP surface used by this phase as of this research date — flagged instead as **fast-moving**: both `claude-agent-sdk` (weekly-cadence PyPI releases) and the MCP spec itself are young and still evolving. Re-verify exact hook-callback signatures and `ResultMessage` field names against the installed package version at implementation time (see Open Questions).

## Open Questions

1. **Exact `HookMatcher`/hook-callback function signature and the full enum of hook input fields.**
   - What we know: `PreToolUse`/`PostToolUse` (and `UserPromptSubmit`/`Stop`/`SubagentStart`/`SubagentStop`/`PreCompact`) are confirmed to exist and fire where documented (official `agent-loop` doc's Hooks table, directly fetched and quoted above). Hooks are registered via `ClaudeAgentOptions.hooks: dict[HookEvent, list[HookMatcher]]`.
   - What's unclear: the exact Python callback signature (parameter names/types for `tool_name`, `tool_input`, `tool_response`, `is_error`, etc.) was not fully quotable from the pages fetched this session — the dedicated `/docs/en/agent-sdk/hooks` page (linked from, but not itself fetched in, this research pass) almost certainly has the authoritative signature.
   - Recommendation: planner/implementer should fetch `code.claude.com/docs/en/agent-sdk/hooks` directly (and/or `import inspect; help(claude_agent_sdk.HookMatcher)` once installed) before writing Pattern 2's hook for real — Pattern 2's code example above is a reasonable, docs-consistent sketch but its exact kwarg names are MEDIUM confidence, not HIGH.

2. **Should `ingest_10x`/`analyze` be exposed as two coarse tools (current recommendation) or split into more, finer-grained tools (e.g. separate `preprocess`/`cluster`/`differential_expression` tools)?**
   - What we know: this repo's own pre-existing `ARCHITECTURE.md` explicitly recommends coarse-grained tools ("the LLM plans and interprets, but does not micromanage every pipeline step") and this repo's own `PITFALLS.md` explicitly warns against "Agent-in-the-Loop for Every Pipeline Step" as an anti-pattern.
   - What's unclear: whether a researcher's natural-language request ("cluster this dataset at a higher resolution") needs the agent to call `cluster()` directly (with a custom `resolution`) rather than only `analyze()`'s default config.
   - Recommendation: expose `analyze()`'s existing `AnalysisConfig` fields (already a fully-parameterized dataclass: `resolution`, `n_neighbors`, `n_top_genes`, etc.) as optional tool-input fields on a single `analyze_dataset` tool (per Pitfall 2's optional-field pattern) rather than adding separate per-stage tools — this keeps the tool surface small (per `PITFALLS.md`'s Pitfall 6 mitigation: "keep the tool surface small, typed, and unambiguous... rather than exposing many overlapping variants that increase tool-selection error") while still letting a researcher's request drive real parameter choices.

3. **Where does the system prompt for this agent live, and how much of the "OpenClaw-style" framing needs to be spelled out explicitly vs. relying on Claude's own tool-use judgment?**
   - What we know: `ClaudeAgentOptions(system_prompt=...)` supports a plain string, a preset+append, or a file path (verified, official docs).
   - What's unclear: whether Phase 3 needs a bespoke system prompt at all, or whether tool descriptions + `allowed_tools` scoping is sufficient signal for a small, well-scoped tool surface (2 tools at this phase).
   - Recommendation: start with a short, explicit system-prompt string (not a preset) stating the domain framing ("You are a bioinformatics research assistant... always cite the specific dataset_id and tool result you're referencing") — this directly supports the eventual Phase 6 claim-traceability requirement and costs little to add now, per this repo's own `PITFALLS.md` recommendation that Pitfall 5/6 guardrails be built in from day one rather than retrofitted.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest (already configured) |
| Config file | `pyproject.toml` `[tool.pytest.ini_options]` (`testpaths=["tests"]`, `pythonpath=["."]`) |
| Quick run command | `uv run pytest tests/test_agent_tools.py tests/test_agent_logging.py tests/test_agent_memory.py -x` |
| Full suite command | `uv run pytest tests/ -q` |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|---------------------|---------------|
| AGENT-01 (tool wiring) | `ingest_10x_tool`/`analyze_dataset_tool` handler functions correctly call the underlying Phase 1/2 functions and return valid `{"content": [...]}`-shaped dicts | unit | `uv run pytest tests/test_agent_tools.py -x` | ❌ Wave 0 |
| AGENT-01 (real loop, smoke) | A real `ClaudeSDKClient` session drives at least one plan→tool-call→observe cycle against the in-process server | integration/smoke, API-key-gated, excluded from default CI | `uv run pytest tests/test_agent_integration.py -m live_llm -x` (requires `ANTHROPIC_API_KEY`; not part of the fast default suite per Pitfall 4) | ❌ Wave 0 |
| AGENT-02 | `PostToolUse` hook writes one JSON-lines record per tool call with a verifiable result hash, for both success and error results | unit | `uv run pytest tests/test_agent_logging.py -x` | ❌ Wave 0 |
| AGENT-03 | `SessionMemory` records and recalls dataset references across multiple `record()`/`recent_datasets()` calls for the same `session_id`, isolated from other sessions | unit | `uv run pytest tests/test_agent_memory.py -x` | ❌ Wave 0 |

### Sampling Rate
- **Per task commit:** `uv run pytest tests/test_agent_tools.py tests/test_agent_logging.py tests/test_agent_memory.py -x` (fast tier only — no live API calls)
- **Per wave merge:** `uv run pytest tests/ -q` (fast tier; the `live_llm`-marked integration test is opt-in, run manually/nightly, not part of the standard gate — per Pitfall 4, forcing a live LLM call into every merge is slow, costs money, and is not the deterministic signal a merge gate needs)
- **Phase gate:** Full fast-tier suite green before `/gsd:verify-work`; at least one manual/nightly `live_llm` run demonstrated and its log output (`agent/logs/tool_calls.jsonl`) inspected as the actual AGENT-01/02 acceptance evidence, since no unit test can assert real Claude tool-selection behavior.

### Wave 0 Gaps
- [ ] `tests/test_agent_tools.py` — new file; covers AGENT-01's tool-handler correctness (call the `@tool`-decorated async functions directly, bypassing the SDK/LLM entirely)
- [ ] `tests/test_agent_logging.py` — new file; covers AGENT-02's hook-logging behavior in isolation (call `log_tool_call(...)` directly with synthetic args, assert on the resulting JSON-lines file content)
- [ ] `tests/test_agent_memory.py` — new file; covers AGENT-03's `SessionMemory` store in isolation (mirrors `tests/test_store.py`'s existing pattern for `DatasetStore`)
- [ ] `tests/test_agent_integration.py` — new file, `@pytest.mark.live_llm`; one smoke test driving a real `ClaudeSDKClient` turn, requires `ANTHROPIC_API_KEY`, not part of the fast default suite
- [ ] `pyproject.toml`: register `live_llm` as a custom pytest marker (`[tool.pytest.ini_options] markers = ["live_llm: requires a live Anthropic API key, excluded from fast/CI runs"]`) so the fast tier can reliably exclude it via `-m "not live_llm"`
- [ ] Framework install: `uv add claude-agent-sdk`

## Sources

### Primary (HIGH confidence)
- [Connect to external tools with MCP — Claude Agent SDK docs](https://code.claude.com/docs/en/agent-sdk/mcp) — fetched directly this session; transport types, tool naming, allowedTools, error/status handling for MCP servers, connection timing, Python code examples
- [Give Claude custom tools — Claude Agent SDK docs](https://code.claude.com/docs/en/agent-sdk/custom-tools) — fetched directly this session; `@tool` decorator shape, `create_sdk_mcp_server`, exact content-block/return-value schema, error-handling table (uncaught exception vs. composed `is_error`), confirmed `structuredContent` is dropped by the in-process Python decorator, optional-parameter workaround for dict schemas
- [How the agent loop works — Claude Agent SDK docs](https://code.claude.com/docs/en/agent-sdk/agent-loop) — fetched directly this session; full message-type lifecycle (`SystemMessage`/`AssistantMessage`/`UserMessage`/`StreamEvent`/`ResultMessage`), confirmed hook event list and table (`PreToolUse`, `PostToolUse`, `UserPromptSubmit`, `Stop`, `SubagentStart`/`SubagentStop`, `PreCompact`) with stated purposes, `ResultMessage` fields (`subtype`, `total_cost_usd`, `usage`, `num_turns`, `session_id`, `stop_reason`), session resume/fork/`session_store` mention, full worked Python code example
- PyPI package metadata, fetched directly this session: `claude-agent-sdk` current version `0.2.152`, `requires_python >=3.10`; `mcp` current version `2.1.1`
- `ingest/pipeline.py`, `ingest/store.py`, `analysis/pipeline.py`, `analysis/summary.py` (this repo) — read directly to determine exact function signatures/return shapes Phase 3's tool handlers must wrap
- `.planning/research/{STACK,ARCHITECTURE,PITFALLS,SUMMARY}.md` (this repo, pre-existing project-inception research) — read directly; already-established architectural decisions (coarse-grained tool calls, agent/analysis separation, tool-bypass/Pitfall 6 mitigation requirement, session-memory dataset-versioning requirement) this phase's research must be consistent with, not re-litigate

### Secondary (MEDIUM confidence)
- WebFetch of `code.claude.com/docs/en/agent-sdk/python` — summarized by an intermediate model rather than directly quoted for every claim; cross-checked against the `agent-loop` page's directly-fetched, quoted content where the two overlapped (message types, `ResultMessage` fields, hooks) and found consistent, but a few claims from this fetch specifically (e.g. `list_sessions`/`get_session_info`/`get_session_messages` helper functions, exact `ToolResultBlock` class name) were **not** independently re-confirmed against directly-quoted docs text this session — treat these specific API names as MEDIUM/LOW until verified against the installed package or the dedicated `/docs/en/agent-sdk/python` and `/docs/en/agent-sdk/hooks` pages at implementation time
- WebSearch on testing strategies for agentic-loop code — [pytest-claude-agent-sdk (amyodov) on GitHub](https://github.com/amyodov/pytest-claude-agent-sdk) and aggregator/blog sources on mocking LLM calls in tests; consistent theme across independent sources (mock/exclude the LLM in unit tests, test deterministic surrounding code, treat live-API tests as a separate tier) but no single official Anthropic-authored testing-pattern doc found

### Tertiary (LOW confidence)
- Exact `HookMatcher`/hook-callback Python signature (parameter names/types) — not directly quoted from any fetched page this session; Pattern 2's code example is a docs-consistent sketch, not a verified-correct signature (see Open Question 1)
- `pytest-claude-agent-sdk` as "the" recommended testing plugin — a single community (non-Anthropic) package found via WebSearch, not cross-verified against a second independent source or an official recommendation; the two-tier unit/integration split recommended in this document does not depend on adopting this specific plugin

## Metadata

**Confidence breakdown:**
- Standard stack (`claude-agent-sdk`/MCP core mechanics): HIGH — verified directly against current, officially-fetched documentation pages and live PyPI version metadata, not training-data recall
- Architecture (tool-wrapping pattern, hook-based logging, layered session memory): HIGH for the SDK-primitive pieces (directly sourced from official docs), MEDIUM for the specific composition choices (coarse-vs-fine tool granularity, exact `SessionMemory` schema) since these are original synthesis reasoned from this repo's own pre-existing research files plus the requirements' wording, not an externally documented "the" pattern
- Pitfalls (`structuredContent` drop, optional-schema-field workaround, uncaught-exception handling): HIGH — each directly quoted from official docs fetched this session
- Pitfalls (agentic-loop testing strategy): MEDIUM — consistent across multiple independent WebSearch sources but no single official Anthropic-authored reference found
- Hook callback exact signature: LOW — flagged explicitly in Open Questions, needs direct verification against `code.claude.com/docs/en/agent-sdk/hooks` or the installed package before implementation

**Research date:** 2026-09-04
**Valid until:** ~14 days (shorter than Phase 2's 30-day estimate — `claude-agent-sdk` has an observed weekly-ish release cadence per this repo's own earlier `STACK.md` note, and both the SDK and MCP spec are explicitly flagged as fast-moving; re-verify hook signatures and any newly-added `ClaudeAgentOptions` fields against the then-current installed version before planning execution if more than ~2 weeks elapse)
