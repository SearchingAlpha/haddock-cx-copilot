"""One ticket end to end: classify -> agent -> guardrails. Spec: docs/specs/pipeline.md."""

from dataclasses import dataclass, field
from typing import Literal

from langfuse import get_client, observe, propagate_attributes

from app.agent import AgentResult, run_agent
from app.classify import ClassifyResult, classify
from app.config import CATEGORY_REVIEW_CONFIDENCE, FALLBACK_CLASSIFIER_MODEL
from app.domain import Customer, TicketIn
from app.guardrails import GuardrailResult, check, jev_promise_check
from app.tools import KBIndex, ToolContext


@dataclass(frozen=True)
class RunOptions:
    """Variant knobs for experiments (docs/specs/evals.md). Defaults = production behaviour."""

    classifier: Literal["jev", "haiku"] = "jev"
    prompt_label: str = "production"
    classify_only: bool = False
    category_review_confidence: float = CATEGORY_REVIEW_CONFIDENCE


@dataclass
class TicketResult:
    ticket_id: str
    status: Literal["ready", "escalated"]
    classification: ClassifyResult | None
    agent: AgentResult | None = None
    guardrails: GuardrailResult | None = None
    reasons: list[str] = field(default_factory=list)
    trace_id: str = ""
    review_category: bool = False  # low classifier confidence: the CX agent checks the category

    @property
    def cost_usd(self) -> float:
        return self.agent.cost_usd if self.agent else 0.0


def _low_confidence(result: ClassifyResult, threshold: float) -> bool:
    if result.confidence is None:  # Haiku has no calibrated confidence: nothing to flag
        return False
    return result.confidence.get("category", 1.0) < threshold


def _route(ticket: TicketIn, customers: dict[str, Customer], kb: KBIndex, options: RunOptions) -> TicketResult:
    customer = customers[ticket.customer_id]
    model = FALLBACK_CLASSIFIER_MODEL if options.classifier == "haiku" else None
    classified = classify(ticket.subject, ticket.body, model=model)
    review_category = _low_confidence(classified, options.category_review_confidence)  # flag, never escalate
    if options.classify_only:
        return TicketResult(ticket.id, "ready", classified, reasons=["classify_only"],
                            review_category=review_category)

    ctx = ToolContext(customer=customer, kb=kb)  # the agent only ever sees this customer
    drafted = run_agent(ticket, ctx, prompt_label=options.prompt_label)
    others = [c for c in customers.values() if c.id != customer.id]
    guarded = check(
        drafted, customer, others,
        ticket_text=f"{ticket.subject}\n{ticket.body}", promise_checker=jev_promise_check,
    )
    status = "ready" if guarded.status == "pass" else "escalated"
    return TicketResult(ticket.id, status, classified, drafted, guarded, guarded.reasons,
                        review_category=review_category)


@observe(name="process-ticket", capture_input=False, capture_output=False)
def process_ticket(
    ticket: TicketIn, customers: dict[str, Customer], *, kb: KBIndex, options: RunOptions = RunOptions()
) -> TicketResult:
    langfuse = get_client()
    langfuse.update_current_span(input={"subject": ticket.subject, "body": ticket.body})
    with propagate_attributes(
        session_id=ticket.id,
        trace_name="process-ticket",
        metadata={"ticket_id": ticket.id, "customer_id": ticket.customer_id, "channel": ticket.channel},
    ):
        try:
            result = _route(ticket, customers, kb, options)
        except Exception as error:
            langfuse.update_current_span(level="ERROR", status_message=repr(error))
            result = TicketResult(ticket.id, "escalated", None, reasons=["pipeline_error"])

    result.trace_id = langfuse.get_current_trace_id() or ""
    langfuse.update_current_span(output=summary(result))
    return result


def summary(r: TicketResult) -> dict:
    c = r.classification
    return {
        "status": r.status,
        "reasons": r.reasons,
        "classification": c.classification.model_dump(mode="json") if c else None,
        "confidence": c.confidence if c else None,
        "classifier": c.model if c else None,
        "draft": r.agent.draft if r.agent else None,
        "evidence": r.agent.evidence if r.agent else [],
        "tool_calls": r.agent.tool_calls if r.agent else [],
        "prompt_version": r.agent.prompt_version if r.agent else None,
        "review_category": r.review_category,
        "cost_usd": round(r.cost_usd, 5),
    }
