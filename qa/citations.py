"""Citation parsing and verification for QA-02.

parse_citation_ids(answer_text) -> list[tuple[str, str]]
    Returns [(tool_name, sha256_prefix), ...] for every [ref:TOOL_NAME:SHA256_PREFIX] tag.

verify_answer_citations(answer_text, log_path) -> list[tuple[str, str, dict | None]]
    For each citation tag, look up the matching JSONL record.
    Returns [(tool_name, sha_prefix, record_or_None), ...].
    record is None if no log entry matches (hallucinated citation).
"""
import json
import re
from pathlib import Path

CITATION_RE = re.compile(r'\[ref:([^:\]]+):([0-9a-f]{12})\]')


def parse_citation_ids(answer_text: str) -> list[tuple[str, str]]:
    return CITATION_RE.findall(answer_text)


def verify_answer_citations(
    answer_text: str,
    log_path: Path,
) -> list[tuple[str, str, dict | None]]:
    tags = parse_citation_ids(answer_text)
    records: list[dict] = []
    if log_path.exists():
        for line in log_path.read_text().splitlines():
            line = line.strip()
            if line:
                try:
                    records.append(json.loads(line))
                except json.JSONDecodeError:
                    pass
    results = []
    for tool_name, sha_prefix in tags:
        match = next(
            (r for r in records
             if r.get("tool_name") == tool_name
             and r.get("result_sha256", "").startswith(sha_prefix)),
            None,
        )
        results.append((tool_name, sha_prefix, match))
    return results
