"""CX agent workstation: inbox, review, impact metrics, webhook. Spec: docs/specs/ui.md.

    python -m uv run uvicorn app.main:app --reload   ->  http://localhost:8000
"""

import base64
import json
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

from app import db, github, notify, problems, product_request, radar, story, tour, views
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
    exempt = request.url.path.startswith("/static/") or request.url.path == "/webhooks/github"  # signed by GitHub
    if password and not exempt             and not _authorized(request.headers.get("Authorization"), password):
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


def github_client() -> github.GitHub | None:
    return github.from_env()


def radar_step(ticket: TicketIn, result) -> None:
    """After the reply is ready: the ticket feeds the product radar (docs/specs/radar.md). Never blocks the reply.

    A problem that just crossed the threshold gets its request drafted; one with an open issue gets "+N clientes".
    """
    conn = db.connect()
    try:
        signal = radar.ingest(conn, ticket, CUSTOMERS, GAZETTEER, classification=result.classification)
        row = conn.execute("SELECT status FROM problems WHERE id = ?", (signal.problem_id,)).fetchone()
        if row and row["status"] == "candidate" and product_request.load(conn, signal.problem_id) is None:
            radar.draft_for(conn, signal.problem_id, CUSTOMERS)
        elif row and row["status"] == "requested" and (gh := github_client()):
            radar.comment_new_customers(conn, signal.problem_id, CUSTOMERS, gh)
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
    problem = conn.execute("SELECT id, title, status, github_number, github_url FROM problems WHERE id = ?",
                           ((ticket or {}).get("problem_id"),)).fetchone()
    notice = None
    if ticket and ticket.get("kind") == "proactive":
        ids = json.loads(ticket["body"]).get("tickets", [])
        notice = {"tickets": [dict(r) for r in conn.execute(
            f"SELECT id, subject, created_at FROM tickets WHERE id IN ({','.join('?' * len(ids))}) ORDER BY created_at",
            ids)]}
    conn.close()
    if ticket is None:
        raise HTTPException(404)
    return templates.TemplateResponse(request, "ticket.html", {
        "problem": dict(problem) if problem else None, "problem_status": views.PROBLEM_STATUS_LABELS, "notice": notice,
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
        "requested": sum(1 for p in shown if p["status"] == "requested"),
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
        req = product_request.load(conn, problem_id) if p else None
        duplicates = radar.duplicate_candidates(conn, p) if p and p["status"] == "candidate" else []
        notices = [dict(r) for r in conn.execute(
            "SELECT n.ticket_id, n.customer_id, t.state FROM notices n JOIN tickets t ON t.id = n.ticket_id "
            "WHERE n.problem_id = ? ORDER BY n.customer_id", (problem_id,))]
    finally:
        conn.close()
    if p is None:
        raise HTTPException(404)
    return templates.TemplateResponse(request, "problem.html", {
        **_shell(), "p": p, "customers": CUSTOMERS, "v": views, "req": req, "duplicates": duplicates,
        "notices": notices,
        "github_ready": github_client() is not None, "error": request.query_params.get("error"),
        "threshold": next((e for e in p["events"] if e["kind"] == "threshold"), None),
    })


def _no_public() -> None:
    if is_public():
        raise HTTPException(403, "Public demo: the radar does not write.")


@app.post("/radar/problems/{problem_id}/draft")
def problem_draft(problem_id: str) -> RedirectResponse:
    _no_public()
    conn = db.connect()
    try:
        radar.draft_for(conn, problem_id, CUSTOMERS)
        error = ""
    except Exception as e:
        log.warning("draft failed for %s: %r", problem_id, e)
        error = "?error=draft"
    finally:
        conn.close()
    return RedirectResponse(f"/radar/problems/{problem_id}{error}", status_code=303)


@app.post("/radar/problems/{problem_id}/request")
def problem_request(problem_id: str, decision: str = Form(...), title: str = Form(""), body_md: str = Form(""),
                    merge_into: str = Form("")) -> RedirectResponse:
    """The CX agent decides: approve (create the issue), merge into an open issue, or reject."""
    _no_public()
    conn = db.connect()
    try:
        if decision == "reject":
            radar.reject(conn, problem_id)
            return RedirectResponse(f"/radar/problems/{problem_id}", status_code=303)
        gh = github_client()
        if gh is None:
            return RedirectResponse(f"/radar/problems/{problem_id}?error=github-config", status_code=303)
        if not title.strip() or not body_md.strip():
            raise HTTPException(422, "Empty title or body.")
        try:
            radar.approve(conn, problem_id, CUSTOMERS, gh, title=title.strip(), body=body_md.replace("\r\n", "\n"),
                          merge_into=merge_into or None)
        except github.GitHubError as e:
            log.warning("GitHub failed for %s: %r", problem_id, e)
            return RedirectResponse(f"/radar/problems/{problem_id}?error=github-{e.status}", status_code=303)
    finally:
        conn.close()
    return RedirectResponse(f"/radar/problems/{problem_id}", status_code=303)


# --- the closed loop: docs/specs/notify.md ---------------------------------------------------

def run_notices(problem_id: str) -> None:
    conn = db.connect()
    try:
        notify.on_resolved(conn, problem_id, CUSTOMERS)
    except Exception as error:
        log.warning("notices failed for %s: %r", problem_id, error)
    finally:
        conn.close()


@app.post("/webhooks/github", status_code=202)
async def github_webhook(request: Request, background: BackgroundTasks) -> dict:
    """GitHub `issues` events. The HMAC signature is the authentication, so basic auth does not apply."""
    _no_public()
    body = await request.body()
    if not github.verify_signature(body, request.headers.get("X-Hub-Signature-256"),
                                   os.environ.get("GITHUB_WEBHOOK_SECRET", "")):
        raise HTTPException(401, "bad signature")
    if request.headers.get("X-GitHub-Event") != "issues":
        return {"ignored": request.headers.get("X-GitHub-Event")}
    event = await request.json()
    issue = event.get("issue") or {}
    conn = db.connect()
    try:
        pid = radar.problem_for_issue(conn, issue.get("number"), issue.get("body") or "")
        result = radar.issue_changed(conn, pid, issue.get("state", ""), issue.get("state_reason")) if pid else None
    finally:
        conn.close()
    if result == "notify":
        background.add_task(run_notices, pid)
    return {"problem_id": pid, "action": event.get("action"), "result": result}


@app.post("/radar/sync")
def radar_sync(background: BackgroundTasks) -> RedirectResponse:
    """«Comprobar GitHub»: the poll fallback when GitHub cannot reach this server (local demo)."""
    _no_public()
    gh = github_client()
    if gh is None:
        return RedirectResponse("/radar?error=github-config", status_code=303)
    conn = db.connect()
    try:
        to_notify = radar.sync_issues(conn, gh)
    except github.GitHubError as e:
        return RedirectResponse(f"/radar?error=github-{e.status}", status_code=303)
    finally:
        conn.close()
    for pid in to_notify:
        background.add_task(run_notices, pid)
    return RedirectResponse(f"/radar?synced={len(to_notify)}", status_code=303)


@app.post("/radar/problems/{problem_id}/notices")
def problem_notices(problem_id: str, background: BackgroundTasks) -> RedirectResponse:
    """Draft the notices that are missing (a failed customer, or a reopened and closed issue)."""
    _no_public()
    background.add_task(run_notices, problem_id)
    return RedirectResponse(f"/radar/problems/{problem_id}", status_code=303)


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
