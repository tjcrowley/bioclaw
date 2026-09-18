"""Fast-tier test for the unauthenticated GET /api/health endpoint
(14-RESEARCH.md Wave 0 Gap -- needed by both the Docker Compose
healthcheck: block and scripts/docker_compose_smoke_test.sh)."""
from fastapi.testclient import TestClient

from webapp.backend.main import app


def test_health_returns_ok_without_auth():
    client = TestClient(app)
    resp = client.get("/api/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}
