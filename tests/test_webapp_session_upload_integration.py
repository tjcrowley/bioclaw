"""Live end-to-end session/upload integration test (Phase 8, API-03/API-04).

Drives the real FastAPI app (no dependency_overrides) through a real
POST /api/upload followed by a real POST /api/ask in the same session_id,
proving the uploaded dataset's context is actually recalled by a live
agent turn -- not just structurally wired with fakes (Plans 08-01/08-02).
Also confirms the resulting session shows up in GET /api/sessions.
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
def test_upload_then_ask_recalls_dataset_in_same_session(tmp_path, analyzable_mtx_dir, monkeypatch):
    monkeypatch.setenv("BIOCLAW_WEB_PASSWORD", "testpass")
    monkeypatch.setattr(agent_tools, "STORE_ROOT", str(tmp_path / "store"))

    session_id = str(uuid.uuid4())
    client = TestClient(app)

    with open(analyzable_mtx_dir / "matrix.mtx.gz", "rb") as f1, \
         open(analyzable_mtx_dir / "barcodes.tsv.gz", "rb") as f2, \
         open(analyzable_mtx_dir / "features.tsv.gz", "rb") as f3:
        upload_resp = client.post(
            "/api/upload",
            files=[
                ("files", ("matrix.mtx.gz", f1, "application/gzip")),
                ("files", ("barcodes.tsv.gz", f2, "application/gzip")),
                ("files", ("features.tsv.gz", f3, "application/gzip")),
            ],
            data={"name": "webapp-e2e-upload", "session_id": session_id},
            headers={"Authorization": "Bearer testpass"},
        )
    assert upload_resp.status_code == 200
    upload_body = upload_resp.json()
    assert upload_body["status"] == "success"
    dataset_id = upload_body["dataset_id"]
    assert dataset_id.startswith("webapp-e2e-upload@")

    question = (
        "What dataset do you have context on from earlier in this session? "
        "Analyze it and tell me how many clusters it has."
    )
    ask_resp = client.post(
        "/api/ask",
        json={"question": question, "session_id": session_id},
        headers={"Authorization": "Bearer testpass"},
    )
    assert ask_resp.status_code == 200
    ask_body = ask_resp.json()
    assert ask_body["session_id"] == session_id
    assert ask_body["answer"], "Expected a non-empty answer from the real agent"
    assert dataset_id in ask_body["answer"], (
        f"Expected the real agent's answer to reference the uploaded dataset_id "
        f"{dataset_id!r} (recalled via SessionMemory), got: {ask_body['answer']!r}"
    )

    sessions_resp = client.get("/api/sessions", headers={"Authorization": "Bearer testpass"})
    assert sessions_resp.status_code == 200
    session_ids = [s["session_id"] for s in sessions_resp.json()["sessions"]]
    assert session_id in session_ids

    print("\n=== SESSION/UPLOAD E2E ANSWER ===")
    print(ask_body["answer"])
    print(f"session_id={session_id} dataset_id={dataset_id}")
