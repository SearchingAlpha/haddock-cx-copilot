"""Product radar: one ticket in, signal -> problem -> threshold. Spec: docs/specs/radar.md."""

import contextvars
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor

from langfuse import get_client, observe, propagate_attributes

from app import db
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
