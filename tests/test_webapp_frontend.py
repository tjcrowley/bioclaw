"""Fast-tier tests for Phase 9 frontend: static file serving + login endpoint.

All tests use Starlette's synchronous TestClient -- no pytest-asyncio needed.
Browser/JS behaviour is tested manually in Phase 10.
"""
import pytest
from starlette.testclient import TestClient

from webapp.backend.main import app


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv("BIOCLAW_WEB_PASSWORD", "testpass")
    return TestClient(app, raise_server_exceptions=True)


# ─── Static file serving ─────────────────────────────────────────────────────

def test_login_page_served(client):
    resp = client.get("/app/")
    assert resp.status_code == 200
    assert "text/html" in resp.headers["content-type"]
    assert 'id="login-overlay"' in resp.text
    assert 'id="app"' in resp.text


def test_html_structure(client):
    resp = client.get("/app/")
    assert resp.status_code == 200
    assert 'id="password-input"' in resp.text
    assert 'id="login-btn"' in resp.text
    assert 'id="session-list"' in resp.text
    assert 'id="main-panel"' in resp.text


def test_static_js_files_served(client):
    for js_file in ["main.js", "api.js", "chat.js", "citations.js", "sessions.js"]:
        resp = client.get(f"/app/{js_file}")
        assert resp.status_code == 200, f"{js_file} not served"
        assert "javascript" in resp.headers.get("content-type", "")


def test_static_css_served(client):
    resp = client.get("/app/style.css")
    assert resp.status_code == 200
    assert "text/css" in resp.headers["content-type"]


def test_css_design_tokens(client):
    resp = client.get("/app/style.css")
    assert "--bg-page" in resp.text
    assert "--bg-panel" in resp.text
    assert "--accent-primary" in resp.text
    assert "--sidebar-width" in resp.text


# ─── Login endpoint ──────────────────────────────────────────────────────────

def test_login_sets_cookie(client):
    resp = client.post("/api/login", json={"password": "testpass"})
    assert resp.status_code == 200
    assert resp.json() == {"ok": True}
    # TestClient jar should have the session cookie
    assert "session" in client.cookies


def test_login_rejects_bad_password(client):
    resp = client.post("/api/login", json={"password": "wrongpass"})
    assert resp.status_code == 401


def test_login_rejects_empty_password(client):
    resp = client.post("/api/login", json={"password": ""})
    assert resp.status_code == 401


def test_login_no_prior_auth_required(monkeypatch):
    """POST /api/login must work without any existing session cookie (it IS the auth step)."""
    monkeypatch.setenv("BIOCLAW_WEB_PASSWORD", "testpass")
    # Fresh client with NO cookie jar
    fresh = TestClient(app, raise_server_exceptions=True)
    resp = fresh.post("/api/login", json={"password": "testpass"})
    assert resp.status_code == 200


# ─── JS/CSS file content ─────────────────────────────────────────────────────

def test_api_js_exports(client):
    resp = client.get("/app/api.js")
    assert resp.status_code == 200
    for fn in ["askQuestion", "openToolStream", "listSessions", "uploadDataset", "login"]:
        assert fn in resp.text, f"api.js missing function: {fn}"


def test_chat_js_exports(client):
    resp = client.get("/app/chat.js")
    assert resp.status_code == 200
    for fn in ["sendMessage", "appendMessage", "renderActivityEvent"]:
        assert fn in resp.text, f"chat.js missing function: {fn}"


def test_citations_js_exports(client):
    resp = client.get("/app/citations.js")
    assert resp.status_code == 200
    for fn in ["renderAnswerWithCitations", "showCitationDetail"]:
        assert fn in resp.text, f"citations.js missing function: {fn}"


def test_sessions_js_exports(client):
    resp = client.get("/app/sessions.js")
    assert resp.status_code == 200
    for fn in ["loadSessionList", "resumeSession"]:
        assert fn in resp.text, f"sessions.js missing function: {fn}"


# ─── Existing route regression ───────────────────────────────────────────────

def test_api_ask_still_reachable(client):
    """StaticFiles mount must not shadow /api/* routes."""
    # POST /api/ask without auth should 401, not 404
    resp = client.post("/api/ask", json={"question": "test"})
    assert resp.status_code == 401


def test_api_sessions_still_reachable(client):
    resp = client.get("/api/sessions")
    assert resp.status_code == 401
