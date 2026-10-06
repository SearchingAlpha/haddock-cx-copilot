"""Storage and impact metrics: docs/specs/db.md."""

from datetime import datetime

import pytest

from app import db
from app.classify import ClassifyResult, TicketClassification
from app.domain import Category, Language, Priority, Sentiment, TicketIn
from app.pipeline import TicketResult


@pytest.fixture
def conn(tmp_path):
    c = db.connect(str(tmp_path / "test.db"))
    yield c
    c.close()


def ticket(id="T-900", channel="email"):
    return TicketIn(id=id, customer_id="C-001", channel=channel, created_at=datetime(2026, 10, 1, 9),
                    subject="Facturas", body="Mis facturas siguen en procesando")


def result(id="T-900", status="ready", category=Category.invoices, cost=0.02):
    c = TicketClassification(category=category, priority=Priority.normal, sentiment=Sentiment.neutral,
                             language=Language.es)
    r = TicketResult(id, status, ClassifyResult(c, {"category": 0.95}, "jev"), trace_id="trace-1")
    r.agent = type("A", (), {"draft": "Hola, F-0101 está en procesando.", "evidence": ["F-0101"],
                             "tool_calls": ["get_invoices"], "cost_usd": cost, "prompt_version": 1})()
    return r


def test_ticket_starts_processing_and_result_moves_it(conn):
    db.insert_ticket(conn, ticket())
    assert db.get_ticket(conn, "T-900")["state"] == "processing"

    db.save_result(conn, result(status="escalated"))
    t = db.get_ticket(conn, "T-900")
    assert t["state"] == "escalated"
    assert t["draft"].startswith("Hola")
    assert t["classification"]["category"] == "invoices"


def test_duplicate_ticket_raises(conn):
    db.insert_ticket(conn, ticket())
    with pytest.raises(ValueError):
        db.insert_ticket(conn, ticket())


def test_review_states_and_edit_distance(conn):
    db.insert_ticket(conn, ticket())
    db.save_result(conn, result())

    unchanged = db.record_review(conn, "T-900", "approve", "Hola, F-0101 está en procesando.", 30.0, "invoices")
    assert unchanged["edit_distance"] == 0.0
    assert db.get_ticket(conn, "T-900")["state"] == "sent"

    rejected = db.record_review(conn, "T-900", "reject", "", 5.0, "invoices")
    assert rejected["edit_distance"] == 1.0
    assert db.get_ticket(conn, "T-900")["state"] == "rejected"


def test_mode_is_stable_and_about_20_percent_manual():
    assert db.mode_for("T-001") == db.mode_for("T-001")
    manual = sum(db.mode_for(f"T-{i:04d}") == "manual" for i in range(2000)) / 2000
    assert 0.15 < manual < 0.25


def test_metrics_with_known_reviews(conn, monkeypatch):
    modes = {"T-1": "copilot", "T-2": "copilot", "T-3": "manual"}
    monkeypatch.setattr(db, "mode_for", lambda tid: modes[tid])
    for tid in modes:
        db.insert_ticket(conn, ticket(tid))
        db.save_result(conn, result(tid, category=Category.bank if tid == "T-2" else Category.invoices))
    db.record_review(conn, "T-1", "approve", "Hola, F-0101 está en procesando.", 40.0, "invoices")
    db.record_review(conn, "T-2", "edit", "Hola, otra cosa.", 80.0, "account")   # category corrected
    db.record_review(conn, "T-3", "manual", "Escrito a mano.", 300.0, "invoices")

    m = db.metrics(conn)

    assert m["approved_unedited_rate"] == 0.5
    assert m["avg_seconds_copilot"] == 60.0
    assert m["avg_seconds_manual"] == 300.0
    assert m["seconds_saved_per_ticket"] == 240.0
    assert m["category_corrections"] == 1
    assert m["cost_per_ticket_usd"] == pytest.approx(0.02)
    assert m["by_category"] == {"invoices": 2, "bank": 1}


def test_metrics_without_manual_reviews_has_no_baseline(conn):
    db.insert_ticket(conn, ticket())
    assert db.metrics(conn)["avg_seconds_manual"] is None


def test_old_database_gets_the_radar_columns(tmp_path):
    import sqlite3
    path = str(tmp_path / "old.db")
    old = sqlite3.connect(path)
    old.executescript("CREATE TABLE tickets (id TEXT PRIMARY KEY, customer_id TEXT, channel TEXT, subject TEXT, "
                      "body TEXT, created_at TEXT, mode TEXT, state TEXT);"
                      "INSERT INTO tickets VALUES ('T-1', 'C-001', 'email', 's', 'b', '2026-10-01T09:00:00', "
                      "'copilot', 'ready');")
    old.close()
    conn = db.connect(path)
    t = db.get_ticket(conn, "T-1")
    assert (t["kind"], t["source"], t["problem_id"]) == ("inbound", "live", None)
    db.insert_ticket(conn, ticket("T-2"))  # named columns: works on the migrated table


def test_history_tickets_stay_out_of_the_queue(conn):
    db.insert_ticket(conn, ticket("T-1"), source="history")
    db.insert_ticket(conn, ticket("T-2"))
    assert [t["id"] for t in db.list_tickets(conn)] == ["T-2"]
    assert db.get_ticket(conn, "T-1")["state"] == "history"
    assert len(db.list_tickets(conn, history=True)) == 2
