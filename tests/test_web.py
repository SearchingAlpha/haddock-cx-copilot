"""HTTP contract: docs/specs/ui.md. Pipeline and Langfuse are stubbed."""

import pytest
from fastapi.testclient import TestClient

from app import db, main
from app.domain import TicketIn
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
    monkeypatch.setattr(main, "radar_step", lambda ticket, result: None)  # tests/test_problems.py covers it
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


def _seed_radar():
    from datetime import datetime

    from app import problems
    from app.domain import Component, Kind, Priority
    from app.signals import Signal

    conn = db.connect()
    for i, c in enumerate(["C-019", "C-022", "C-025"]):
        db.insert_ticket(conn, TicketIn(id=f"R-{i}", customer_id=c, channel="email",
                                        created_at=datetime(2026, 9, 2 + i, 10), subject="Garrido",
                                        body="No se lee"), source="history")
        s = Signal(f"R-{i}", c, datetime(2026, 9, 2 + i, 10).isoformat(), "Garrido", Component.invoices_ocr, Kind.bug,
                   "Distribuciones Garrido", "El OCR no lee Garrido", priority=Priority.high)
        problems.assign(conn, s, matcher=lambda text: problems.Match(True, 0.9))
        problems.refresh_status(conn, "P-0001", main.CUSTOMERS, s.created_at)
    conn.close()


def test_radar_pages_render(client):
    assert "Aún no hay problemas" in client.get("/radar").text
    _seed_radar()
    page = client.get("/radar")
    assert page.status_code == 200 and "El OCR no lee Garrido" in page.text
    graph = client.get("/radar/graph.json").json()
    assert {n["data"]["kind"] for n in graph["nodes"]} == {"area", "problem", "customer"}
    detail = client.get("/radar/problems/P-0001")
    assert detail.status_code == 200 and "Cruzó el umbral" in detail.text
    assert client.get("/radar/problems/P-9999").status_code == 404
    assert client.get("/").status_code == 200  # history tickets stay out of the queue


def test_request_flow_from_the_problem_page(client, monkeypatch):
    from app import product_request
    from tests.test_product_request import FakeAnthropic, FakeGitHub, draft

    _seed_radar()
    monkeypatch.setattr(product_request, "_client", lambda: FakeAnthropic(draft()))
    assert "Redactar la petición" in client.get("/radar/problems/P-0001").text
    assert client.post("/radar/problems/P-0001/draft", follow_redirects=False).status_code == 303
    page = client.get("/radar/problems/P-0001").text
    assert "Crear la issue en GitHub" not in page and "GitHub no está configurado" in page

    gh = FakeGitHub()
    monkeypatch.setattr(main, "github_client", lambda: gh)
    page = client.get("/radar/problems/P-0001").text
    assert "Crear la issue en GitHub" in page
    req = product_request.load(db.connect(), "P-0001")
    r = client.post("/radar/problems/P-0001/request", data={
        "decision": "approve", "title": req["title"], "body_md": req["body_md"].replace("\n", "\r\n")},
        follow_redirects=False)
    assert r.status_code == 303 and len(gh.issues) == 1
    assert product_request.load(db.connect(), "P-0001")["decision"] == "approve"  # \r\n from the form is not an edit
    assert "#7 en GitHub" in client.get("/radar/problems/P-0001").text


def test_request_without_github_redirects_with_an_error(client, monkeypatch):
    from app import product_request
    from tests.test_product_request import FakeAnthropic, draft

    _seed_radar()
    monkeypatch.setattr(product_request, "_client", lambda: FakeAnthropic(draft()))
    monkeypatch.setattr(main, "github_client", lambda: None)
    client.post("/radar/problems/P-0001/draft")
    r = client.post("/radar/problems/P-0001/request", data={"decision": "approve", "title": "t", "body_md": "b"},
                    follow_redirects=False)
    assert r.headers["location"].endswith("?error=github-config")


def test_public_demo_never_writes_from_the_radar(client, monkeypatch):
    _seed_radar()
    monkeypatch.setenv("HADDOCK_PUBLIC", "1")
    assert client.post("/radar/problems/P-0001/draft").status_code == 403
    assert client.post("/radar/problems/P-0001/request", data={"decision": "reject"}).status_code == 403
    assert client.get("/radar/problems/P-0001").status_code == 200


def _signed(payload: dict, secret: str = "s3cret") -> tuple[bytes, dict]:
    import hashlib
    import hmac
    import json as _json

    body = _json.dumps(payload).encode()
    sig = "sha256=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    return body, {"X-Hub-Signature-256": sig, "X-GitHub-Event": "issues", "Content-Type": "application/json"}


def test_github_webhook_resolves_and_queues_notices(client, monkeypatch):
    monkeypatch.setenv("GITHUB_WEBHOOK_SECRET", "s3cret")
    monkeypatch.setenv("DEMO_PASSWORD", "pw")  # the webhook skips basic auth: the signature is its auth
    _seed_radar()
    conn = db.connect()
    conn.execute("UPDATE problems SET status = 'requested', github_number = 7 WHERE id = 'P-0001'")
    conn.commit()
    conn.close()
    queued = []
    monkeypatch.setattr(main, "run_notices", lambda pid: queued.append(pid))
    payload = {"action": "closed", "issue": {"number": 7, "state": "closed", "state_reason": "completed", "body": ""}}

    body, headers = _signed(payload)
    assert client.post("/webhooks/github", content=body, headers={**headers, "X-Hub-Signature-256": "sha256=0"}).status_code == 401
    r = client.post("/webhooks/github", content=body, headers=headers)
    assert r.status_code == 202 and r.json()["result"] == "notify" and queued == ["P-0001"]
    assert client.post("/webhooks/github", content=body, headers=headers).json()["result"] is None  # idempotent
    assert client.get("/radar").status_code == 401  # everything else still asks for the password


def test_public_demo_ignores_github(client, monkeypatch):
    monkeypatch.setenv("HADDOCK_PUBLIC", "1")
    body, headers = _signed({"action": "closed"})
    assert client.post("/webhooks/github", content=body, headers=headers).status_code == 403
    assert client.post("/radar/sync").status_code == 403
