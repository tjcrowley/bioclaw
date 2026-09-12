"""Per-request stream_id -> asyncio.Queue registry + the PostToolUse hook
factory that bridges agent tool-call activity into that queue (API-02).

Single Uvicorn worker assumption (07-RESEARCH.md Pitfall 3): asyncio.Queue
is in-process only. Every hook built here must never raise -- mirrors
agent/session.py::record_dataset_reference()'s own documented invariant --
because an uncaught exception in a PostToolUse hook can silently break the
entire hook chain for a request (07-RESEARCH.md Pitfall 4), including the
unrelated citation-hash logging hook.
"""
import asyncio
from typing import Any

_QUEUES: dict[str, asyncio.Queue] = {}


def get_or_create_queue(stream_id: str, maxsize: int = 100) -> asyncio.Queue:
    if stream_id not in _QUEUES:
        _QUEUES[stream_id] = asyncio.Queue(maxsize=maxsize)
    return _QUEUES[stream_id]


def drop_queue(stream_id: str) -> None:
    _QUEUES.pop(stream_id, None)


def _tool_response_is_error(tool_response: Any) -> bool:
    if isinstance(tool_response, dict):
        return bool(tool_response.get("is_error"))
    return False


def make_stream_hook(queue: asyncio.Queue):
    async def _hook(input_data, tool_use_id, context):
        try:
            event = {
                "tool_name": input_data.get("tool_name", ""),
                "tool_input": input_data.get("tool_input", {}),
                "is_error": _tool_response_is_error(input_data.get("tool_response")),
            }
            queue.put_nowait(event)
        except Exception:
            pass
        return {}

    return _hook
