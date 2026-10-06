"""Close the loop: one proactive notice per affected customer when a problem is resolved. Spec: docs/specs/notify.md."""

import json
from datetime import datetime
from functools import cache

import anthropic
from langfuse import get_client, observe, propagate_attributes
from pydantic import BaseModel, Field

from app import db, problems, product_request
from app.agent import AgentResult, cost_usd
from app.config import NOTICE_MODEL
from app.domain import Customer, TicketIn
from app.guardrails import check, jev_promise_check
from app.pipeline import TicketResult
from app.prompts import PROACTIVE_NOTICE, get_prompt


class Notice(BaseModel):
    subject: str = Field(description="At most 70 characters, in Spanish.")
    body: str = Field(description="60 to 140 words, in Spanish.")


@cache
def _client() -> anthropic.Anthropic:
    return anthropic.Anthropic()


def notice_id(problem_id: str, customer_id: str) -> str:
    return f"N-{problem_id.replace('-', '')}-{customer_id.replace('-', '')}"


def notice_input(problem: dict, fix: dict, customer: Customer, own: list[dict]) -> str:
    """Only this customer's tickets: the notice cannot leak another customer's data it never saw."""
    tickets = "\n\n".join(f'<ticket date="{s["created_at"][:10]}">\n{s.get("subject") or ""}\n\n{s.get("body") or ""}\n</ticket>'
                          for s in own)
    return (f"<fix>\nTítulo: {fix['title']}\nResumen: {fix['summary']}\nResuelto: {fix['resolved_at'][:10]}\n</fix>\n\n"
            f"<customer>{customer.name} · contacto {customer.contact_name}</customer>\n\n{tickets}")


@observe(name="notice-draft", as_type="generation", capture_input=False, capture_output=False)
def _write(text: str, client) -> tuple[Notice, float]:
    prompt = get_prompt(PROACTIVE_NOTICE)
    response = client.messages.parse(model=NOTICE_MODEL, max_tokens=2000, system=prompt.text,
                                     messages=[{"role": "user", "content": text}], output_format=Notice)
    if response.stop_reason == "refusal" or response.parsed_output is None:
        raise RuntimeError(f"no notice: stop_reason={response.stop_reason}")
    cost = cost_usd(NOTICE_MODEL, response.usage)
    get_client().update_current_generation(
        model=NOTICE_MODEL, input=text, output=response.parsed_output.model_dump(), prompt=prompt.client,
        usage_details={"input": response.usage.input_tokens, "output": response.usage.output_tokens},
        cost_details={"total": cost},
    )
    return response.parsed_output, cost


def _fix(conn, problem: dict) -> dict:
    req = product_request.load(conn, problem["id"]) or {}
    return {"title": problem["title"], "summary": (req.get("payload") or {}).get("summary", ""),
            "resolved_at": problem.get("resolved_at") or datetime.now().isoformat(timespec="seconds")}


@observe(name="notice", capture_input=False)
def _one(conn, problem: dict, fix: dict, customer: Customer, customers: dict[str, Customer], client,
         promise_checker) -> str:
    tid = notice_id(problem["id"], customer.id)
    with propagate_attributes(session_id=tid, trace_name="notice",
                              metadata={"problem_id": problem["id"], "customer_id": customer.id}):
        own = [s for s in problem["signals"] if s["customer_id"] == customer.id]
        notice, cost = _write(notice_input(problem, fix, customer, own), client)
        agent = AgentResult(draft=notice.body, evidence=[s["ticket_id"] for s in own], confidence="high",
                            escalation=None, tool_calls=[], iterations=1, stop="submitted", cost_usd=cost)
        others = [c for c in customers.values() if c.id != customer.id]
        guarded = check(agent, customer, others, ticket_text="\n".join(s.get("body") or "" for s in own),
                        promise_checker=promise_checker)
    ticket = TicketIn(id=tid, customer_id=customer.id, channel="email", subject=notice.subject,
                      created_at=datetime.fromisoformat(fix["resolved_at"]),
                      body=json.dumps({"problem_id": problem["id"], "tickets": [s["ticket_id"] for s in own]}))
    try:
        db.insert_ticket(conn, ticket, kind="proactive", mode="copilot", problem_id=problem["id"])
    except ValueError:
        pass  # a crash after the insert and before `notices`: keep the ticket, write the new draft

    result = TicketResult(tid, "ready" if guarded.status == "pass" else "escalated", None, agent, guarded,
                          guarded.reasons, trace_id=get_client().get_current_trace_id() or "")
    db.save_result(conn, result)
    return tid


@observe(name="notify", capture_input=False)
def on_resolved(conn, problem_id: str, customers: dict[str, Customer], *, client=None,
                promise_checker=jev_promise_check) -> list[str]:
    """One notice per affected customer, once (UNIQUE in `notices`). A failure skips that customer only."""
    problem = problems.get_problem(conn, problem_id, customers)
    if problem is None or problem["status"] != "resolved":
        return []
    fix, client = _fix(conn, problem), client or _client()
    done = {r[0] for r in conn.execute("SELECT customer_id FROM notices WHERE problem_id = ?", (problem_id,))}
    created = []
    for cid in problem["impact"].customers:
        if cid in done or cid not in customers:
            continue
        try:
            tid = _one(conn, problem, fix, customers[cid], customers, client, promise_checker)
        except Exception as error:
            get_client().update_current_span(level="WARNING", status_message=f"{cid}: {error!r}")
            continue
        with conn:
            conn.execute("INSERT OR IGNORE INTO notices VALUES (?, ?, ?, ?)",
                         (problem_id, cid, tid, datetime.now().isoformat(timespec="seconds")))
        created.append(tid)
    if created:
        with conn:
            problems._event(conn, problem_id, "notices", {"tickets": created},
                            datetime.now().isoformat(timespec="seconds"))
    get_client().update_current_span(output={"notices": created})
    return created
