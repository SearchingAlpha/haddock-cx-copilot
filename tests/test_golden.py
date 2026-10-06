"""Golden database for the public demo: scripts/build_golden.py, docs/specs/deploy.md."""

import sqlite3
from datetime import datetime

from app import db
from app.domain import TicketIn
from scripts.build_golden import build
from tests.test_db import result


def test_golden_has_the_live_queue_and_every_radar_state(tmp_path):
    base, radar_db, out = (str(tmp_path / n) for n in ("base.db", "radar.db", "golden.db"))
    b = db.connect(base)
    db.insert_ticket(b, TicketIn(id="T-1", customer_id="C-001", channel="email", created_at=datetime(2026, 10, 1),
                                 subject="s", body="b"))
    db.save_result(b, result("T-1"))
    db.record_review(b, "T-1", "approve", "x", 10.0, None)
    b.close()
    r = db.connect(radar_db)
    db.insert_ticket(r, TicketIn(id="R-1", customer_id="C-019", channel="email", created_at=datetime(2026, 9, 2),
                                 subject="s", body="b"), source="history")
    db.insert_ticket(r, TicketIn(id="N-P0001-C019", customer_id="C-019", channel="email",
                                 created_at=datetime(2026, 10, 5), subject="Resuelto", body="{}"),
                     kind="proactive", mode="copilot", problem_id="P-0001")
    db.save_result(r, result("N-P0001-C019"))
    with r:
        r.execute("INSERT INTO problems (id, component, kind, title, status) VALUES "
                  "('P-0001', 'invoices.ocr', 'bug', 'a', 'resolved'), ('P-0002', 'bank.sync', 'bug', 'b', 'candidate')")
        r.execute("INSERT INTO notices VALUES ('P-0001', 'C-019', 'N-P0001-C019', '2026-10-05')")
    r.close()

    counts = build(base, radar_db, out, {"P-0002": 7})
    assert counts == {"resolved": 1, "requested": 1, "notices": 1, "live_tickets": 1}
    g = sqlite3.connect(out)
    assert g.execute("SELECT COUNT(*) FROM reviews").fetchone()[0] == 0  # every session starts the same
    assert g.execute("SELECT state FROM tickets WHERE id = 'T-1'").fetchone()[0] == "ready"
    assert g.execute("SELECT state FROM tickets WHERE id = 'N-P0001-C019'").fetchone()[0] == "ready"
