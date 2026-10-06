"""CX agent workstation: inbox, review, impact metrics, webhook. Spec: docs/specs/ui.md.

    python -m uv run uvicorn app.main:app --reload   ->  http://localhost:8000
"""

import base64
import logging
import os
import secrets
import time
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import BackgroundTasks, FastAPI, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from langfuse import get_client

from app import db, problems, radar, story, tour, views
from app.data import load_customers, load_kb, load_tickets
from app.domain import Category, TicketIn
from app.entities import Gazetteer
from app.observability import init_tracing
from app.pipeline import process_ticket
from app.tools import KBIndex

log = logging.getLogger(__name__)
templates = Jinja2Templates(directory=Path(__file__).parent / "templates")
CUSTOMERS = load_customers()
KB = KBIndex(load_kb())
GAZETTEER = Gazetteer.from_customers(CUSTOMERS)


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_tracing()
    yield
    try:
        get_client().flush()
    except Exception:
        pass


app = FastAPI(title="haddock CX copilot", lifespan=lifespan)
app.mount("/static", StaticFiles(directory=Path(__file__).parent / "static"), name="static")


# --- public demo: docs/specs/deploy.md --------------------------------------------------------

def is_public() -> bool:
    """HADDOCK_PUBLIC=1: no pipeline, so nobody spends tokens on the public URL."""
    return os.environ.get("HADDOCK_PUBLIC") == "1"


def _authorized(header: str | None, password: str) -> bool:
    if not header or not header.startswith("Basic "):
        return False
    try:
        _, _, given = base64.b64decode(header[6:]).decode().partition(":")
    except ValueError:
        return False
    return secrets.compare_digest(given.encode(), password.encode())


@app.middleware("http")
async def basic_auth(request: Request, call_next):
    """DEMO_PASSWORD set: every page asks for it. Any user name works."""
    password = os.environ.get("DEMO_PASSWORD")
    if password and not request.url.path.startswith("/static/")             and not _authorized(request.headers.get("Authorization"), password):
        return Response(status_code=401, headers={"WWW-Authenticate": 'Basic realm="haddock demo"'})
    return await call_next(request)


# --- pipeline in the background --------------------------------------------------------------

def run_pipeline(ticket: TicketIn) -> None:
    result = process_ticket(ticket, CUSTOMERS, kb=KB)
    conn = db.connect()
    try:
        db.save_result(conn, result)
    finally:
        conn.close()
    radar_step(ticket, result)


def radar_step(ticket: TicketIn, result) -> None:
    """After the reply is ready: the ticket feeds the product radar (docs/specs/radar.md). Never blocks the reply."""
    conn = db.connect()
    try:
        radar.ingest(conn, ticket, CUSTOMERS, GAZETTEER, classification=result.classification)
    except Exception as error:
        log.warning("radar failed for %s: %r", ticket.id, error)
    finally:
        conn.close()


def accept(ticket: TicketIn, background: BackgroundTasks) -> str:
    if is_public():
        raise HTTPException(403, "Public demo: the pipeline is off.")
    if ticket.customer_id not in CUSTOMERS:
        raise HTTPException(404, f"unknown customer {ticket.customer_id}")
    conn = db.connect()
    try:
        mode = db.insert_ticket(conn, ticket)
    except ValueError as error:
        raise HTTPException(409, str(error)) from error
    finally:
        conn.close()
    background.add_task(run_pipeline, ticket)
    return mode


@app.post("/webhooks/ticket", status_code=202)
def webhook(ticket: TicketIn, background: BackgroundTasks) -> dict:
    """Zendesk-style entry point: store, answer 202 at once, process in the background."""
    return {"ticket_id": ticket.id, "mode": accept(ticket, background), "state": "processing"}


@app.post("/demo/load")
def demo_load(background: BackgroundTasks, n: int = 5) -> RedirectResponse:
    """Feed n tickets from data/tickets.jsonl through the same path as the webhook."""
    if is_public():
        raise HTTPException(403, "Public demo: the pipeline is off.")
    conn = db.connect()
    known = {t["id"] for t in db.list_tickets(conn)}
    conn.close()
    for t in [t for t in load_tickets() if t.id not in known][:n]:
        accept(TicketIn(**t.model_dump(exclude={"labels"})), background)
    return RedirectResponse("/", status_code=303)


# --- pages -----------------------------------------------------------------------------------

def _shell(selected: str | None = None) -> dict:
    """Context shared by every page: the queue column and the J/K neighbours of the selected ticket."""
    conn = db.connect()
    tickets = db.list_tickets(conn)
    conn.close()
    for t in tickets:
        t["customer"] = CUSTOMERS[t["customer_id"]].name
        t["age"] = views.age(t["created_at"])
    order = views.queue_order(tickets)
    pos = order.index(selected) if selected in order else -1
    if pos >= 0:
        next_id = order[pos + 1] if pos < len(order) - 1 else None
    else:
        next_id = order[0] if order else None
    return {
        "groups": views.queue_groups(tickets),
        "selected": selected,
        "processing": any(t["state"] == "processing" for t in tickets),
        "pending": len(order),
        "public": is_public(),
        "prev_id": order[pos - 1] if pos > 0 else None,
        "next_id": next_id,
        "labels": {"state": views.STATE_LABELS, "priority": views.PRIORITY_LABELS,
                   "value": views.VALUE_LABELS, "team": views.TEAM_LABELS, "status": views.STATUS_LABELS},
    }


@app.get("/", response_class=HTMLResponse)
def home(request: Request):
    return templates.TemplateResponse(request, "home.html", _shell())


@app.get("/intro", response_class=HTMLResponse)
def intro(request: Request):
    return templates.TemplateResponse(request, "story.html", {"story": story.INTRO})


@app.get("/presentacion", response_class=HTMLResponse)
def presentation(request: Request):
    return templates.TemplateResponse(request, "story.html", {"story": story.PRESENTATION})


@app.get("/codigo", response_class=HTMLResponse)
def code_tour(request: Request):
    stops = [(stop, [tour.resolve(e) for e in stop.excerpts]) for stop in tour.TOUR]
    return templates.TemplateResponse(request, "tour.html", {"stops": stops})


@app.get("/queue", response_class=HTMLResponse)
def queue(request: Request, selected: str | None = None):
    """HTMX partial: the queue column polls it while tickets are processing."""
    return templates.TemplateResponse(request, "_queue.html", _shell(selected))


@app.get("/tickets/{ticket_id}", response_class=HTMLResponse)
def ticket_page(request: Request, ticket_id: str):
    conn = db.connect()
    ticket = db.get_ticket(conn, ticket_id)
    problem = conn.execute("SELECT id, title, status FROM problems WHERE id = ?",
                           ((ticket or {}).get("problem_id"),)).fetchone()
    conn.close()
    if ticket is None:
        raise HTTPException(404)
    return templates.TemplateResponse(request, "ticket.html", {
        "problem": dict(problem) if problem else None, "problem_status": views.PROBLEM_STATUS_LABELS,
        **_shell(ticket_id),
        "t": ticket,
        "customer": CUSTOMERS[ticket["customer_id"]],
        "categories": [c.value for c in Category],
        "trace_url": _trace_url(ticket.get("trace_id")),
        "opened_at": time.time(),
        "ticket_age": views.age(ticket["created_at"]),
        "reply_html": views.render_reply(ticket.get("draft")),
        "evidence": views.evidence_items(ticket),
        "reasons": views.reason_view(ticket.get("reasons")),
        "manual": ticket["mode"] == "manual" or not ticket.get("draft"),
        "blocking": bool(views.BLOCKING & set(ticket.get("reasons") or [])),
    })


@app.post("/tickets/{ticket_id}/review")
def review(ticket_id: str, decision: str = Form(...), final_text: str = Form(""),
           opened_at: float = Form(...), category_final: str = Form(None)) -> RedirectResponse:
    conn = db.connect()
    try:
        ticket = db.get_ticket(conn, ticket_id)
        if ticket is None:
            raise HTTPException(404)
        if decision != "reject":  # the server decides approve vs edit: did the text change?
            if not final_text.strip():
                raise HTTPException(422, "Empty reply: write the answer before sending.")
            if ticket["mode"] == "manual" or not ticket.get("draft"):
                decision = "manual"
            else:
                decision = "approve" if final_text.strip() == ticket["draft"].strip() else "edit"
            if decision == "approve" and views.BLOCKING & set(ticket.get("reasons") or []):
                raise HTTPException(409, "Blocked by guardrails: edit the draft before sending.")
        seconds = max(0.0, time.time() - opened_at)
        saved = db.record_review(conn, ticket_id, decision, final_text, seconds, category_final)
    finally:
        conn.close()
    send_scores(ticket.get("trace_id"), saved)
    next_id = _shell()["next_id"]  # first pending ticket in queue order
    return RedirectResponse(f"/tickets/{next_id}" if next_id else "/", status_code=303)


@app.get("/metrics", response_class=HTMLResponse)
def metrics_page(request: Request):
    conn = db.connect()
    m = db.metrics(conn)
    conn.close()
    return templates.TemplateResponse(request, "metrics.html", {**_shell(), "m": m})


# --- product radar: docs/specs/radar.md -----------------------------------------------------

@app.get("/radar", response_class=HTMLResponse)
def radar_page(request: Request):
    conn = db.connect()
    try:
        found = problems.list_problems(conn, CUSTOMERS)
        signals = conn.execute("SELECT COUNT(*) FROM signals").fetchone()[0]
    finally:
        conn.close()
    shown = [p for p in found if views.shown_on_radar(p)]
    return templates.TemplateResponse(request, "radar.html", {
        **_shell(), "problems": shown, "hidden": len(found) - len(shown), "signals": signals,
        "candidates": sum(1 for p in shown if p["status"] == "candidate"),
        "graph": views.radar_graph(found, CUSTOMERS), "v": views,
    })


@app.get("/radar/graph.json")
def radar_graph_json() -> dict:
    conn = db.connect()
    try:
        return views.radar_graph(problems.list_problems(conn, CUSTOMERS), CUSTOMERS)
    finally:
        conn.close()


@app.get("/radar/problems/{problem_id}", response_class=HTMLResponse)
def problem_page(request: Request, problem_id: str):
    conn = db.connect()
    try:
        p = problems.get_problem(conn, problem_id, CUSTOMERS)
    finally:
        conn.close()
    if p is None:
        raise HTTPException(404)
    return templates.TemplateResponse(request, "problem.html", {
        **_shell(), "p": p, "customers": CUSTOMERS, "v": views,
        "threshold": next((e for e in p["events"] if e["kind"] == "threshold"), None),
    })


# --- Langfuse --------------------------------------------------------------------------------

def send_scores(trace_id: str | None, review: dict) -> None:
    """Human feedback on the pipeline trace: the bridge between production and evals."""
    if not trace_id:
        return
    try:
        langfuse = get_client()
        langfuse.create_score(trace_id=trace_id, name="human_decision", value=review["decision"],
                              data_type="CATEGORICAL")
        langfuse.create_score(trace_id=trace_id, name="edit_distance", value=review["edit_distance"])
        langfuse.create_score(trace_id=trace_id, name="review_seconds", value=review["review_seconds"])
        if review["category_final"]:
            langfuse.create_score(trace_id=trace_id, name="category_final", value=review["category_final"],
                                  data_type="CATEGORICAL")
    except Exception as error:  # the review is already in SQLite; never lose it for telemetry
        log.warning("Langfuse scores failed for %s: %r", trace_id, error)


def _trace_url(trace_id: str | None) -> str | None:
    if not trace_id:
        return None
    try:
        return get_client().get_trace_url(trace_id=trace_id)
    except Exception:
        return None
