"""AGENT-01 tool-calling surface: thin `@tool`-decorated async handlers
wrapping Phase 1/2's `ingest_10x`/`analyze` entrypoints verbatim -- no
reimplemented pipeline logic.

Per 03-RESEARCH.md Pitfall 1, the in-process `@tool` decorator only
forwards `content`/`is_error` from a handler's return dict --
`structuredContent` is silently dropped -- so both handlers here serialize
their bounded-dataclass result as a single JSON `text` content block
instead.

Per 03-RESEARCH.md Pitfall 2, `analyze_dataset_tool`'s optional `version`
parameter is intentionally omitted from the tool's dict schema (every key
in a dict schema is treated as required) and read via `args.get("version")`
in the handler body.

Per 03-RESEARCH.md Pitfall 3, neither handler catches exceptions raised by
`ingest_10x`/`analyze` (e.g. `KeyError` from an unknown dataset name,
`RuntimeError` from a counts-integrity failure) -- the SDK's in-process MCP
server converts an uncaught handler exception into an error tool result at
dispatch time, so letting it propagate is the correct default.
"""

import json
import os
from typing import Any

from claude_agent_sdk import tool

from analysis.pipeline import analyze
from ingest.pipeline import ingest_10x

# Module-level constant, set once at import time (overridable via the
# BIOCLAW_STORE_ROOT env var, or directly in tests via
# `monkeypatch.setattr(agent.tools, "STORE_ROOT", ...)`). Deliberately never
# read from LLM-controlled `args` -- the agent cannot redirect where
# datasets get written by asking for it in a prompt.
STORE_ROOT = os.environ.get("BIOCLAW_STORE_ROOT", "data")


@tool(
    "ingest_10x",
    "Ingest a 10x Genomics .mtx directory or .h5 file into the versioned "
    "dataset store, running standard QC. Returns the new dataset_id.",
    {"path": str, "name": str},
)
async def ingest_10x_tool(args: dict[str, Any]) -> dict[str, Any]:
    dataset_id = ingest_10x(args["path"], args["name"], store_root=STORE_ROOT)
    return {
        "content": [{"type": "text", "text": json.dumps({"dataset_id": dataset_id})}],
        "is_error": False,
    }


@tool(
    "analyze_dataset",
    "Run preprocess -> cluster -> (optional) differential expression on a "
    "named/versioned dataset from the store. Optionally pass 'version' "
    "(int) to analyze a specific version instead of the latest. Returns "
    "a bounded summary, never raw matrices.",
    {"name": str},  # 'version' intentionally omitted -- optional, see Pitfall 2
)
async def analyze_dataset_tool(args: dict[str, Any]) -> dict[str, Any]:
    version = args.get("version")
    new_id, summary = analyze(args["name"], version=version, store_root=STORE_ROOT)
    return {
        "content": [
            {"type": "text", "text": json.dumps({"dataset_id": new_id, **summary})}
        ],
        "is_error": False,
    }
