"""Radar contract: docs/specs/radar.md. A fake matcher and a fake extractor: no network."""

from datetime import datetime, timedelta

import pytest

from app import db, problems, radar
from app.data import load_customers
from app.domain import Component, Kind, Priority, TicketIn
from app.entities import Gazetteer
from app.problems import Match, impact
from app.signals import Signal


@pytest.fixture(scope="module")
def customers():
    return load_customers()


@pytest.fixture
def conn(tmp_path):
    c = db.connect(str(tmp_path / "radar.db"))
    yield c
    c.close()


T0 = datetime(2026, 9, 1, 10)


def signal(id, customer="C-018", component=Component.invoices_ocr, kind=Kind.bug, entity="Distribuciones Garrido",
           symptom="El OCR no lee el total de Garrido", day=0, priority=Priority.high) -> Signal:
    return Signal(id, customer, (T0 + timedelta(days=day)).isoformat(), f"{symptom}\n\nbody", component, kind,
                  entity, symptom, priority=priority)


def stored(conn, s: Signal) -> Signal:
    db.insert_ticket(conn, TicketIn(id=s.ticket_id, customer_id=s.customer_id, channel="email",
                                    created_at=datetime.fromisoformat(s.created_at), subject="x", body="y"),
                     source="history")
    return s


class Recorder:
    """Fake matcher: says yes to the problems in `yes`, and records every question."""

    def __init__(self, yes=(), confidence=0.9):
        self.yes, self.confidence, self.asked = set(yes), confidence, []

    def __call__(self, text: str) -> Match:
        self.asked.append(text)
        known = text.split("New ticket")[0]  # look only at the known problem, never at the new ticket
        return Match(any(p in known for p in self.yes), self.confidence)


def test_how_to_and_user_error_never_form_a_problem(conn):
    matcher = Recorder()
    for i, kind in enumerate((Kind.how_to, Kind.user_error)):
        assert problems.assign(conn, stored(conn, signal(f"R-{i}", kind=kind)), matcher=matcher) is None
    assert matcher.asked == []
    assert conn.execute("SELECT COUNT(*) FROM problems").fetchone()[0] == 0
    assert conn.execute("SELECT COUNT(*) FROM signals").fetchone()[0] == 2


def test_first_bug_opens_a_problem_titled_by_its_symptom(conn):
    pid = problems.assign(conn, stored(conn, signal("R-1")), matcher=Recorder())
    row = conn.execute("SELECT * FROM problems WHERE id = ?", (pid,)).fetchone()
    assert (pid, row["status"], row["title"]) == ("P-0001", "open", "El OCR no lee el total de Garrido")
    assert db.get_ticket(conn, "R-1")["problem_id"] == pid


def test_yes_joins_the_problem_and_no_opens_a_new_one(conn):
    first = problems.assign(conn, stored(conn, signal("R-1")), matcher=Recorder())
    joined = problems.assign(conn, stored(conn, signal("R-2", day=1)), matcher=Recorder(yes=["Garrido"]))
    split = problems.assign(conn, stored(conn, signal("R-3", day=2)), matcher=Recorder(yes=[]))
    assert joined == first
    assert split != first


def test_low_confidence_yes_opens_a_new_problem(conn):
    first = problems.assign(conn, stored(conn, signal("R-1")), matcher=Recorder())
    weak = Recorder(yes=["Garrido"], confidence=0.2)
    assert problems.assign(conn, stored(conn, signal("R-2")), matcher=weak) != first


def test_fallback_yes_without_confidence_counts(conn):
    first = problems.assign(conn, stored(conn, signal("R-1")), matcher=Recorder())
    fallback = Recorder(yes=["Garrido"], confidence=None)
    assert problems.assign(conn, stored(conn, signal("R-2")), matcher=fallback) == first


def test_candidates_need_the_same_component_and_a_compatible_entity(conn):
    problems.assign(conn, stored(conn, signal("R-1")), matcher=Recorder())
    other_area = Recorder(yes=["Garrido"])
    problems.assign(conn, stored(conn, signal("R-2", component=Component.bank_sync, entity="Kutxabank")),
                    matcher=other_area)
    other_supplier = Recorder(yes=["Garrido"])
    problems.assign(conn, stored(conn, signal("R-3", entity="Makro")), matcher=other_supplier)
    no_entity = Recorder(yes=["Garrido"])
    problems.assign(conn, stored(conn, signal("R-4", entity=None)), matcher=no_entity)
    assert other_area.asked == [] and other_supplier.asked == []
    assert len(no_entity.asked) == 2  # P-0001 (Garrido) and P-0003 (Makro): an empty entity is compatible


def test_bm25_sends_only_the_top_3_when_there_are_more(conn):
    for i, word in enumerate(["Makro", "Mahou", "Cruzcampo", "Garrido", "Damm"]):
        problems.assign(conn, stored(conn, signal(f"R-{i}", entity=None, symptom=f"El OCR falla con {word}")),
                        matcher=Recorder())
    matcher = Recorder(yes=["Garrido"])
    pid = problems.assign(conn, stored(conn, signal("R-9", entity=None, symptom="El OCR falla con Garrido")),
                          matcher=matcher)
    assert len(matcher.asked) == 3
    assert pid == "P-0004"


def test_a_failing_matcher_splits_instead_of_merging(conn):
    first = problems.assign(conn, stored(conn, signal("R-1")), matcher=Recorder())

    def broken(text):
        raise TimeoutError

    assert problems.assign(conn, stored(conn, signal("R-2")), matcher=broken) != first


def test_dismissed_problems_take_no_new_tickets(conn):
    first = problems.assign(conn, stored(conn, signal("R-1")), matcher=Recorder())
    conn.execute("UPDATE problems SET status = 'dismissed' WHERE id = ?", (first,))
    matcher = Recorder(yes=["Garrido"])
    assert problems.assign(conn, stored(conn, signal("R-2")), matcher=matcher) != first
    assert matcher.asked == []


def test_impact_counts_distinct_customers_and_their_mrr(customers):
    now = T0 + timedelta(days=14)
    rows = [{"customer_id": c, "priority": p, "created_at": (now - timedelta(days=d)).isoformat()}
            for c, p, d in [("C-018", "high", 1), ("C-018", "normal", 2), ("C-021", "urgent", 10)]]
    imp = impact(rows, customers, now)
    assert imp.customers == ["C-018", "C-021"]
    assert imp.mrr_eur == 149.0 + 560.0
    assert imp.severity == round(2 / 3, 3)
    assert imp.trend == round((2 + 1) / (1 + 1), 2)
    assert imp.weekly[-2:] == [1, 2]
    assert imp.score == round(709.0 * (1 + 0.5 * 2 / 3) * 1.5, 1)


def test_threshold_three_customers_or_two_with_400_eur(customers):
    def imp(*ids):
        return impact([{"customer_id": c, "priority": "normal", "created_at": T0.isoformat()} for c in ids],
                      customers, T0)

    assert not problems.crosses_threshold(imp("C-003"))  # 690 EUR, but one voice is not a pattern
    assert not problems.crosses_threshold(imp("C-042", "C-048"))  # 2 starters: 118 EUR
    assert problems.crosses_threshold(imp("C-003", "C-042"))  # 2 customers, 749 EUR
    assert problems.crosses_threshold(imp("C-042", "C-048", "C-050"))


def test_refresh_status_records_detection_once(conn, customers):
    yes = Recorder(yes=["Garrido"])
    for i, c in enumerate(["C-019", "C-022", "C-025", "C-028"]):
        s = stored(conn, signal(f"R-{i}", customer=c, day=i))
        problems.assign(conn, s, matcher=yes)
        status = problems.refresh_status(conn, "P-0001", customers, s.created_at)
    row = conn.execute("SELECT * FROM problems WHERE id = 'P-0001'").fetchone()
    assert status == "candidate"
    assert row["detected_at_n"] == 3  # the third distinct customer crossed it
    events = [r["kind"] for r in conn.execute("SELECT kind FROM problem_events WHERE problem_id = 'P-0001'")]
    assert events.count("threshold") == 1


def test_backfill_replays_in_time_order_and_skips_done_tickets(conn, customers):
    tickets = [TicketIn(id=f"R-{i}", customer_id=c, channel="email", created_at=T0 + timedelta(days=d),
                        subject="Garrido", body="El OCR no lee el total") for i, (c, d) in
               enumerate([("C-019", 3), ("C-022", 1), ("C-025", 2)])]

    def extractor(ticket, customer, gazetteer, classification=None):
        return signal(ticket.id, customer=ticket.customer_id, day=(ticket.created_at - T0).days)

    order = []
    radar.backfill(conn, tickets, customers, workers=2, extractor=extractor, matcher=Recorder(yes=["Garrido"]),
                   progress=lambda n, s: order.append(s.ticket_id))
    assert order == ["R-1", "R-2", "R-0"]
    assert db.list_tickets(conn) == []  # history never shows in the queue
    assert radar.backfill(conn, tickets, customers, extractor=extractor, matcher=Recorder()) == []
    assert conn.execute("SELECT status FROM problems").fetchone()[0] == "candidate"


def test_gazetteer_is_built_from_the_customers(customers):
    g = Gazetteer.from_customers(customers)
    assert g.suppliers["garrido"] == "Distribuciones Garrido"
    assert g.banks["kutxabank"] == "Kutxabank"
    assert g.pos["revo"] == "Revo"


def test_yes_to_two_problems_merges_them_into_the_bigger(conn):
    problems.assign(conn, stored(conn, signal("R-1")), matcher=Recorder())
    problems.assign(conn, stored(conn, signal("R-2")), matcher=Recorder(yes=["Garrido"]))
    problems.assign(conn, stored(conn, signal("R-3")), matcher=Recorder(yes=[]))  # weak answer: split
    assert conn.execute("SELECT COUNT(*) FROM problems WHERE status = 'open'").fetchone()[0] == 2
    pid = problems.assign(conn, stored(conn, signal("R-4")), matcher=Recorder(yes=["Garrido"]))
    assert pid == "P-0001"
    row = conn.execute("SELECT status, merged_into FROM problems WHERE id = 'P-0002'").fetchone()
    assert tuple(row) == ("merged", "P-0001")
    assert {r[0] for r in conn.execute("SELECT problem_id FROM signals")} == {"P-0001"}
    assert db.get_ticket(conn, "R-3")["problem_id"] == "P-0001"


def test_a_problem_with_an_issue_survives_a_merge(conn):
    problems.assign(conn, stored(conn, signal("R-1")), matcher=Recorder())
    problems.assign(conn, stored(conn, signal("R-2")), matcher=Recorder(yes=["Garrido"]))
    problems.assign(conn, stored(conn, signal("R-3")), matcher=Recorder(yes=[]))
    conn.execute("UPDATE problems SET status = 'requested' WHERE id = 'P-0002'")
    assert problems.assign(conn, stored(conn, signal("R-4")), matcher=Recorder(yes=["Garrido"])) == "P-0002"


def test_candidates_cross_components_of_one_area_or_one_entity(conn):
    problems.assign(conn, stored(conn, signal("R-1")), matcher=Recorder())  # invoices.ocr, Garrido
    same_area = Recorder(yes=["Garrido"])
    assert problems.assign(conn, stored(conn, signal("R-2", component=Component.invoices_suppliers)),
                           matcher=same_area) == "P-0001"
    problems.assign(conn, stored(conn, signal("R-3", component=Component.pos_sales, entity="Revo",
                                              symptom="Revo duplica ventas")), matcher=Recorder())
    same_entity = Recorder(yes=["Revo"])
    assert problems.assign(conn, stored(conn, signal("R-4", component=Component.reports_pnl, entity="Revo",
                                                     symptom="El P&L infla las ventas")),
                           matcher=same_entity) == "P-0002"


def test_a_bug_is_never_matched_with_a_feature(conn):
    problems.assign(conn, stored(conn, signal("R-1", kind=Kind.feature)), matcher=Recorder())
    matcher = Recorder(yes=["Garrido"])
    assert problems.assign(conn, stored(conn, signal("R-2")), matcher=matcher) != "P-0001"
    assert matcher.asked == []


def test_without_entity_only_the_same_component_is_a_candidate(conn):
    problems.assign(conn, stored(conn, signal("R-1", component=Component.reports_pnl, entity="Revo",
                                              symptom="El P&L infla las ventas de Revo")), matcher=Recorder())
    matcher = Recorder(yes=["P&L"])
    problems.assign(conn, stored(conn, signal("R-2", component=Component.reports_export, entity=None,
                                              symptom="El Excel del P&L suma el IVA")), matcher=matcher)
    assert matcher.asked == []


def test_component_and_entity_follow_the_majority(conn):
    yes = Recorder(yes=["Garrido"])
    problems.assign(conn, stored(conn, signal("R-1", component=Component.invoices_suppliers)), matcher=yes)
    for i in (2, 3):
        problems.assign(conn, stored(conn, signal(f"R-{i}")), matcher=yes)
    row = conn.execute("SELECT component, entity FROM problems WHERE id = 'P-0001'").fetchone()
    assert tuple(row) == ("invoices.ocr", "Distribuciones Garrido")
