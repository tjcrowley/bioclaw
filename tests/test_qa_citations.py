"""Unit tests for qa/citations.py (QA-02).

Covers parse_citation_ids() (pure regex extraction) and verify_answer_citations()
(JSONL log resolution). No LLM required -- these are the deterministic pieces
that Wave 1/2 of Phase 6 depend on for hallucinated-citation detection.

The synthetic JSONL records match agent/logging.py's schema exactly:
    {"ts", "tool_name", "tool_input", "is_error", "result_sha256",
     "result_preview"}
so any change to that schema breaks these tests loudly rather than silently
skewing citation resolution downstream.
"""

import json

from qa.citations import CITATION_RE, parse_citation_ids, verify_answer_citations


def _write_log(log_path, records):
    log_path.write_text("\n".join(json.dumps(r) for r in records) + "\n")


def _make_record(tool_name: str, sha_prefix: str, **overrides) -> dict:
    """Build a JSONL record matching agent/logging.py's schema exactly.
    sha_prefix is the first 12 hex chars; the remaining 52 chars are filled
    with '0' so the full result_sha256 is a valid 64-char hex string."""
    record = {
        "ts": 1.0,
        "tool_name": tool_name,
        "tool_input": {},
        "is_error": False,
        "result_sha256": sha_prefix + "0" * (64 - len(sha_prefix)),
        "result_preview": "...",
    }
    record.update(overrides)
    return record


def test_parse_citation_ids_finds_tags():
    answer = (
        "The dataset has 1200 cells [ref:mcp__bioclaw__ingest_10x:a3f9c2b10d44] "
        "with a leiden clustering of 5 groups "
        "[ref:mcp__bioclaw__analyze_dataset:b7e0d1c22e55]."
    )
    tags = parse_citation_ids(answer)
    assert tags == [
        ("mcp__bioclaw__ingest_10x", "a3f9c2b10d44"),
        ("mcp__bioclaw__analyze_dataset", "b7e0d1c22e55"),
    ]


def test_parse_citation_ids_empty():
    assert parse_citation_ids("No citations here.") == []
    assert parse_citation_ids("") == []


def test_parse_citation_ids_ignores_malformed():
    # Missing sha prefix, uppercase hex, wrong length -- none should match.
    answer = (
        "Bad ones: [ref:tool] and [ref:tool:ABCDEF012345] and "
        "[ref:tool:abcdef01234] (11 chars) and [ref:tool:abcdef0123456] (13 chars)."
    )
    assert parse_citation_ids(answer) == []
    # Sanity: the regex itself rejects each of these individually.
    assert CITATION_RE.search("[ref:tool]") is None
    assert CITATION_RE.search("[ref:tool:ABCDEF012345]") is None


def test_verify_answer_citations_resolves_match(tmp_path):
    log_path = tmp_path / "tool_calls.jsonl"
    _write_log(
        log_path,
        [_make_record("mcp__bioclaw__analyze_dataset", "a3f9c2b10d44")],
    )
    answer = "Result [ref:mcp__bioclaw__analyze_dataset:a3f9c2b10d44] shows 5 clusters."
    results = verify_answer_citations(answer, log_path)
    assert len(results) == 1
    tool_name, sha_prefix, record = results[0]
    assert tool_name == "mcp__bioclaw__analyze_dataset"
    assert sha_prefix == "a3f9c2b10d44"
    assert record is not None
    assert record["tool_name"] == "mcp__bioclaw__analyze_dataset"
    assert record["result_sha256"].startswith("a3f9c2b10d44")


def test_verify_answer_citations_unresolved(tmp_path):
    log_path = tmp_path / "tool_calls.jsonl"
    _write_log(
        log_path,
        [_make_record("mcp__bioclaw__analyze_dataset", "aaaaaaaaaaaa")],
    )
    # Same tool, but a sha prefix that no record starts with -- hallucinated.
    answer = "Fake [ref:mcp__bioclaw__analyze_dataset:deadbeefcafe]."
    results = verify_answer_citations(answer, log_path)
    assert len(results) == 1
    tool_name, sha_prefix, record = results[0]
    assert tool_name == "mcp__bioclaw__analyze_dataset"
    assert sha_prefix == "deadbeefcafe"
    assert record is None


def test_verify_answer_citations_empty_log(tmp_path):
    log_path = tmp_path / "does_not_exist.jsonl"
    answer = (
        "Two tags [ref:mcp__bioclaw__ingest_10x:a3f9c2b10d44] and "
        "[ref:mcp__bioclaw__analyze_dataset:b7e0d1c22e55]."
    )
    results = verify_answer_citations(answer, log_path)
    assert len(results) == 2
    for _, _, record in results:
        assert record is None


def test_verify_answer_citations_empty_answer(tmp_path):
    log_path = tmp_path / "tool_calls.jsonl"
    _write_log(
        log_path,
        [_make_record("mcp__bioclaw__analyze_dataset", "a3f9c2b10d44")],
    )
    assert verify_answer_citations("No citations here.", log_path) == []
    assert verify_answer_citations("", log_path) == []
