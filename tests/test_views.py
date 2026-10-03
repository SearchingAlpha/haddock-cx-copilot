"""Presentation helpers: docs/specs/ui.md."""

import json
from datetime import datetime

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
    assert items[0]["title"] == "Makro · 842,30 €"
    assert {i["id"] for i in items} == {"F-0101", "kb-02"}


def test_reason_view_marks_blocking():
    [r] = reason_view(["refund_promise"])
    assert r["blocking"] and r["label"] == "Promete un reembolso"
