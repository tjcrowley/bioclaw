"""Tests for agent.logging.log_tool_call -- the AGENT-02 verifiable-execution log.

Calls the function directly with synthetic tool-call data (bypassing the
SDK/LLM entirely, per Pitfall 4's two-tier testing strategy).
"""

import asyncio
import json

import pytest

from agent.logging import log_tool_call


def _read_lines(log_path):
    return log_path.read_text().splitlines()


def test_single_call_appends_one_line_with_expected_keys(tmp_path):
    log_path = tmp_path / "log.jsonl"

    asyncio.run(
        log_tool_call(
            "ingest_10x",
            {"path": "x", "name": "pilot"},
            {"dataset_id": "pilot@1"},
            False,
            log_path=log_path,
        )
    )

    lines = _read_lines(log_path)
    assert len(lines) == 1

    record = json.loads(lines[0])
    assert set(record.keys()) >= {
        "ts",
        "tool_name",
        "tool_input",
        "is_error",
        "result_sha256",
        "result_preview",
    }
    assert record["tool_name"] == "ingest_10x"
    assert record["is_error"] is False


def test_second_call_appends_without_truncating_first(tmp_path):
    log_path = tmp_path / "log.jsonl"

    asyncio.run(
        log_tool_call(
            "ingest_10x",
            {"path": "x", "name": "pilot"},
            {"dataset_id": "pilot@1"},
            False,
            log_path=log_path,
        )
    )
    first_line = _read_lines(log_path)[0]

    asyncio.run(
        log_tool_call(
            "run_qc",
            {"dataset_id": "pilot@1"},
            {"n_cells": 100},
            False,
            log_path=log_path,
        )
    )

    lines = _read_lines(log_path)
    assert len(lines) == 2
    assert lines[0] == first_line

    second_record = json.loads(lines[1])
    assert second_record["tool_name"] == "run_qc"


def test_error_call_still_writes_record_with_is_error_true(tmp_path):
    log_path = tmp_path / "log.jsonl"

    asyncio.run(
        log_tool_call(
            "ingest_10x",
            {"path": "missing", "name": "pilot"},
            "RuntimeError: dataset not found",
            True,
            log_path=log_path,
        )
    )

    lines = _read_lines(log_path)
    assert len(lines) == 1

    record = json.loads(lines[0])
    assert record["is_error"] is True
    assert record["result_sha256"]


def test_result_sha256_is_deterministic(tmp_path):
    log_path = tmp_path / "log.jsonl"

    asyncio.run(
        log_tool_call(
            "run_qc",
            {"dataset_id": "pilot@1"},
            {"n_cells": 100, "mito_pct": 3.5},
            False,
            log_path=log_path,
        )
    )
    asyncio.run(
        log_tool_call(
            "run_qc",
            {"dataset_id": "pilot@1"},
            {"n_cells": 100, "mito_pct": 3.5},
            False,
            log_path=log_path,
        )
    )

    lines = _read_lines(log_path)
    assert len(lines) == 2

    hash_1 = json.loads(lines[0])["result_sha256"]
    hash_2 = json.loads(lines[1])["result_sha256"]
    assert hash_1 == hash_2


def test_parent_directory_created_automatically(tmp_path):
    log_path = tmp_path / "nested" / "dir" / "log.jsonl"
    assert not log_path.parent.exists()

    asyncio.run(
        log_tool_call(
            "ingest_10x",
            {"path": "x"},
            {"dataset_id": "pilot@1"},
            False,
            log_path=log_path,
        )
    )

    assert log_path.exists()
    assert len(_read_lines(log_path)) == 1
