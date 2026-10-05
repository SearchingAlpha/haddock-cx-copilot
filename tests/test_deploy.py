"""Public demo guards: docs/specs/deploy.md. Pipeline and Langfuse are stubbed."""

import base64

import pytest
from fastapi.testclient import TestClient

from app import main
from tests.test_web import PAYLOAD


def auth(password: str) -> dict:
    return {"Authorization": "Basic " + base64.b64encode(f"enric:{password}".encode()).decode()}


@pytest.fixture
def make_client(tmp_path, monkeypatch):
    monkeypatch.setenv("HADDOCK_DB", str(tmp_path / "deploy.db"))
    monkeypatch.setattr(main, "init_tracing", lambda: None)
    monkeypatch.setattr(main, "run_pipeline", lambda ticket: None)

    def make(**env):
        for key in ("DEMO_PASSWORD", "HADDOCK_PUBLIC"):
            monkeypatch.delenv(key, raising=False)
        for key, value in env.items():
            monkeypatch.setenv(key, value)
        return TestClient(main.app)

    return make


def test_no_password_means_no_auth(make_client):
    assert make_client().get("/").status_code == 200


def test_password_required_when_set(make_client):
    client = make_client(DEMO_PASSWORD="s3cret")
    r = client.get("/")
    assert r.status_code == 401
    assert r.headers["WWW-Authenticate"].startswith("Basic")
    assert client.get("/", headers=auth("wrong")).status_code == 401
    assert client.get("/", headers=auth("s3cret")).status_code == 200


def test_static_needs_no_auth(make_client):
    assert make_client(DEMO_PASSWORD="s3cret").get("/static/favicon.png").status_code == 200


def test_public_mode_blocks_pipeline_entry_points(make_client):
    client = make_client(HADDOCK_PUBLIC="1")
    assert client.post("/webhooks/ticket", json=PAYLOAD).status_code == 403
    assert client.post("/demo/load", follow_redirects=False).status_code == 403
    assert "/demo/load" not in client.get("/").text


def test_local_mode_keeps_demo_button(make_client):
    assert "/demo/load" in make_client().get("/").text
