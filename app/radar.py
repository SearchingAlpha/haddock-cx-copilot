"""Product radar: one ticket in, signal -> problem -> threshold. Spec: docs/specs/radar.md."""

import contextvars
import json
import re
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime

from langfuse import get_client, observe, propagate_attributes

from app import db, github, problems, product_request
from app.classify import ClassifyResult
from app.domain import Customer, TicketIn
from app.entities import Gazetteer
from app.problems import Match, assign, jev_same_problem, refresh_status
from app.signals import Signal, extract_signal


@observe(name="radar-signal", capture_input=False)
def traced_signal(ticket: TicketIn, customer: Customer, gazetteer: Gazetteer, *,
                  classification: ClassifyResult | None = None, extractor=extract_signal) -> Signal:
    with propagate_attributes(session_id=ticket.id, trace_name="radar-signal",
                              metadata={"ticket_id": ticket.id, "customer_id": ticket.customer_id}):
        signal = extractor(ticket, customer, gazetteer, classification=classification)
    signal.trace_id = get_client().get_current_trace_id() or ""
    get_client().update_current_span(output={"component": signal.component.value, "kind": signal.kind.value,
                                             "entity": signal.entity, "symptom": signal.symptom})
    return signal


@observe(name="radar-ingest", capture_input=False)
def ingest(conn, ticket: TicketIn, customers: dict[str, Customer], gazetteer: Gazetteer, *,
           signal: Signal | None = None, classification: ClassifyResult | None = None,
           matcher: Callable[[str], Match] = jev_same_problem, extractor=extract_signal) -> Signal:
    """Signal (unless given), problem, threshold. The ticket must already be in the database."""
    with propagate_attributes(session_id=ticket.id, trace_name="radar-ingest",
                              metadata={"ticket_id": ticket.id, "customer_id": ticket.customer_id}):
        if signal is None:
            signal = extractor(ticket, customers[ticket.customer_id], gazetteer, classification=classification)
            signal.trace_id = get_client().get_current_trace_id() or ""
        problem_id = assign(conn, signal, matcher=matcher)
        status = refresh_status(conn, problem_id, customers, signal.created_at) if problem_id else None
    get_client().update_current_span(output={"problem_id": problem_id, "status": status})
    return signal


def backfill(conn, tickets: list[TicketIn], customers: dict[str, Customer], *, workers: int = 8,
             matcher: Callable[[str], Match] = jev_same_problem, extractor=extract_signal,
             progress: Callable[[int, Signal], None] | None = None) -> list[Signal]:
    """Replay past tickets as source=history. Signals in parallel; problems in time order, one by one."""
    gazetteer = Gazetteer.from_customers(customers)
    tickets = sorted(tickets, key=lambda t: t.created_at)
    for t in tickets:
        try:
            db.insert_ticket(conn, TicketIn(**t.model_dump(include=set(TicketIn.model_fields))), source="history")
        except ValueError:
            pass  # already there: re-running the backfill on the same database is fine
    done = {r[0] for r in conn.execute("SELECT ticket_id FROM signals")}
    todo = [t for t in tickets if t.id not in done]
    signals = []
    with ThreadPoolExecutor(workers) as pool:
        futures = [pool.submit(contextvars.copy_context().run, traced_signal, t, customers[t.customer_id],
                               gazetteer, extractor=extractor) for t in todo]
        for n, (t, future) in enumerate(zip(todo, futures), start=1):
            signal = ingest(conn, t, customers, gazetteer, signal=future.result(), matcher=matcher)
            signals.append(signal)
            if progress:
                progress(n, signal)
    return signals


# --- product requests: docs/specs/product-request.md ------------------------------------------------

def _event(conn, problem_id: str, kind: str, payload: dict) -> None:
    problems._event(conn, problem_id, kind, payload, datetime.now().isoformat(timespec="seconds"))


def draft_for(conn, problem_id: str, customers: dict[str, Customer], *, client=None) -> product_request.ProductRequest:
    """Sonnet drafts the request; it waits in product_requests for a CX agent. The issue title becomes the title."""
    problem = problems.get_problem(conn, problem_id, customers)
    req = product_request.draft_request(problem, customers, client=client)
    product_request.save(conn, problem_id, req)
    with conn:
        conn.execute("UPDATE problems SET title = ? WHERE id = ?", (req.draft.title, problem_id))
        _event(conn, problem_id, "drafted", {"dropped_quotes": len(req.dropped), "cost_usd": round(req.cost_usd, 4)})
    return req


def duplicate_candidates(conn, problem: dict) -> list[dict]:
    """Problems that already have an issue and may be the same: same area, compatible entity. A human decides."""
    area = problem["component"].split(".")[0]
    rows = conn.execute(
        "SELECT * FROM problems WHERE status = 'requested' AND id != ? AND kind = ? AND component LIKE ? "
        "AND (? IS NULL OR entity IS NULL OR entity = ?)",
        (problem["id"], problem["kind"], f"{area}.%", problem.get("entity"), problem.get("entity")))
    return [dict(r) for r in rows]


def _customers_md(ids: list[str], customers: dict[str, Customer]) -> str:
    return "\n".join(f"- {product_request.customer_line(customers.get(c), c)}" for c in ids)


@observe(name="request-decision", capture_input=False)
def approve(conn, problem_id: str, customers: dict[str, Customer], gh: github.GitHub, *, title: str, body: str,
            merge_into: str | None = None) -> dict:
    """Create the issue, or comment on the issue of `merge_into` and fold this problem into it."""
    problem = problems.get_problem(conn, problem_id, customers)
    req = product_request.load(conn, problem_id) or {}
    decision = "approve" if (title, body) == (req.get("title"), req.get("body_md")) else "edit"
    if merge_into:
        target = conn.execute("SELECT * FROM problems WHERE id = ? AND status = 'requested'", (merge_into,)).fetchone()
        if target is None:
            raise ValueError(f"{merge_into} has no open issue")
        gh.comment(target["github_number"],
                   f"**+{len(problem['impact'].customers)} clientes** con el mismo problema "
                   f"({problem['impact'].tickets} tickets, detectado como `{problem_id}`):\n\n"
                   + _customers_md(problem["impact"].customers, customers))
        with conn:
            survivor = problems.merge(conn, [dict(target), problem], datetime.now().isoformat(timespec="seconds"))
            known = set(json.loads(target["issue_customers"] or "[]")) | set(problem["impact"].customers)
            conn.execute("UPDATE problems SET issue_customers = ? WHERE id = ?", (json.dumps(sorted(known)), survivor))
            _event(conn, survivor, "commented", {"from": problem_id, "customers": problem["impact"].customers})
        decision, out = "merge", {"number": target["github_number"], "url": target["github_url"]}
    else:
        labels = ["radar", "feature" if problem["kind"] == "feature" else "bug"]
        out = gh.create_issue(title, body, labels)
        with conn:
            conn.execute(
                "UPDATE problems SET status = 'requested', title = ?, github_number = ?, github_url = ?, "
                "issue_customers = ? WHERE id = ? AND status = 'candidate'",
                (title, out["number"], out["url"], json.dumps(problem["impact"].customers), problem_id))
            _event(conn, problem_id, "requested", out)
    with conn:
        conn.execute("UPDATE product_requests SET status = 'approved', decision = ?, decided_at = ?, title = ?, "
                     "body_md = ? WHERE problem_id = ?",
                     (decision, datetime.now().isoformat(timespec="seconds"), title, body, problem_id))
    _decision_score(req.get("trace_id"), decision)
    return out | {"decision": decision}


def reject(conn, problem_id: str) -> None:
    req = product_request.load(conn, problem_id) or {}
    with conn:
        conn.execute("UPDATE problems SET status = 'dismissed' WHERE id = ? AND status IN ('open', 'candidate')",
                     (problem_id,))
        conn.execute("UPDATE product_requests SET status = 'rejected', decision = 'reject', decided_at = ? "
                     "WHERE problem_id = ?", (datetime.now().isoformat(timespec="seconds"), problem_id))
        _event(conn, problem_id, "dismissed", {"by": "agente CX"})
    _decision_score(req.get("trace_id"), "reject")


def _decision_score(trace_id: str | None, decision: str) -> None:
    if not trace_id:
        return
    try:
        get_client().create_score(trace_id=trace_id, name="request_decision", value=decision, data_type="CATEGORICAL")
    except Exception:  # the decision is in SQLite already
        pass


@observe(name="issue-update")
def comment_new_customers(conn, problem_id: str, customers: dict[str, Customer], gh: github.GitHub) -> str | None:
    """The issue is open and new customers arrived: tell product, once per new batch."""
    p = conn.execute("SELECT * FROM problems WHERE id = ?", (problem_id,)).fetchone()
    if p is None or p["status"] != "requested" or not p["github_number"]:
        return None
    known = set(json.loads(p["issue_customers"] or "[]"))
    order = list(dict.fromkeys(s["customer_id"] for s in problems.problem_signals(conn, problem_id)))
    new = [c for c in order if c not in known]
    if not new:
        return None
    imp = problems.impact(problems.problem_signals(conn, problem_id), customers, problems.now_of(conn))
    url = gh.comment(p["github_number"],
                     f"**+{len(new)} {'cliente' if len(new) == 1 else 'clientes'}** desde la última actualización. "
                     f"Ahora: {imp.tickets} tickets de {len(imp.customers)} clientes, "
                     f"{imp.mrr_eur:,.0f} €/mes de MRR de clientes afectados.\n\n".replace(",", ".")
                     + _customers_md(new, customers))
    with conn:
        conn.execute("UPDATE problems SET issue_customers = ? WHERE id = ?", (json.dumps(sorted(known | set(new))),
                                                                             problem_id))
        _event(conn, problem_id, "commented", {"customers": new, "url": url})
    return url


# --- the closed loop: docs/specs/notify.md ------------------------------------------------------------

def issue_changed(conn, problem_id: str, state: str, state_reason: str | None) -> str | None:
    """GitHub says the issue changed. Returns "notify" when the problem just became resolved. Idempotent."""
    now = datetime.now().isoformat(timespec="seconds")
    with conn:
        if state == "closed" and state_reason in (None, "completed"):
            if conn.execute("UPDATE problems SET status = 'resolved', resolved_at = ? WHERE id = ? AND status = 'requested'",
                            (now, problem_id)).rowcount:
                _event(conn, problem_id, "resolved", {"state_reason": state_reason or "completed"})
                return "notify"
        elif state == "closed":  # not_planned, duplicate: nothing was fixed, nobody is told it was
            if conn.execute("UPDATE problems SET status = 'dismissed' WHERE id = ? AND status = 'requested'",
                            (problem_id,)).rowcount:
                _event(conn, problem_id, "dismissed", {"state_reason": state_reason})
        elif state == "open":
            if conn.execute("UPDATE problems SET status = 'requested', resolved_at = NULL WHERE id = ? "
                            "AND status = 'resolved'", (problem_id,)).rowcount:
                _event(conn, problem_id, "reopened", {})
    return None


def problem_for_issue(conn, number: int, body: str = "") -> str | None:
    row = conn.execute("SELECT id FROM problems WHERE github_number = ? AND status != 'merged'", (number,)).fetchone()
    if row:
        return row["id"]
    marker = re.search(r"<!-- haddock-problem:(P-\d+) -->", body or "")  # the database was reset: the marker remains
    if marker and conn.execute("SELECT 1 FROM problems WHERE id = ?", (marker.group(1),)).fetchone():
        return marker.group(1)
    return None


@observe(name="github-sync")
def sync_issues(conn, gh: github.GitHub) -> list[str]:
    """Poll instead of webhook: read the radar issues and apply their state. Returns problems to notify."""
    to_notify = []
    for issue in gh.list_issues(state="all"):
        pid = problem_for_issue(conn, issue["number"], issue["body"])
        if pid and issue_changed(conn, pid, issue["state"], issue["state_reason"]) == "notify":
            to_notify.append(pid)
    get_client().update_current_span(output={"notify": to_notify})
    return to_notify
