"""Fast-tier tests for webapp/backend/uploads.py and POST /api/upload (API-04)."""
import asyncio
import io

from fastapi import UploadFile

from webapp.backend import uploads


def _upload(name: str, content: bytes = b"data") -> UploadFile:
    return UploadFile(file=io.BytesIO(content), filename=name)


def test_stage_single_h5_file_stages_to_tempfile():
    f = _upload("sample.h5")
    path = asyncio.run(uploads.stage([f]))
    try:
        assert path.name == "sample.h5"
        assert path.read_bytes() == b"data"
    finally:
        uploads.cleanup(path)


def test_stage_rejects_bad_single_suffix():
    f = _upload("sample.txt")
    try:
        asyncio.run(uploads.stage([f]))
        assert False, "expected ValueError"
    except ValueError:
        pass


def test_stage_mtx_trio_stages_all_three():
    files = [_upload(n) for n in ["matrix.mtx.gz", "barcodes.tsv.gz", "features.tsv.gz"]]
    path = asyncio.run(uploads.stage(files))
    try:
        assert path.is_dir()
        assert {p.name for p in path.iterdir()} == {
            "matrix.mtx.gz", "barcodes.tsv.gz", "features.tsv.gz",
        }
    finally:
        uploads.cleanup(path)


def test_stage_rejects_incomplete_mtx_trio():
    files = [_upload("matrix.mtx.gz"), _upload("barcodes.tsv.gz")]
    try:
        asyncio.run(uploads.stage(files))
        assert False, "expected ValueError"
    except ValueError:
        pass


from fastapi.testclient import TestClient

import agent.tools as agent_tools
from agent.memory import SessionMemory
from webapp.backend import deps
from webapp.backend.main import app


def test_upload_h5_returns_dataset_id(monkeypatch, tmp_path, tiny_h5_file):
    monkeypatch.setenv("BIOCLAW_WEB_PASSWORD", "testpass")
    monkeypatch.setattr(agent_tools, "STORE_ROOT", str(tmp_path / "store"))
    app.dependency_overrides[deps.get_session_memory] = lambda: SessionMemory(root=tmp_path / "m.sqlite")
    try:
        client = TestClient(app)
        with open(tiny_h5_file, "rb") as f:
            resp = client.post(
                "/api/upload",
                files={"files": ("sample.h5", f, "application/octet-stream")},
                data={"name": "uploaded-sample"},
                headers={"Authorization": "Bearer testpass"},
            )
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "success"
        assert body["dataset_id"].startswith("uploaded-sample@")
    finally:
        app.dependency_overrides.clear()


def test_upload_mtx_trio_returns_dataset_id(monkeypatch, tmp_path, tiny_mtx_dir):
    monkeypatch.setenv("BIOCLAW_WEB_PASSWORD", "testpass")
    monkeypatch.setattr(agent_tools, "STORE_ROOT", str(tmp_path / "store"))
    app.dependency_overrides[deps.get_session_memory] = lambda: SessionMemory(root=tmp_path / "m.sqlite")
    try:
        client = TestClient(app)
        with open(tiny_mtx_dir / "matrix.mtx.gz", "rb") as f1, \
             open(tiny_mtx_dir / "barcodes.tsv.gz", "rb") as f2, \
             open(tiny_mtx_dir / "features.tsv.gz", "rb") as f3:
            resp = client.post(
                "/api/upload",
                files=[
                    ("files", ("matrix.mtx.gz", f1, "application/gzip")),
                    ("files", ("barcodes.tsv.gz", f2, "application/gzip")),
                    ("files", ("features.tsv.gz", f3, "application/gzip")),
                ],
                data={"name": "uploaded-mtx"},
                headers={"Authorization": "Bearer testpass"},
            )
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "success"
        assert body["dataset_id"].startswith("uploaded-mtx@")
    finally:
        app.dependency_overrides.clear()


def test_upload_rejects_incomplete_mtx_set(monkeypatch, tiny_mtx_dir):
    monkeypatch.setenv("BIOCLAW_WEB_PASSWORD", "testpass")
    client = TestClient(app)
    with open(tiny_mtx_dir / "matrix.mtx.gz", "rb") as f:
        resp = client.post(
            "/api/upload",
            files={"files": ("matrix.mtx.gz", f, "application/gzip")},
            data={"name": "bad"},
            headers={"Authorization": "Bearer testpass"},
        )
    assert resp.status_code == 422


def test_upload_result_recalled_in_next_question(monkeypatch, tmp_path, tiny_h5_file):
    monkeypatch.setenv("BIOCLAW_WEB_PASSWORD", "testpass")
    monkeypatch.setattr(agent_tools, "STORE_ROOT", str(tmp_path / "store"))
    mem = SessionMemory(root=tmp_path / "m.sqlite")
    app.dependency_overrides[deps.get_session_memory] = lambda: mem

    async def _fake_ask(question, session_memory=None, session_id=None, extra_hooks=None, log_path=None):
        recalled = session_memory.recent_datasets(session_id) if session_memory else []
        return f"recalled: {recalled}", session_id, []

    app.dependency_overrides[deps.get_ask_question] = lambda: _fake_ask
    try:
        client = TestClient(app)
        with open(tiny_h5_file, "rb") as f:
            up = client.post(
                "/api/upload",
                files={"files": ("sample.h5", f, "application/octet-stream")},
                data={"name": "convo-ds", "session_id": "sess-convo"},
                headers={"Authorization": "Bearer testpass"},
            )
        assert up.status_code == 200
        dataset_id = up.json()["dataset_id"]

        ask_resp = client.post(
            "/api/ask",
            json={"question": "what did I upload?", "session_id": "sess-convo"},
            headers={"Authorization": "Bearer testpass"},
        )
        assert dataset_id in ask_resp.json()["answer"]
    finally:
        app.dependency_overrides.clear()


def test_upload_uses_agent_tools_store_root(monkeypatch, tmp_path, tiny_h5_file):
    monkeypatch.setenv("BIOCLAW_WEB_PASSWORD", "testpass")
    custom_root = tmp_path / "custom-store"
    monkeypatch.setattr(agent_tools, "STORE_ROOT", str(custom_root))
    app.dependency_overrides[deps.get_session_memory] = lambda: SessionMemory(root=tmp_path / "m.sqlite")
    try:
        client = TestClient(app)
        with open(tiny_h5_file, "rb") as f:
            resp = client.post(
                "/api/upload",
                files={"files": ("sample.h5", f, "application/octet-stream")},
                data={"name": "root-check"},
                headers={"Authorization": "Bearer testpass"},
            )
        assert resp.status_code == 200
        assert custom_root.exists()  # DatasetStore.__init__ creates root -- proves the monkeypatched value was used
    finally:
        app.dependency_overrides.clear()


def test_upload_rejected_without_password(monkeypatch, tiny_h5_file):
    monkeypatch.setenv("BIOCLAW_WEB_PASSWORD", "testpass")
    client = TestClient(app)
    with open(tiny_h5_file, "rb") as f:
        resp = client.post(
            "/api/upload",
            files={"files": ("sample.h5", f, "application/octet-stream")},
            data={"name": "noauth"},
        )
    assert resp.status_code == 401
