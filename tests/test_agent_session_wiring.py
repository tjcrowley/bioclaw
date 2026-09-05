"""Tests for agent/session.py's wiring logic -- build_options(),
record_dataset_reference(), and _recall_preamble() -- unit-tested without any
live API call (fast tier). The one live_llm smoke test that exercises a real
ClaudeSDKClient session lives in tests/test_agent_integration.py.

Per 03-RESEARCH.md Open Question 1, the installed claude_agent_sdk package's
PostToolUse hook callback signature is `(input_data: PostToolUseHookInput,
tool_use_id: str | None, context: HookContext) -> Awaitable[HookJSONOutput]`
(verified via `inspect.signature(claude_agent_sdk.HookMatcher)` /
`claude_agent_sdk.types.PostToolUseHookInput.__annotations__` against the
installed package) -- `record_dataset_reference()`'s returned callable and
`build_options()`'s internal log hook both match this shape, not the
plan sketch's `(tool_name, tool_input, tool_response, is_error, **_)`
positional-kwargs shape (which does not match the installed SDK version).
"""

import asyncio
import json

from claude_agent_sdk import ClaudeAgentOptions, HookMatcher

from agent.memory import SessionMemory
from agent.session import (
    _recall_preamble,
    build_options,
    record_dataset_reference,
)

CONTEXT = {"signal": None}


def _post_tool_use_input(tool_name, tool_response, tool_input=None):
    return {
        "session_id": "sess-1",
        "transcript_path": "/tmp/transcript.json",
        "cwd": "/tmp",
        "hook_event_name": "PostToolUse",
        "tool_name": tool_name,
        "tool_input": tool_input or {},
        "tool_response": tool_response,
        "tool_use_id": "tool-use-1",
    }


def test_build_options_returns_claude_agent_options(tmp_path):
    mem = SessionMemory(root=tmp_path / "memory.sqlite")
    options = build_options(mem, "sess-1", log_path=tmp_path / "log.jsonl")

    assert isinstance(options, ClaudeAgentOptions)
    assert options.mcp_servers["bioclaw"] is not None
    assert "mcp__bioclaw__*" in options.allowed_tools
    assert options.hooks is not None
    post_tool_use = options.hooks["PostToolUse"]
    assert len(post_tool_use) > 0
    assert all(isinstance(m, HookMatcher) for m in post_tool_use)
    assert any(len(m.hooks) > 0 for m in post_tool_use)


def test_record_dataset_reference_records_dataset_id_from_valid_result(tmp_path):
    mem = SessionMemory(root=tmp_path / "memory.sqlite")
    hook = record_dataset_reference(mem, "sess-1")

    # Real tool_response shape (verified live 2026-09-05): the handler's
    # `content` array itself, not the {"content": [...], "is_error": ...}
    # dict agent/tools.py's handlers return -- the CLI unwraps it.
    tool_response = [
        {
            "type": "text",
            "text": json.dumps({"dataset_id": "pilot@1", "preprocess": {}}),
        }
    ]
    input_data = _post_tool_use_input("ingest_10x", tool_response)

    asyncio.run(hook(input_data, "tool-use-1", CONTEXT))

    assert "pilot@1" in mem.recent_datasets("sess-1")


def test_record_dataset_reference_ignores_non_json_text(tmp_path):
    mem = SessionMemory(root=tmp_path / "memory.sqlite")
    hook = record_dataset_reference(mem, "sess-1")

    tool_response = [{"type": "text", "text": "RuntimeError: dataset not found"}]
    input_data = _post_tool_use_input("ingest_10x", tool_response)

    asyncio.run(hook(input_data, "tool-use-1", CONTEXT))

    assert mem.recent_datasets("sess-1") == []


def test_record_dataset_reference_ignores_json_without_dataset_id(tmp_path):
    mem = SessionMemory(root=tmp_path / "memory.sqlite")
    hook = record_dataset_reference(mem, "sess-1")

    tool_response = [{"type": "text", "text": json.dumps({"n_cells": 100})}]
    input_data = _post_tool_use_input("ingest_10x", tool_response)

    asyncio.run(hook(input_data, "tool-use-1", CONTEXT))

    assert mem.recent_datasets("sess-1") == []


def test_record_dataset_reference_does_not_raise_on_malformed_response(tmp_path):
    mem = SessionMemory(root=tmp_path / "memory.sqlite")
    hook = record_dataset_reference(mem, "sess-1")

    # Not a content array at all -- must not crash the hook chain.
    input_data = _post_tool_use_input("ingest_10x", {"is_error": False})

    asyncio.run(hook(input_data, "tool-use-1", CONTEXT))

    assert mem.recent_datasets("sess-1") == []


def test_record_dataset_reference_does_not_raise_on_empty_content_list(tmp_path):
    mem = SessionMemory(root=tmp_path / "memory.sqlite")
    hook = record_dataset_reference(mem, "sess-1")

    input_data = _post_tool_use_input("ingest_10x", [])

    asyncio.run(hook(input_data, "tool-use-1", CONTEXT))

    assert mem.recent_datasets("sess-1") == []


def test_recall_preamble_empty_when_nothing_recorded(tmp_path):
    mem = SessionMemory(root=tmp_path / "memory.sqlite")

    assert _recall_preamble(mem, "sess-1") == ""


def test_recall_preamble_nonempty_after_record(tmp_path):
    mem = SessionMemory(root=tmp_path / "memory.sqlite")
    mem.record("sess-1", "pilot@1", note="ingested")

    preamble = _recall_preamble(mem, "sess-1")

    assert preamble != ""
    assert "pilot@1" in preamble
