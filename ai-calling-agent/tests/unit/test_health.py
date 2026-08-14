"""Health endpoints are load-bearing — ECS task health checks depend on them."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client(dev_env: None) -> TestClient:
    from fg_voice.main import app

    return TestClient(app)


def test_healthz_returns_200(client: TestClient) -> None:
    r = client.get("/healthz")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert "version" in body
    assert body["env"] == "dev"


def test_readyz_returns_200_in_p0(client: TestClient) -> None:
    """In P0 there are no external dependencies to ping, so readyz is
    always 200. P4 will add snapshot readiness and this test evolves."""
    r = client.get("/readyz")
    assert r.status_code == 200
    assert r.json()["status"] == "ready"
