"""Unit tests for webapp/backend/{auth,schemas}.py (Phase 7 Wave 1, API-02/API-05).

Covers `_valid()`'s three branches (correct password, wrong password, None
candidate) and construction of the Pydantic request/response contracts that
Plan 07-02's endpoints implement against. No FastAPI TestClient/app wiring
here -- that lands in Plan 07-02 alongside main.py.
"""

from webapp.backend import auth, schemas


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
