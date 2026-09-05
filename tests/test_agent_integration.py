"""Live end-to-end smoke test for agent/session.py's run_session(): a real
ClaudeSDKClient session ingesting a dataset via a real tool call, that call
being logged, and a SECOND turn recalling the resulting dataset_id with no
restatement by the caller.

Marked @pytest.mark.live_llm and skipped when ANTHROPIC_API_KEY is unset --
this test drives real model calls against the in-process bioclaw MCP server
and cannot be faked with a mock (03-VALIDATION.md's Phase Gate). The fast
tier (tests/test_agent_session_wiring.py) covers the wiring logic itself
without any live API call, per Pitfall 4's two-tier testing strategy.
"""

import asyncio
import json
import os

import pytest

import agent.tools as agent_tools
from agent.memory import SessionMemory
from agent.session import run_session

pytestmark = pytest.mark.live_llm


@pytest.mark.skipif(
    not os.environ.get("ANTHROPIC_API_KEY"), reason="requires ANTHROPIC_API_KEY"
)
def test_run_session_two_turns_ingest_then_recall(tmp_path, tiny_mtx_dir, monkeypatch):
    monkeypatch.setattr(agent_tools, "STORE_ROOT", str(tmp_path / "store"))

    log_path = tmp_path / "tool_calls.jsonl"
    mem = SessionMemory(root=tmp_path / "memory.sqlite")

    texts, sid = asyncio.run(
        run_session(
            [
                f"Ingest the 10x dataset at {tiny_mtx_dir} and name it 'pilot'.",
                "What dataset id did we just discuss? Answer with only the "
                "dataset_id, nothing else.",
            ],
            session_memory=mem,
            log_path=log_path,
        )
    )

    # AGENT-02: a real tool call occurred and was logged, not simulated text.
    assert log_path.exists()
    records = [json.loads(line) for line in log_path.read_text().splitlines()]
    assert any(r["tool_name"] == "ingest_10x" for r in records)

    # AGENT-03 (write half): the dataset reference was recorded.
    recent = mem.recent_datasets(sid)
    assert recent

    # AGENT-01 + AGENT-03 (read-back half): turn 2's answer, with no
    # dataset_id restated by the caller, reflects turn 1's tool result.
    assert len(texts) == 2
    assert recent[0] in texts[1]
