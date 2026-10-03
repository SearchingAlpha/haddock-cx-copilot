"""Presentation logic for the workstation templates. Spec: docs/specs/ui.md. Pure functions, unit-tested."""

import json
import re
from datetime import datetime
from html import escape

from markupsafe import Markup

QUEUE_GROUPS = [  # (state, label): what needs a decision first, done work last
    ("escalated", "Escalados"),
    ("ready", "Listos para revisar"),
    ("processing", "En proceso"),
    ("sent", "Enviados"),
    ("rejected", "Rechazados"),
]
STATE_LABELS = {"processing": "En proceso", "ready": "Listo", "escalated": "Escalado",
                "sent": "Enviado", "rejected": "Rechazado"}
PRIORITY_LABELS = {"urgent": "Urgente", "high": "Alta", "normal": "Normal", "low": "Baja"}
VALUE_LABELS = {
    "priority": PRIORITY_LABELS,
    "sentiment": {"positive": "Positivo", "neutral": "Neutral", "negative": "Negativo",
                  "very_negative": "Muy negativo"},
    "language": {"es": "Español", "ca": "Catalán", "en": "Inglés"},
}
TEAM_LABELS = {"finance": "Finanzas", "tech": "Técnico", "support": "Soporte"}
STATUS_LABELS = {  # raw data statuses as the CX agent reads them
    "ok": "conectado", "error": "error", "disconnected": "desconectado", "failed": "fallido",
    "processed": "procesada", "processing": "procesando", "duplicate": "duplicada",
}


def status_label(value: str | None) -> str:
    return STATUS_LABELS.get(value, value or "—")
REASON_LABELS = {
    "agent_escalated": "El agente pidió escalar",
    "refund_promise": "Promete un reembolso",
    "deadline_promise": "Promete un plazo",
    "other_customer_data": "Menciona datos de otro cliente",
    "promise_check_failed": "No se pudo verificar si promete algo",
    "no_draft": "Sin borrador",
    "low_agent_confidence": "El agente tiene poca confianza",
    "pipeline_error": "Error del pipeline",
}
BLOCKING = {"refund_promise", "deadline_promise", "other_customer_data"}


def render_reply(text: str | None) -> Markup:
    """The draft as the customer reads it: escaped first, then **bold**, lists and paragraphs."""
    if not text:
        return Markup("")
    blocks, current_list, list_tag = [], [], None

    def flush_list():
        nonlocal current_list, list_tag
        if current_list:
            blocks.append(f"<{list_tag}>" + "".join(f"<li>{i}</li>" for i in current_list) + f"</{list_tag}>")
        current_list, list_tag = [], None

    for paragraph in re.split(r"\n\s*\n", escape(text.strip())):
        for line in paragraph.split("\n"):
            line = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", line.strip())
            heading = re.match(r"^#{1,4}\s+(.*)", line)
            numbered, bullet = re.match(r"^\d+[.)]\s+(.*)", line), re.match(r"^[-•]\s+(.*)", line)
            if heading:
                flush_list()
                blocks.append(f"<p><strong>{heading.group(1)}</strong></p>")
            elif numbered or bullet:
                tag = "ol" if numbered else "ul"
                if list_tag and list_tag != tag:
                    flush_list()
                list_tag = tag
                current_list.append((numbered or bullet).group(1))
            elif line:
                flush_list()
                blocks.append(f"<p>{line}</p>")
        flush_list()
    return Markup("".join(blocks))


def age(created_at: str | None, now: datetime | None = None) -> str:
    if not created_at:
        return ""
    delta = (now or datetime.now()) - datetime.fromisoformat(created_at)
    minutes = int(delta.total_seconds() // 60)
    if minutes < 60:
        return f"{max(minutes, 1)} min"
    if minutes < 60 * 24:
        return f"{minutes // 60} h"
    return f"{minutes // (60 * 24)} d"


def queue_groups(tickets: list[dict]) -> list[dict]:
    order = {"urgent": 0, "high": 1, "normal": 2, "low": 3}
    groups = []
    for state, label in QUEUE_GROUPS:
        items = [t for t in tickets if t["state"] == state]
        items.sort(key=lambda t: (order.get((t.get("classification") or {}).get("priority"), 4), t["created_at"]))
        if items:
            groups.append({"state": state, "label": label, "tickets": items,
                           "collapsed": state in ("sent", "rejected")})
    return groups


def queue_order(tickets: list[dict]) -> list[str]:
    """J/K navigation order: the pending tickets as the queue shows them."""
    return [t["id"] for g in queue_groups(tickets) if not g["collapsed"] for t in g["tickets"]]


def _parse(text):
    try:
        return json.loads(text)
    except (TypeError, ValueError):
        return text


def evidence_items(ticket: dict) -> list[dict]:
    """What the agent read, grouped for the context panel; `cited` marks what the draft relies on."""
    cited = set(ticket.get("evidence") or [])
    articles, invoices, banks, profile = {}, {}, None, None
    for call in ticket.get("tool_outputs") or []:
        out = _parse(call.get("output"))
        if call["tool"] == "search_kb" and isinstance(out, list):
            for a in out:
                articles.setdefault(a["id"], a)
        elif call["tool"] == "get_invoices" and isinstance(out, list):
            for inv in out:
                invoices.setdefault(inv["id"], inv)
        elif call["tool"] == "get_bank_sync_status" and isinstance(out, list):
            banks = out
        elif call["tool"] == "get_customer" and isinstance(out, dict):
            profile = out

    items = []
    for inv in invoices.values():
        items.append({"kind": "Factura", "id": inv["id"], "cited": inv["id"] in cited,
                      "title": f'{inv["supplier"]} · ' + f'{inv["amount_eur"]:,.2f}'.replace(",", "X").replace(".", ",").replace("X", ".") + " €",
                      "detail": status_label(inv["status"]).capitalize() + (f' · {inv["error"]}' if inv.get("error") else ""),
                      "risk": inv["status"] in ("failed", "duplicate")})
    for b in banks or []:
        items.append({"kind": "Banco", "id": "bank_sync", "cited": "bank_sync" in cited,
                      "title": f'{b["provider"]} · {status_label(b["status"])}',
                      "detail": b.get("error") or f'Última sincronización {b.get("last_sync") or "—"}',
                      "risk": b["status"] != "ok"})
    if profile:
        items.append({"kind": "Cliente", "id": "customer", "cited": "customer" in cited,
                      "title": f'Plan {profile["plan"]} · pago {"al día" if profile["billing"]["payment_status"] == "ok" else status_label(profile["billing"]["payment_status"])}',
                      "detail": ", ".join(f'{i["provider"]}: {status_label(i["status"])}' for i in profile.get("integrations", []))
                                or "Sin integraciones",
                      "risk": profile["billing"]["payment_status"] != "ok"})
    for a in articles.values():
        items.append({"kind": "Ayuda", "id": a["id"], "cited": a["id"] in cited, "title": a["title"],
                      "detail": render_reply(a["text"]), "risk": False})
    items.sort(key=lambda i: not i["cited"])  # what the draft relies on comes first
    return items


def reason_view(reasons: list[str] | None) -> list[dict]:
    return [{"code": r, "label": REASON_LABELS.get(r, r), "blocking": r in BLOCKING} for r in reasons or []]
