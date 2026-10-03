"""HTTP contract: docs/specs/ui.md. Pipeline and Langfuse are stubbed."""

import pytest
from fastapi.testclient import TestClient

from app import main
from tests.test_db import result

PAYLOAD = {"id": "Z-1", "customer_id": "C-001", "channel": "email", "created_at": "2026-10-03T10:00:00",
           "subject": "Facturas", "body": "Mis facturas de Makro siguen en procesando"}


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("HADDOCK_DB", str(tmp_path / "web.db"))
    scores = []
    monkeypatch.setattr(main, "process_ticket", lambda ticket, customers, kb: result(ticket.id))
    monkeypatch.setattr(main, "send_scores", lambda trace_id, review: scores.append((trace_id, review)))
    monkeypatch.setattr(main, "init_tracing", lambda: None)
    with TestClient(main.app) as c:
        c.scores = scores
        yield c


def test_webhook_accepts_and_processes(client):
    r = client.post("/webhooks/ticket", json=PAYLOAD)
    assert r.status_code == 202
    page = client.get("/tickets/Z-1")
    assert page.status_code == 200
    assert "F-0101" in page.text  # the stubbed draft


def test_duplicate_webhook_is_409(client):
    client.post("/webhooks/ticket", json=PAYLOAD)
    assert client.post("/webhooks/ticket", json=PAYLOAD).status_code == 409


def test_unknown_customer_is_404(client):
    assert client.post("/webhooks/ticket", json={**PAYLOAD, "customer_id": "C-999"}).status_code == 404


def test_review_sends_scores_and_moves_on(client):
    client.post("/webhooks/ticket", json=PAYLOAD)
    r = client.post("/tickets/Z-1/review", data={
        "decision": "approve", "final_text": "Hola, F-0101 está en procesando.",
        "opened_at": "0", "category_final": "invoices",
    }, follow_redirects=False)
    assert r.status_code == 303
    [(trace_id, review)] = client.scores
    assert trace_id == "trace-1"
    assert review["decision"] == "approve"


def test_empty_reply_is_refused(client):
    client.post("/webhooks/ticket", json=PAYLOAD)
    r = client.post("/tickets/Z-1/review", data={"decision": "send", "final_text": "  ", "opened_at": "0"})
    assert r.status_code == 422
    assert client.scores == []


def test_blocked_draft_cannot_be_sent_unedited(client, monkeypatch):
    def blocked(ticket, customers, kb):
        r = result(ticket.id, status="escalated")
        r.reasons = ["refund_promise"]
        return r

    monkeypatch.setattr(main, "process_ticket", blocked)
    client.post("/webhooks/ticket", json=PAYLOAD)
    unedited = "Hola, F-0101 está en procesando."
    assert client.post("/tickets/Z-1/review", data={
        "decision": "send", "final_text": unedited, "opened_at": "0"}).status_code == 409
    edited = client.post("/tickets/Z-1/review", data={
        "decision": "send", "final_text": unedited + " Finanzas revisará tu caso.", "opened_at": "0"},
        follow_redirects=False)
    assert edited.status_code == 303
    assert client.scores[0][1]["decision"] == "edit"


def test_inbox_and_metrics_render(client):
    client.post("/webhooks/ticket", json=PAYLOAD)
    assert "Z-1" in client.get("/").text
    assert client.get("/metrics").status_code == 200
