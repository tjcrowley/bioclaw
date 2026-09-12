"""Live end-to-end webapp integration test (Phase 7, API-01/API-02).

Drives the real FastAPI app (no dependency_overrides) through a real
ask_question() call and asserts the WebSocket leg actually receives live
tool-call events during that call, mirroring tests/test_qa_integration.py's
Phase-6 live_llm pattern at the HTTP/WS layer.

Marked @pytest.mark.live_llm and skipped when ANTHROPIC_API_KEY is unset.
"""
import os
import uuid

import pytest
from fastapi.testclient import TestClient

import agent.tools as agent_tools
from webapp.backend.main import app


@pytest.mark.live_llm
@pytest.mark.skipif(
    not os.environ.get("ANTHROPIC_API_KEY"),
    reason="requires ANTHROPIC_API_KEY",
)
def test_ask_streams_real_tool_events_end_to_end(tmp_path, analyzable_mtx_dir, monkeypatch):
    monkeypatch.setenv("BIOCLAW_WEB_PASSWORD", "testpass")
    monkeypatch.setattr(agent_tools, "STORE_ROOT", str(tmp_path / "store"))

    stream_id = str(uuid.uuid4())
    question = (
        "Ingest the dataset at {path} and tell me how many clusters it has."
    ).format(path=str(analyzable_mtx_dir))

    client = TestClient(app)
    with client.websocket_connect(f"/ws/{stream_id}?password=testpass") as ws:
        resp = client.post(
            "/api/ask",
            json={"question": question, "stream_id": stream_id},
            headers={"Authorization": "Bearer testpass"},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["answer"], "Expected a non-empty answer from the real agent"

        event = ws.receive_json()
        assert event["tool_name"].startswith("mcp__bioclaw__"), (
            f"Expected a real bioclaw tool-call event, got: {event}"
        )

    print("\n=== WEBAPP E2E ANSWER ===")
    print(body["answer"])
    print(f"session_id={body['session_id']}")
    print(f"first streamed tool event: {event}")
