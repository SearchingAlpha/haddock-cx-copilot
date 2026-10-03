"""CX agent workstation: inbox, review, impact metrics, webhook. Spec: docs/specs/ui.md.

    python -m uv run uvicorn app.main:app --reload   ->  http://localhost:8000
"""

import logging
import time
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import BackgroundTasks, FastAPI, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from langfuse import get_client

from app import db
from app.data import load_customers, load_kb, load_tickets
from app.domain import Category, TicketIn
from app.observability import init_tracing
from app.pipeline import process_ticket
from app.tools import KBIndex

log = logging.getLogger(__name__)
templates = Jinja2Templates(directory=Path(__file__).parent / "templates")
CUSTOMERS = load_customers()
KB = KBIndex(load_kb())
PENDING = ("ready", "escalated")


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_tracing()
    yield
    try:
        get_client().flush()
    except Exception:
        pass


app = FastAPI(title="haddock CX copilot", lifespan=lifespan)


# --- pipeline in the background --------------------------------------------------------------

def run_pipeline(ticket: TicketIn) -> None:
    result = process_ticket(ticket, CUSTOMERS, kb=KB)
    conn = db.connect()
    try:
        db.save_result(conn, result)
    finally:
        conn.close()


def accept(ticket: TicketIn, background: BackgroundTasks) -> str:
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
    conn = db.connect()
    known = {t["id"] for t in db.list_tickets(conn)}
    conn.close()
    for t in [t for t in load_tickets() if t.id not in known][:n]:
        accept(TicketIn(**t.model_dump(exclude={"labels"})), background)
    return RedirectResponse("/", status_code=303)


# --- pages -----------------------------------------------------------------------------------

@app.get("/", response_class=HTMLResponse)
def inbox(request: Request):
    return templates.TemplateResponse(request, "inbox.html", _inbox_context())


@app.get("/rows", response_class=HTMLResponse)
def rows(request: Request):
    """HTMX partial: the inbox polls it while tickets are processing."""
    return templates.TemplateResponse(request, "_rows.html", _inbox_context())


def _inbox_context() -> dict:
    conn = db.connect()
    tickets = db.list_tickets(conn)
    conn.close()
    for t in tickets:
        t["customer"] = CUSTOMERS[t["customer_id"]].name
    return {"tickets": tickets, "processing": any(t["state"] == "processing" for t in tickets)}


@app.get("/tickets/{ticket_id}", response_class=HTMLResponse)
def ticket_page(request: Request, ticket_id: str):
    conn = db.connect()
    ticket = db.get_ticket(conn, ticket_id)
    conn.close()
    if ticket is None:
        raise HTTPException(404)
    return templates.TemplateResponse(request, "ticket.html", {
        "t": ticket,
        "customer": CUSTOMERS[ticket["customer_id"]],
        "categories": [c.value for c in Category],
        "trace_url": _trace_url(ticket.get("trace_id")),
        "opened_at": time.time(),
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
            if ticket["mode"] == "manual" or not ticket.get("draft"):
                decision = "manual"
            else:
                decision = "approve" if final_text.strip() == ticket["draft"].strip() else "edit"
        seconds = max(0.0, time.time() - opened_at)
        saved = db.record_review(conn, ticket_id, decision, final_text, seconds, category_final)
        next_id = next((t["id"] for t in reversed(db.list_tickets(conn)) if t["state"] in PENDING), None)
    finally:
        conn.close()
    send_scores(ticket.get("trace_id"), saved)
    return RedirectResponse(f"/tickets/{next_id}" if next_id else "/", status_code=303)


@app.get("/metrics", response_class=HTMLResponse)
def metrics_page(request: Request):
    conn = db.connect()
    m = db.metrics(conn)
    conn.close()
    return templates.TemplateResponse(request, "metrics.html", {"m": m})


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
