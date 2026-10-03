"""Deterministic checks on every draft before human review. Spec: docs/specs/guardrails.md."""

import re
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Literal

from langfuse import get_client, observe
from pydantic import BaseModel, Field
from pydantic_ai import Agent

from app.agent import AgentResult
from app.config import JEV_MODEL
from app.domain import Customer

BLOCKING = {"refund_promise", "deadline_promise", "other_customer_data"}

# Commitments only. "Normalmente en menos de 24 horas" (kb-02) is information, not a promise.
REFUND_PATTERNS = [
    r"\b(te|os|le|les)\s+(devolvemos|devolveremos|reembolsamos|reembolsaremos|abonamos|abonaremos)\b",
    r"\breembolso\s+(garantizado|aprobado|confirmado)\b",
    r"\bwe(\s+will|'ll)\s+refund\b",
    r"\b(us|et)\s+(retornarem|tornarem)\b",
]
DEADLINE_PATTERNS = [
    r"\b(te|os|le|les)\s+(garantizo|garantizamos|aseguro|aseguramos|prometo|prometemos)\b",
    r"\bestar[áa]n?\s+(resuelto|solucionado|procesado|arreglado)s?\s+(hoy|mañana|antes)\b",
    r"\bwe\s+(guarantee|promise)\b",
    r"\b(et|us)\s+(garanteixo|garantim)\b",
]


@dataclass
class PromiseCheck:
    refund: bool
    deadline: bool


@dataclass
class GuardrailResult:
    status: Literal["pass", "blocked", "escalated"]
    reasons: list[str] = field(default_factory=list)


class _PromiseQuestions(BaseModel):
    refund: bool = Field(description="Does this support reply promise the customer a refund or a compensation?")
    deadline: bool = Field(
        description="Does this support reply guarantee that the problem will be solved by a specific time?"
    )


def _promise_agent() -> Agent[None, _PromiseQuestions]:
    # Not cached: see app/classify.py::_agent (async client bound to one event loop).
    return Agent(JEV_MODEL, output_type=_PromiseQuestions, name="promise-check")


def jev_promise_check(text: str) -> PromiseCheck:
    out = _promise_agent().run_sync(text).output
    return PromiseCheck(refund=out.refund, deadline=out.deadline)


@observe(name="promise_check", as_type="guardrail")
def _promises(draft: str, checker: Callable[[str], PromiseCheck]) -> list[str]:
    reasons = []
    if any(re.search(p, draft, re.IGNORECASE) for p in REFUND_PATTERNS):
        reasons.append("refund_promise")
    if any(re.search(p, draft, re.IGNORECASE) for p in DEADLINE_PATTERNS):
        reasons.append("deadline_promise")
    if reasons:
        return reasons  # explicit commitment found: no need to ask Jev
    try:
        found = checker(draft)
    except Exception as error:
        get_client().update_current_span(level="WARNING", status_message=f"promise check failed: {error!r}")
        return ["promise_check_failed"]
    return [r for r, hit in (("refund_promise", found.refund), ("deadline_promise", found.deadline)) if hit]


@observe(name="other_customer_data", as_type="guardrail")
def _other_customer_data(draft: str, others: list[Customer], ticket_text: str) -> list[str]:
    text, already_known = draft.lower(), ticket_text.lower()
    for other in others:
        markers = [other.name, other.contact_email, other.id, *(i.id for i in other.invoices)]
        # Repeating what the customer wrote is not a leak: "no podemos enviarte facturas de Grupo Brasa".
        if any(m.lower() in text and m.lower() not in already_known for m in markers):
            return ["other_customer_data"]
    return []


def _escalation_rules(result: AgentResult) -> list[str]:
    reasons = []
    if result.escalation:
        reasons.append("agent_escalated")
    if result.draft is None:
        reasons.append("no_draft")
    if result.confidence == "low":
        reasons.append("low_agent_confidence")
    return reasons


@observe(name="guardrails", as_type="guardrail")
def check(
    result: AgentResult,
    customer: Customer,
    others: list[Customer],
    *,
    ticket_text: str = "",
    promise_checker: Callable[[str], PromiseCheck] = jev_promise_check,
) -> GuardrailResult:
    others = [o for o in others if o.id != customer.id]
    reasons = []
    if result.draft:  # every check runs, so `reasons` shows all problems at once
        reasons += _promises(result.draft, promise_checker)
        reasons += _other_customer_data(result.draft, others, ticket_text)
    reasons += _escalation_rules(result)

    if BLOCKING & set(reasons):
        status = "blocked"
    elif reasons:
        status = "escalated"
    else:
        status = "pass"
    return GuardrailResult(status, reasons)
