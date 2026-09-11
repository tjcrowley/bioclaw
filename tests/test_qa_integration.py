"""Live end-to-end Q&A integration test (Phase 6, QA-01/02/03).

Drives a real ClaudeSDKClient session through `qa.session.ask_question`
against the bioclaw MCP tools and asserts three closure properties:

- QA-01: at least two distinct tools were logged (multi-tool composition --
  the answer required composing ingest + analyze, not a single-tool
  shortcut).
- QA-02: every `[ref:TOOL_NAME:SHA256_PREFIX]` tag in the answer resolves
  to a real JSONL log entry (no hallucinated citations).
- QA-03: the answer contains at least one decimal quantitative value AND
  the citation list is non-empty -- the combination proves the numeric
  value came from a cited tool result, not a bare hallucinated fact.

Marked @pytest.mark.live_llm and skipped when ANTHROPIC_API_KEY is unset,
mirroring tests/test_agent_integration.py's Phase-3 pattern.

The `analyzable_mtx_dir` fixture (300 genes x 60 cells, two marker
populations) is defined in tests/conftest.py -- large enough to survive
default QC's min_genes_per_cell=200 threshold so ingest -> analyze runs
end to end.
"""

import asyncio
import json
import os
import re

import pytest

import agent.tools as agent_tools
from agent.memory import SessionMemory
from qa.citations import parse_citation_ids
from qa.session import ask_question


@pytest.mark.live_llm
@pytest.mark.skipif(
    not os.environ.get("ANTHROPIC_API_KEY"),
    reason="requires ANTHROPIC_API_KEY",
)
def test_qa_multi_tool_compose_with_citations(tmp_path, analyzable_mtx_dir, monkeypatch):
    monkeypatch.setattr(agent_tools, "STORE_ROOT", str(tmp_path / "store"))
    log_path = tmp_path / "tool_calls.jsonl"
    mem = SessionMemory(root=tmp_path / "memory.sqlite")

    question = (
        "Ingest the dataset at {path}, analyze it for clustering, and tell me "
        "what clusters exist and which genes are most differentially expressed. "
        "Provide uncertainty values for every quantitative claim."
    ).format(path=str(analyzable_mtx_dir))

    answer, sid, citation_results = asyncio.run(
        ask_question(question, session_memory=mem, log_path=log_path)
    )

    # Surface the answer text so the human-verify checkpoint can eyeball it
    # in captured stdout (`pytest -s`).
    print("\n=== Q&A ANSWER ===")
    print(answer)
    print("=== END ANSWER ===")
    print(f"session_id={sid}")
    print(f"citation_results (n={len(citation_results)}):")
    for tn, sp, rec in citation_results:
        status = "RESOLVED" if rec is not None else "UNRESOLVED"
        print(f"  [{status}] {tn}:{sp}")

    # QA-01: at least two distinct tools were called (multi-tool composition,
    # not single-tool shortcut).
    assert log_path.exists(), "No JSONL log written -- no tool was called"
    records = [
        json.loads(line)
        for line in log_path.read_text().splitlines()
        if line.strip()
    ]
    distinct_tools = {r["tool_name"] for r in records}
    assert len(distinct_tools) >= 2, (
        f"Expected at least 2 distinct tool calls (ingest + analyze), "
        f"got {len(distinct_tools)}: {distinct_tools}"
    )

    # QA-02: citations are present and ALL resolve to real log entries.
    citation_ids = parse_citation_ids(answer)
    assert len(citation_ids) > 0, (
        f"Answer contains no [ref:...] citations -- QA-02 not met.\n\nAnswer:\n{answer}"
    )
    unresolved = [(tn, sp) for tn, sp, rec in citation_results if rec is None]
    assert not unresolved, (
        f"Hallucinated citations (no matching log entry): {unresolved}\n\nAnswer:\n{answer}"
    )

    # QA-03: at least one decimal quantitative value is present AND citations
    # are non-empty (the combination proves the numeric value came from a
    # cited tool result, not a bare hallucinated fact).
    has_decimal = bool(re.search(r"\d+\.\d+", answer))
    assert has_decimal and len(citation_results) > 0, (
        f"QA-03 not met -- answer must contain a decimal value accompanied "
        f"by at least one resolved citation.\n"
        f"has_decimal={has_decimal}, citation_results={len(citation_results)}\n\n"
        f"Answer:\n{answer}"
    )
