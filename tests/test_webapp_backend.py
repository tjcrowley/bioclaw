"""Unit tests for webapp/backend/{auth,schemas}.py (Phase 7 Wave 1, API-02/API-05).

Covers `_valid()`'s three branches (correct password, wrong password, None
candidate) and construction of the Pydantic request/response contracts that
Plan 07-02's endpoints implement against. No FastAPI TestClient/app wiring
here -- that lands in Plan 07-02 alongside main.py.
"""

import asyncio

from webapp.backend import auth, schemas, streaming


def test__valid_accepts_correct_password(monkeypatch):
    monkeypatch.setenv("BIOCLAW_WEB_PASSWORD", "testpass")

    assert auth._valid("testpass") is True


def test__valid_rejects_wrong_password(monkeypatch):
    monkeypatch.setenv("BIOCLAW_WEB_PASSWORD", "testpass")

    assert auth._valid("wrong") is False


def test__valid_rejects_none(monkeypatch):
    monkeypatch.setenv("BIOCLAW_WEB_PASSWORD", "testpass")

    assert auth._valid(None) is False


def test_schemas_importable():
    ask_request = schemas.AskRequest(question="x")
    assert ask_request.session_id is None
    assert ask_request.stream_id is None

    tool_event = schemas.ToolEvent(tool_name="t", tool_input={}, is_error=False)
    assert tool_event.tool_name == "t"

    ask_response = schemas.AskResponse(answer="a", session_id="s", citations=[])
    assert ask_response.answer == "a"


def test_get_or_create_queue_returns_same_queue_for_same_id():
    q1 = streaming.get_or_create_queue("s1")
    q2 = streaming.get_or_create_queue("s1")
    q3 = streaming.get_or_create_queue("s2")

    assert q1 is q2
    assert q1 is not q3


def test_make_stream_hook_enqueues_event():
    queue = asyncio.Queue()
    hook = streaming.make_stream_hook(queue)
    input_data = {
        "tool_name": "mcp__bioclaw__analyze_dataset",
        "tool_input": {"name": "x"},
        "tool_response": [{"type": "text", "text": "{}"}],
    }

    asyncio.run(hook(input_data, "tid", {}))

    assert queue.get_nowait() == {
        "tool_name": "mcp__bioclaw__analyze_dataset",
        "tool_input": {"name": "x"},
        "is_error": False,
    }


def test_make_stream_hook_marks_is_error_true():
    queue = asyncio.Queue()
    hook = streaming.make_stream_hook(queue)
    input_data = {
        "tool_name": "mcp__bioclaw__analyze_dataset",
        "tool_input": {"name": "x"},
        "tool_response": {"is_error": True},
    }

    asyncio.run(hook(input_data, "tid", {}))

    event = queue.get_nowait()
    assert event["is_error"] is True


def test_make_stream_hook_never_raises_on_malformed_input():
    queue = asyncio.Queue()
    hook = streaming.make_stream_hook(queue)
    input_data = {"tool_name": "x", "tool_input": {}, "tool_response": None}

    result = asyncio.run(hook(input_data, "tid", {}))
    assert result == {}

    full_queue = asyncio.Queue(maxsize=1)
    full_queue.put_nowait({"already": "full"})
    full_hook = streaming.make_stream_hook(full_queue)

    result = asyncio.run(full_hook(input_data, "tid", {}))
    assert result == {}


def test_drop_queue_removes_entry():
    q1 = streaming.get_or_create_queue("s1")
    streaming.drop_queue("s1")
    q2 = streaming.get_or_create_queue("s1")

    assert q1 is not q2
