"""AGENT-02 verifiable-execution log.

`log_tool_call` writes one JSON-lines record per tool call (name, input,
result hash, error flag, timestamp) to an append-only log file. This is the
audit trail that lets a researcher (or a test) prove a result came from a
real tool invocation, not simulated text.

Declared `async` to match the expected shape of an SDK `PostToolUse` hook
callback (per 03-RESEARCH.md Open Question 1, the exact parameter
names/signature are LOW confidence and must be verified against the
installed `claude_agent_sdk` package before Wave 2 wires this into
`ClaudeAgentOptions(hooks=...)`). This plan's tests call the function
directly with synthetic args, bypassing the SDK/LLM entirely.
"""

import hashlib
import json
import time
from pathlib import Path
from typing import Any

DEFAULT_LOG_PATH = Path("agent/logs/tool_calls.jsonl")


async def log_tool_call(
    tool_name: str,
    tool_input: dict[str, Any],
    tool_response: Any,
    is_error: bool,
    log_path: Path = DEFAULT_LOG_PATH,
) -> None:
    """Appends one JSON-lines record per tool call. `tool_response` may be
    any JSON-serializable value (a dict, or a raw string for an error
    message) -- serialized with `default=str` so non-JSON-native types
    (e.g. a raised exception object) don't crash logging itself."""
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
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("a") as f:
        f.write(json.dumps(record) + "\n")
