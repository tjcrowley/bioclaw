"""One-shot diagnostic for the test_run_session_two_turns_ingest_then_recall
failure (log_path never created -> no PostToolUse hook ever fired).

Drives the same two-turn session as the failing test, but streams every raw
message (SystemMessage init -- which lists connected MCP servers/tools --
plus every ToolUseBlock/ToolResultBlock/TextBlock) instead of only reading
the final text, so we can see exactly where it breaks:
  - SystemMessage shows no "bioclaw" server / no ingest_10x tool -> MCP
    handshake/registration problem.
  - SystemMessage looks fine but no ToolUseBlock ever appears -> the model
    itself never attempted a tool call.
  - ToolUseBlock appears but no ToolResultBlock / hook fires -> permission
    or hook-dispatch problem.

Run locally (never paste the key into chat):
    cd bioclaw && ANTHROPIC_API_KEY=... uv run python3 -m scripts.debug_live_session

Paste the full stdout back -- it contains no secrets.
"""

import asyncio
import gzip
import os
import shutil
import sys
import tempfile
from pathlib import Path

from claude_agent_sdk import (
    AssistantMessage,
    ClaudeSDKClient,
    ResultMessage,
    SystemMessage,
    TextBlock,
    ToolResultBlock,
    ToolUseBlock,
)

import agent.tools as agent_tools
from agent.memory import SessionMemory
from agent.session import _recall_preamble, build_options

# Build a tiny throwaway 10x MEX dir inline so this script has no fixture
# dependency on pytest/conftest.py.


def _make_tiny_mtx_dir(root: Path) -> Path:
    d = root / "tiny_mtx"
    d.mkdir(parents=True)
    with gzip.open(d / "matrix.mtx.gz", "wt") as f:
        f.write("%%MatrixMarket matrix coordinate integer general\n%\n2 2 2\n1 1 3\n2 2 5\n")
    with gzip.open(d / "barcodes.tsv.gz", "wt") as f:
        f.write("AAACCTGAGAAACCAT-1\nAAACCTGAGAAACCGC-1\n")
    with gzip.open(d / "features.tsv.gz", "wt") as f:
        f.write("ENSG1\tGENE1\tGene Expression\nENSG2\tGENE2\tGene Expression\n")
    return d


async def main() -> None:
    tmp = Path(tempfile.mkdtemp(prefix="bioclaw-debug-"))
    print(f"[debug] scratch dir: {tmp}")
    try:
        tiny_mtx_dir = _make_tiny_mtx_dir(tmp)
        agent_tools.STORE_ROOT = str(tmp / "store")

        log_path = tmp / "tool_calls.jsonl"
        mem = SessionMemory(root=tmp / "memory.sqlite")
        session_id = "debug-session"
        options = build_options(mem, session_id, log_path=log_path)

        prompts = [
            f"Ingest the 10x dataset at {tiny_mtx_dir} and name it 'pilot'.",
            "What dataset id did we just discuss? Answer with only the "
            "dataset_id, nothing else.",
        ]

        async with ClaudeSDKClient(options=options) as client:
            for i, prompt in enumerate(prompts, 1):
                preamble = _recall_preamble(mem, session_id)
                full_prompt = preamble + prompt
                print(f"\n=== turn {i}: sending: {full_prompt!r} ===")
                await client.query(full_prompt)
                async for message in client.receive_response():
                    print(f"[msg] {type(message).__name__}: {message!r}")
                    if isinstance(message, SystemMessage):
                        print(f"    subtype={message.subtype} data={message.data}")
                    if isinstance(message, AssistantMessage):
                        for block in message.content:
                            print(f"    block: {type(block).__name__}")
                            if isinstance(block, TextBlock):
                                print(f"      text={block.text!r}")
                            if isinstance(block, ToolUseBlock):
                                print(f"      tool={block.name} input={block.input}")
                            if isinstance(block, ToolResultBlock):
                                print(f"      result={block.content!r} is_error={block.is_error}")
                    if isinstance(message, ResultMessage):
                        print(f"    subtype={message.subtype} result={message.result!r}")

        print(f"\n[debug] log_path exists: {log_path.exists()}")
        if log_path.exists():
            print(log_path.read_text())
        print(f"[debug] recorded datasets: {mem.recent_datasets(session_id)}")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("ANTHROPIC_API_KEY not set", file=sys.stderr)
        sys.exit(1)
    asyncio.run(main())
