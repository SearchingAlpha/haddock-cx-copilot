"""Presentation helpers: docs/specs/ui.md."""

import json
from datetime import datetime

from app import views
from app.problems import Impact
from app.views import age, evidence_items, queue_groups, queue_order, reason_view, render_reply


def test_render_reply_escapes_html_before_formatting():
    html = str(render_reply("Hola <script>alert(1)</script> **Ajustes**"))
    assert "<script>" not in html
    assert "&lt;script&gt;" in html
    assert "<strong>Ajustes</strong>" in html


def test_render_reply_lists_and_paragraphs():
    html = str(render_reply("Hola Marta:\n\n1. Abre Ajustes.\n2. Pulsa Guardar.\n\nUn saludo"))
    assert html == "<p>Hola Marta:</p><ol><li>Abre Ajustes.</li><li>Pulsa Guardar.</li></ol><p>Un saludo</p>"


def test_age():
    now = datetime(2026, 10, 3, 12, 0)
    assert age("2026-10-03T11:30:00", now) == "30 min"
    assert age("2026-10-03T07:00:00", now) == "5 h"
    assert age("2026-09-30T12:00:00", now) == "3 d"


def ticket(id, state, priority="normal", created="2026-10-01T09:00:00"):
    return {"id": id, "state": state, "created_at": created, "classification": {"priority": priority}}


def test_queue_puts_escalated_first_and_urgent_on_top():
    tickets = [ticket("A", "ready"), ticket("B", "escalated"), ticket("C", "ready", "urgent"),
               ticket("D", "sent")]
    groups = queue_groups(tickets)
    assert [g["state"] for g in groups] == ["escalated", "ready", "sent"]
    assert [t["id"] for t in groups[1]["tickets"]] == ["C", "A"]
    assert groups[2]["collapsed"]
    assert queue_order(tickets) == ["B", "C", "A"]


def test_evidence_items_parse_tool_outputs_and_put_cited_first():
    t = {"evidence": ["F-0101"], "tool_outputs": [
        {"tool": "search_kb", "input": {}, "output": json.dumps([{"id": "kb-02", "title": "Procesando", "text": "x"}])},
        {"tool": "get_invoices", "input": {}, "output": json.dumps([
            {"id": "F-0101", "supplier": "Makro", "amount_eur": 842.3, "status": "processing"}])},
    ]}
    items = evidence_items(t)
    assert items[0]["id"] == "F-0101" and items[0]["cited"]
    assert items[0]["title"] == "Makro · 842,30 €"  # non-breaking space: the € never wraps alone
    assert {i["id"] for i in items} == {"F-0101", "kb-02"}


def test_reason_view_marks_blocking():
    [r] = reason_view(["refund_promise"])
    assert r["blocking"] and r["label"] == "Promete un reembolso"


# --- radar: docs/specs/ui.md (Radar) --------------------------------------------------------



def _problem(pid, component, status="candidate", by_customer=None, score=100.0, tickets=None):
    by_customer = by_customer or {"C-001": 1, "C-002": 1}
    imp = Impact(tickets or sum(by_customer.values()), sorted(by_customer), 200.0, 0.5, 1.0, score, [0, 1, 2])
    return {"id": pid, "title": f"Problema {pid}", "component": component, "status": status, "kind": "bug",
            "impact": imp, "by_customer": by_customer}


def test_money_uses_spanish_thousands():
    assert views.money(1839.0) == "1.839 €"
    assert views.money(None) == "—"


def test_sparkline_is_svg_with_an_accessible_label():
    svg = str(views.sparkline([0, 3, 1]))
    assert svg.startswith("<svg") and 'aria-label="Tickets por semana: 0, 3, 1"' in svg


def test_trend_labels():
    assert views.trend_label(2.0) == "↑ sube" and views.trend_label(0.5) == "↓ baja"
    assert views.trend_label(1.0) == "→ estable"


def test_one_ticket_problems_stay_off_the_radar():
    assert not views.shown_on_radar(_problem("P-1", "other", status="open", by_customer={"C-001": 1}))
    assert views.shown_on_radar(_problem("P-2", "other", status="open"))
    assert not views.shown_on_radar(_problem("P-3", "other", status="merged"))


def test_radar_graph_has_three_columns_and_marks_shared_customers():
    from app.data import load_customers
    customers = load_customers()
    problems = [_problem("P-1", "invoices.ocr", by_customer={"C-001": 2, "C-002": 1}),
                _problem("P-2", "bank.sync", status="open", by_customer={"C-002": 1, "C-003": 1}, score=10)]
    g = views.radar_graph(problems, customers)
    xs = {n["data"]["kind"]: n["position"]["x"] for n in g["nodes"]}
    assert xs["area"] < xs["problem"] < xs["customer"]
    shared = next(n for n in g["nodes"] if n["data"]["id"] == "c:C-002")
    assert "multi" in shared["classes"] and g["multi"] == 1
    edge = next(e for e in g["edges"] if e["data"]["id"] == "e:P-1:C-001")
    assert edge["data"]["width"] == 3  # 1 + tickets
    assert views.radar_graph(problems, customers) == g  # deterministic: the graph never jumps


def test_radar_graph_orders_areas_like_the_categories():
    from app.data import load_customers
    problems = [_problem("P-1", "reports.pnl"), _problem("P-2", "invoices.ocr")]
    g = views.radar_graph(problems, load_customers())
    areas = [n for n in g["nodes"] if n["data"]["kind"] == "area"]
    assert [a["data"]["label"] for a in sorted(areas, key=lambda a: a["position"]["y"])] == ["Facturas", "Informes"]
