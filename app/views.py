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


# --- product radar: docs/specs/ui.md (Radar) --------------------------------------------------

AREA_LABELS = {"invoices": "Facturas", "bank": "Banco", "pos": "TPV", "inventory": "Inventario",
               "reports": "Informes", "account": "Cuenta", "other": "Otros"}
PROBLEM_STATUS_LABELS = {"open": "Abierto", "candidate": "Para pedir a producto", "requested": "En producto",
                         "resolved": "Resuelto", "dismissed": "Descartado", "merged": "Unido"}
KIND_LABELS = {"bug": "Fallo", "feature": "Petición de función", "how_to": "Duda", "user_error": "Error del cliente"}
EVENT_LABELS = {"opened": "Primer ticket", "ticket_added": "Ticket nuevo", "threshold": "Cruzó el umbral",
                "merged": "Unido", "requested": "Issue creada", "commented": "Comentario en la issue",
                "resolved": "Issue cerrada", "dismissed": "Descartado", "reopened": "Issue reabierta",
                "notices": "Avisos proactivos en la cola"}
# DESIGN.md: amber = check this, red = risk, rail teal = in product's hands, neutral = done. No green.
STATUS_COLORS = {"candidate": "#e38215", "requested": "#03363d", "resolved": "#8aa6b5",
                 "dismissed": "#d8dcde", "open": "#aeb8bd"}
TOP, ROW_H = 20, 22
GRAPH_X = {"area": 70, "problem": 380, "customer": 760}


def money(value: float | None) -> str:
    """1839.0 -> '1.839 €' (Spanish thousands separator, no decimals)."""
    if value is None:
        return "—"
    return f"{value:,.0f}".replace(",", ".") + " €"


def area_of(component: str) -> str:
    return component.split(".")[0]


def sparkline(weekly: list[int], width: int = 84, height: int = 22) -> Markup:
    """Inline SVG of tickets per week; the last point is the current week."""
    if not weekly:
        return Markup("")
    top = max(max(weekly), 1)
    step = width / max(len(weekly) - 1, 1)
    points = [(round(i * step, 1), round(height - 2 - (v / top) * (height - 4), 1)) for i, v in enumerate(weekly)]
    path = " ".join(f"{x},{y}" for x, y in points)
    x, y = points[-1]
    label = ", ".join(str(v) for v in weekly)
    return Markup(
        f'<svg class="spark" width="{width}" height="{height}" viewBox="0 0 {width} {height}" role="img" '
        f'aria-label="Tickets por semana: {label}"><polyline points="{path}" fill="none" stroke="#5c6970" '
        f'stroke-width="1.5" stroke-linejoin="round"/><circle cx="{x}" cy="{y}" r="2.5" fill="#17202a"/></svg>')


def trend_label(trend: float) -> str:
    if trend >= 1.25:
        return "↑ sube"
    if trend <= 0.8:
        return "↓ baja"
    return "→ estable"


def shown_on_radar(p: dict) -> bool:
    """One ticket in an open problem is not a pattern yet: the graph shows it only from 2 tickets."""
    return p["status"] != "merged" and (p["impact"].tickets >= 2 or p["status"] != "open")


def _short(text: str, n: int = 52) -> str:
    return text if len(text) <= n else text[: n - 1].rstrip() + "…"


def radar_graph(problems: list[dict], customers: dict) -> dict:
    """Nodes and edges for cytoscape with fixed positions: areas | problems | customers.

    Deterministic, so the graph never jumps. Each problem gets a band of rows as tall as its number of
    customers, and its customers sit in that band (ordered by the mean height of their problems), so edges
    stay short. A customer in two problems or more gets the `multi` class.
    """
    shown = [p for p in problems if shown_on_radar(p)]
    shown.sort(key=lambda p: (list(AREA_LABELS).index(area_of(p["component"])), -p["impact"].score, p["id"]))
    nodes, edges, y_problem = [], [], {}
    cursor, last_area = 0.0, None
    for p in shown:
        if last_area is not None and area_of(p["component"]) != last_area:
            cursor += 1  # one empty row between areas
        rows = max(len(p["by_customer"]), 1)
        y_problem[p["id"]] = TOP + (cursor + rows / 2) * ROW_H
        cursor += rows
        last_area = area_of(p["component"])
    height = TOP * 2 + cursor * ROW_H

    for a in dict.fromkeys(area_of(p["component"]) for p in shown):
        ys = [y_problem[p["id"]] for p in shown if area_of(p["component"]) == a]
        nodes.append({"data": {"id": f"area:{a}", "label": AREA_LABELS[a], "kind": "area"},
                      "position": {"x": GRAPH_X["area"], "y": round((min(ys) + max(ys)) / 2, 1)}, "classes": "area"})

    links: dict[str, list[str]] = {}
    max_score = max((p["impact"].score for p in shown), default=1) or 1
    for p in shown:
        imp = p["impact"]
        nodes.append({"data": {"id": p["id"], "label": _short(p["title"]), "kind": "problem",
                               "status": p["status"], "color": STATUS_COLORS.get(p["status"], "#aeb8bd"),
                               "size": round(14 + 26 * (imp.score / max_score) ** 0.5, 1),
                               "tickets": imp.tickets, "customers": len(imp.customers), "mrr": money(imp.mrr_eur),
                               "href": f"/radar/problems/{p['id']}"},
                      "position": {"x": GRAPH_X["problem"], "y": round(y_problem[p["id"]], 1)},
                      "classes": f"problem {p['status']}"})
        edges.append({"data": {"id": f"e:area:{p['id']}", "source": f"area:{area_of(p['component'])}",
                               "target": p["id"], "width": 1}})
        for cid, n in sorted(p["by_customer"].items()):
            links.setdefault(cid, []).append(p["id"])
            edges.append({"data": {"id": f"e:{p['id']}:{cid}", "source": p["id"], "target": f"c:{cid}",
                                   "width": min(1 + n, 5)}})

    order = sorted(links, key=lambda c: (sum(y_problem[p] for p in links[c]) / len(links[c]), c))
    step = (height - 2 * TOP) / max(len(order), 1)
    for i, cid in enumerate(order):
        c = customers.get(cid)
        nodes.append({"data": {"id": f"c:{cid}", "label": c.name if c else cid, "kind": "customer",
                               "plan": c.plan if c else "", "mrr": money(c.billing.monthly_price_eur) if c else "",
                               "problems": len(links[cid])},
                      "position": {"x": GRAPH_X["customer"], "y": round(TOP + (i + 0.5) * step, 1)},
                      "classes": "customer multi" if len(links[cid]) > 1 else "customer"})
    return {"nodes": nodes, "edges": edges, "height": round(height), "multi": sum(1 for c in links if len(links[c]) > 1)}
