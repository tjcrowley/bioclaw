"""Unit tests for webapp/backend/{auth,schemas}.py (Phase 7 Wave 1, API-02/API-05).

Covers `_valid()`'s three branches (correct password, wrong password, None
candidate) and construction of the Pydantic request/response contracts that
Plan 07-02's endpoints implement against. No FastAPI TestClient/app wiring
here -- that lands in Plan 07-02 alongside main.py.
"""

import asyncio

import pytest
from fastapi.testclient import TestClient

from agent.memory import SessionMemory
from webapp.backend import auth, deps, schemas, streaming
from webapp.backend.main import app


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


async def _fake_ask_question(question, session_memory=None, session_id=None, extra_hooks=None, log_path=None):
    for hook in extra_hooks or []:
        await hook(
            {
                "tool_name": "mcp__bioclaw__analyze_dataset",
                "tool_input": {"name": "x"},
                "tool_response": [{"type": "text", "text": "{}"}],
            },
            "tool-use-1",
            {},
        )
    resolved_session_id = session_id or "sess-1"
    if session_memory is not None:
        session_memory.touch(resolved_session_id)
    return "fake answer", resolved_session_id, []


def test_ask_returns_answer(monkeypatch):
    monkeypatch.setenv("BIOCLAW_WEB_PASSWORD", "testpass")
    app.dependency_overrides[deps.get_ask_question] = lambda: _fake_ask_question
    try:
        client = TestClient(app)
        resp = client.post(
            "/api/ask",
            json={"question": "how many clusters?"},
            headers={"Authorization": "Bearer testpass"},
        )
        assert resp.status_code == 200
        assert resp.json() == {"answer": "fake answer", "session_id": "sess-1", "citations": []}
    finally:
        app.dependency_overrides.clear()


def test_ask_streams_tool_events(monkeypatch):
    monkeypatch.setenv("BIOCLAW_WEB_PASSWORD", "testpass")
    app.dependency_overrides[deps.get_ask_question] = lambda: _fake_ask_question
    try:
        client = TestClient(app)
        with client.websocket_connect("/ws/stream-1?password=testpass") as ws:
            resp = client.post(
                "/api/ask",
                json={"question": "q", "stream_id": "stream-1"},
                headers={"Authorization": "Bearer testpass"},
            )
            assert resp.status_code == 200
            event = ws.receive_json()
            assert event == {
                "tool_name": "mcp__bioclaw__analyze_dataset",
                "tool_input": {"name": "x"},
                "is_error": False,
            }
    finally:
        app.dependency_overrides.clear()


def test_ask_rejected_without_password(monkeypatch):
    monkeypatch.setenv("BIOCLAW_WEB_PASSWORD", "testpass")
    client = TestClient(app)
    resp = client.post("/api/ask", json={"question": "q"})
    assert resp.status_code == 401


def test_ws_rejected_without_password(monkeypatch):
    monkeypatch.setenv("BIOCLAW_WEB_PASSWORD", "testpass")
    client = TestClient(app)
    with pytest.raises(Exception):
        with client.websocket_connect("/ws/stream-2"):
            pass


def test_ask_resumes_existing_session_id(monkeypatch, tmp_path):
    monkeypatch.setenv("BIOCLAW_WEB_PASSWORD", "testpass")
    app.dependency_overrides[deps.get_ask_question] = lambda: _fake_ask_question
    app.dependency_overrides[deps.get_session_memory] = lambda: SessionMemory(root=tmp_path / "m.sqlite")
    try:
        client = TestClient(app)
        resp = client.post(
            "/api/ask",
            json={"question": "q1", "session_id": "sess-42"},
            headers={"Authorization": "Bearer testpass"},
        )
        assert resp.json()["session_id"] == "sess-42"  # NOT a fresh default
    finally:
        app.dependency_overrides.clear()


def test_list_sessions_returns_metadata(monkeypatch, tmp_path):
    monkeypatch.setenv("BIOCLAW_WEB_PASSWORD", "testpass")
    mem = SessionMemory(root=tmp_path / "m.sqlite")
    mem.touch("sess-1")
    mem.record("sess-1", "pilot@1")
    app.dependency_overrides[deps.get_session_memory] = lambda: mem
    try:
        client = TestClient(app)
        resp = client.get("/api/sessions", headers={"Authorization": "Bearer testpass"})
        assert resp.status_code == 200
        body = resp.json()
        assert body["sessions"][0]["session_id"] == "sess-1"
        assert body["sessions"][0]["recent_datasets"] == ["pilot@1"]
    finally:
        app.dependency_overrides.clear()


def test_list_sessions_rejected_without_password(monkeypatch):
    monkeypatch.setenv("BIOCLAW_WEB_PASSWORD", "testpass")
    client = TestClient(app)
    resp = client.get("/api/sessions")
    assert resp.status_code == 401


def test_get_session_returns_404_for_unknown_session(monkeypatch, tmp_path):
    monkeypatch.setenv("BIOCLAW_WEB_PASSWORD", "testpass")
    app.dependency_overrides[deps.get_session_memory] = lambda: SessionMemory(root=tmp_path / "m.sqlite")
    try:
        client = TestClient(app)
        resp = client.get("/api/sessions/no-such-session", headers={"Authorization": "Bearer testpass"})
        assert resp.status_code == 404
    finally:
        app.dependency_overrides.clear()


def test_resume_recalls_prior_dataset_reference(monkeypatch, tmp_path):
    monkeypatch.setenv("BIOCLAW_WEB_PASSWORD", "testpass")
    mem = SessionMemory(root=tmp_path / "m.sqlite")
    app.dependency_overrides[deps.get_session_memory] = lambda: mem

    async def _fake_with_recall(question, session_memory=None, session_id=None, extra_hooks=None, log_path=None):
        sid = session_id or "sess-99"
        if session_memory is not None:
            session_memory.touch(sid)
            if not session_memory.recent_datasets(sid):
                session_memory.record(sid, "pilot@1")
        return "answer", sid, []

    app.dependency_overrides[deps.get_ask_question] = lambda: _fake_with_recall
    try:
        client = TestClient(app)
        r1 = client.post(
            "/api/ask",
            json={"question": "ingest pilot", "session_id": "sess-99"},
            headers={"Authorization": "Bearer testpass"},
        )
        assert r1.json()["session_id"] == "sess-99"
        assert mem.recent_datasets("sess-99") == ["pilot@1"]

        r2 = client.post(
            "/api/ask",
            json={"question": "what clusters?", "session_id": "sess-99"},
            headers={"Authorization": "Bearer testpass"},
        )
        assert r2.json()["session_id"] == "sess-99"
        assert mem.recent_datasets("sess-99") == ["pilot@1"]
    finally:
        app.dependency_overrides.clear()
