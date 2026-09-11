"""Q&A session entry point (Phase 6, QA-01/02/03). Implemented in Plan 06-03."""
from pathlib import Path
from agent.memory import SessionMemory

QA_SYSTEM_PROMPT = ""  # Placeholder — set in Plan 06-03


async def ask_question(
    question: str,
    session_memory: SessionMemory | None = None,
    log_path: Path = Path("tool_calls.jsonl"),
) -> tuple[str, str, list]:
    raise NotImplementedError("ask_question implemented in Plan 06-03")
