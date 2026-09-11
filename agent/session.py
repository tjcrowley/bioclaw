"""Wave 2 wiring: the `ClaudeSDKClient`-driven run-loop entrypoint that ties
Wave 1's three independent modules together into one working agent session.

- `agent/server.py`'s `bioclaw_server` supplies the tool surface (AGENT-01).
- `agent/logging.py`'s `log_tool_call` is wired in as a `PostToolUse` hook,
  so every tool call is logged as a structural side effect of the call
  itself, not an opt-in the agent could skip (AGENT-02).
- `agent/memory.py`'s `SessionMemory` is written to by another `PostToolUse`
  hook (`record_dataset_reference`) and read back by `_recall_preamble`,
  which is prepended to every turn's prompt before it is sent to the SDK.
  This read-back half is what makes AGENT-03 an observable, later-turn
  behavior rather than a database row nobody consults (closes the
  plan-checker's write-only-memory blocker, 2026-09-05).

Per 03-RESEARCH.md Open Question 1, the exact `PostToolUse` hook callback
shape was LOW confidence at plan-writing time. Verified at implementation
time against the installed `claude_agent_sdk` package (`inspect.signature`
against `claude_agent_sdk.HookMatcher`/`claude_agent_sdk.types.
PostToolUseHookInput.__annotations__`): a hook is `async def _hook(input_data,
tool_use_id, context)`, where `input_data` is a `PostToolUseHookInput`
TypedDict (keys include `tool_name`, `tool_input`, `tool_response`), NOT the
plan sketch's `(tool_name, tool_input, tool_response, is_error, **_)`
positional-kwargs shape -- `is_error` is not a top-level `PostToolUseHookInput`
key, it lives inside `tool_response` itself (the same
`{"content": [...], "is_error": bool}` dict `agent/tools.py`'s handlers
return). `ClaudeAgentOptions.hooks["PostToolUse"]` is a `list[HookMatcher]`,
not a bare list of callables -- each hook list must be wrapped in a
`HookMatcher(hooks=[...])`.
"""

import json
import uuid
from pathlib import Path
from typing import Any

from claude_agent_sdk import (
    AssistantMessage,
    ClaudeAgentOptions,
    ClaudeSDKClient,
    HookMatcher,
    ResultMessage,
    TextBlock,
)

from agent.logging import DEFAULT_LOG_PATH, log_tool_call
from agent.memory import SessionMemory
from agent.server import bioclaw_server

SYSTEM_PROMPT = (
    "You are a bioinformatics research assistant for single-cell "
    "transcriptomics data. Use the available tools to ingest and analyze "
    "datasets -- never fabricate a dataset_id or analysis result. Always "
    "cite the specific dataset_id and tool result you are referencing "
    "when reporting findings."
)


def _tool_response_is_error(tool_response: Any) -> bool:
    if isinstance(tool_response, dict):
        return bool(tool_response.get("is_error"))
    return False


def _make_log_hook(log_path: Path):
    async def _hook(input_data, tool_use_id, context):
        tool_response = input_data.get("tool_response")
        await log_tool_call(
            input_data.get("tool_name", ""),
            input_data.get("tool_input", {}),
            tool_response,
            _tool_response_is_error(tool_response),
            log_path=log_path,
        )
        return {}

    return _hook


def record_dataset_reference(session_memory: SessionMemory, session_id: str):
    """Returns a `PostToolUse` hook callback that parses a `dataset_id` out
    of a real tool result's JSON text content and records it in
    `session_memory` -- the write half of AGENT-03. A tool call that
    produced no dataset reference (or failed) is simply not memory-worthy;
    this must never raise or otherwise crash the hook chain.

    Verified against a live run (2026-09-05): for an in-process MCP tool,
    `input_data["tool_response"]` is the handler's `content` array itself
    (e.g. `[{"type": "text", "text": "..."}]`) -- the CLI strips the
    `{"content": [...], "is_error": ...}` wrapper `agent/tools.py`'s
    handlers actually return before it reaches this hook, and `is_error`
    is not passed through separately. So there is no reliable is_error
    signal to check here; a failed/malformed result is instead filtered
    out naturally below when it fails to parse as `{"dataset_id": ...}`
    JSON."""

    async def _hook(input_data, tool_use_id, context):
        tool_name = input_data.get("tool_name", "")
        tool_response = input_data.get("tool_response")
        try:
            text = tool_response[0]["text"]
            payload = json.loads(text)
            dataset_id = payload.get("dataset_id")
        except (KeyError, IndexError, TypeError, ValueError):
            return {}
        if dataset_id:
            note = f"{tool_name}: dataset_id={dataset_id}"
            session_memory.record(session_id, dataset_id, note=note)
        return {}

    return _hook


def _recall_preamble(session_memory: SessionMemory, session_id: str) -> str:
    """Builds a short context preamble from dataset references recorded
    earlier in this session, so a later turn can recall them without
    depending on the SDK's own transcript retention surviving automatic
    context compaction (03-RESEARCH.md Pattern 3). Called fresh before
    every turn in run_session() -- this is the read-back half of AGENT-03;
    record_dataset_reference() above is the write half. Returns "" when
    nothing has been recorded yet (do not inject an empty/misleading
    context block into a session's first turn)."""
    datasets = session_memory.recent_datasets(session_id)
    if not datasets:
        return ""
    return (
        "(Session context: dataset(s) referenced earlier in this "
        f"conversation, most recent first: {', '.join(datasets)}.)\n\n"
    )


def build_options(
    session_memory: SessionMemory,
    session_id: str,
    log_path: Path = DEFAULT_LOG_PATH,
    system_prompt: str = SYSTEM_PROMPT,
) -> ClaudeAgentOptions:
    return ClaudeAgentOptions(
        mcp_servers={"bioclaw": bioclaw_server},
        allowed_tools=["mcp__bioclaw__*"],
        system_prompt=system_prompt,
        hooks={
            "PostToolUse": [
                HookMatcher(
                    hooks=[
                        _make_log_hook(log_path),
                        record_dataset_reference(session_memory, session_id),
                    ]
                )
            ]
        },
        max_turns=30,
    )


async def run_session(
    prompts: str | list[str],
    session_memory: SessionMemory | None = None,
    session_id: str | None = None,
    log_path: Path = DEFAULT_LOG_PATH,
    system_prompt: str = SYSTEM_PROMPT,
) -> tuple[list[str], str]:
    """Runs one or more turns of a Claude Agent SDK session against the
    bioclaw tool server, within a single ClaudeSDKClient context.
    Returns (final_texts, session_id) -- one entry in final_texts per
    prompt, in order. session_id is our own process-local identifier
    (not the SDK's internal session id) used to key SessionMemory --
    stable across all turns in this call, and reusable across separate
    run_session() calls to extend the same logical session further,
    without depending on the SDK's own session_id being available inside
    a hook callback (unconfirmed, see 03-RESEARCH.md Open Question 1).

    Before each turn (including the first), _recall_preamble() is
    prepended to the prompt actually sent to the SDK -- on turn 1 this is
    "" (nothing recorded yet); on turn 2+ it surfaces any dataset_id
    recorded via record_dataset_reference() during an earlier turn in
    this same call. This is what makes AGENT-03 an observable behavior
    (a later turn's answer reflects an earlier turn's tool result), not
    just a database row nobody reads.
    """
    if isinstance(prompts, str):
        prompts = [prompts]

    session_memory = session_memory or SessionMemory()
    session_id = session_id or str(uuid.uuid4())
    options = build_options(
        session_memory,
        session_id,
        log_path=log_path,
        system_prompt=system_prompt,
    )

    final_texts: list[str] = []
    async with ClaudeSDKClient(options=options) as client:
        for prompt in prompts:
            preamble = _recall_preamble(session_memory, session_id)
            await client.query(preamble + prompt)
            final_text = ""
            async for message in client.receive_response():
                if isinstance(message, AssistantMessage):
                    for block in message.content:
                        if isinstance(block, TextBlock):
                            final_text += block.text
                if isinstance(message, ResultMessage) and message.subtype == "success":
                    final_text = message.result or final_text
            final_texts.append(final_text)

    return final_texts, session_id
