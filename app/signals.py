"""What the radar extracts from one ticket: component, kind, entity, symptom. Spec: docs/specs/radar.md."""

from dataclasses import dataclass, field

from langfuse import get_client, observe
from pydantic import BaseModel, Field
from pydantic_ai import Agent
from pydantic_ai.models import Model

from app.classify import ClassifyResult, classify
from app.config import FALLBACK_CLASSIFIER_MODEL, SIGNAL_MODEL, SYMPTOM_MODEL
from app.domain import Component, Customer, Kind, Priority, TicketIn
from app.entities import Gazetteer, extract_entity
from app.prompts import SYMPTOM, get_prompt


class TicketSignal(BaseModel):
    """Jev gets no instructions: each field description is the question it answers."""

    component: Component = Field(
        description="Which part of haddock does the ticket's problem or request affect? "
        "invoices.ocr = reading invoice data (OCR, totals, 'no se lee', reading errors); "
        "invoices.suppliers = suppliers, uploading or downloading invoices; "
        "invoices.duplicates = an invoice that appears twice; "
        "bank.sync = bank connection, authorization and sync of movements; "
        "bank.reconciliation = matching bank movements with invoices; "
        "pos.sync = POS/TPV connection, terminals, sales that do not arrive; "
        "pos.sales = POS sales that arrive with wrong or duplicated numbers; "
        "inventory.stock = stock counts; inventory.recipes = recipes, escandallos, food cost; "
        "reports.pnl = P&L content and views; reports.export = exporting reports to Excel or PDF; "
        "account.users = users and permissions; account.billing = the haddock plan and its billing; "
        "other = anything else."
    )
    kind: Kind = Field(
        description="What kind of ticket is it? bug = haddock does not work as it should: it worked before, "
        "the data is wrong, or it fails with a correct input; feature = the customer asks haddock to build "
        "something it does not have (a new report, a new view); how_to = the customer asks how to do something "
        "or whether something is possible ('¿se puede...?', '¿puedo...?', '¿hacéis...?'); user_error = the cause is "
        "on the customer's side: a blurry photo, a changed password, a disconnected device, a file "
        "uploaded twice."
    )


class Symptom(BaseModel):
    symptom: str = Field(description="One short sentence in Spanish, at most 20 words.")


@dataclass
class Signal:
    ticket_id: str
    customer_id: str
    created_at: str
    text: str  # subject + body, for BM25 and the matcher
    component: Component
    kind: Kind
    entity: str | None
    symptom: str
    priority: Priority | None = None
    confidence: dict[str, float] | None = None  # Jev's per field; None after the fallback
    model: str = ""
    trace_id: str = ""
    problem_id: str | None = None
    match_confidence: float | None = None
    matched: list[dict] = field(default_factory=list)  # the matcher's answers, for the trace and the UI


def _signal_agent(model: str | Model) -> Agent[None, TicketSignal]:
    # Not cached: see app/classify.py::_agent (async client bound to one event loop).
    return Agent(model, output_type=TicketSignal, name="ticket-signal")


@observe(name="signal")
def typed_signal(text: str, *, model: str | Model | None = None,
                 fallback_model: str | Model | None = None) -> tuple[TicketSignal, dict | None, str]:
    model = model or SIGNAL_MODEL
    try:
        result = _signal_agent(model).run_sync(text)
        return result.output, (result.response.provider_details or {}).get("confidence"), str(model)
    except Exception as error:
        get_client().update_current_span(level="WARNING", status_message=f"Jev failed, fallback: {error!r}")
        result = _signal_agent(fallback_model or FALLBACK_CLASSIFIER_MODEL).run_sync(text)
        return result.output, None, "fallback"


@observe(name="symptom")
def symptom(text: str, *, model: str | Model | None = None) -> str:
    prompt = get_prompt(SYMPTOM)
    get_client().update_current_span(metadata={"prompt_version": getattr(prompt.client, "version", None)})
    agent = Agent(model or SYMPTOM_MODEL, output_type=Symptom, instructions=prompt.text, name="ticket-symptom")
    return agent.run_sync(f"<ticket>\n{text}\n</ticket>").output.symptom.strip()


def extract_signal(
    ticket: TicketIn,
    customer: Customer,
    gazetteer: Gazetteer,
    *,
    classification: ClassifyResult | None = None,
    model: str | Model | None = None,
    fallback_model: str | Model | None = None,
    symptom_model: str | Model | None = None,
    classify_model: str | Model | None = None,
) -> Signal:
    """Live tickets pass the pipeline's classification; the backfill classifies here (Jev, cheap)."""
    text = f"{ticket.subject}\n\n{ticket.body}"
    if classification is None:
        classification = classify(ticket.subject, ticket.body, model=classify_model, fallback_model=fallback_model)
    typed, confidence, used = typed_signal(text, model=model, fallback_model=fallback_model)
    return Signal(
        ticket_id=ticket.id, customer_id=ticket.customer_id, created_at=ticket.created_at.isoformat(), text=text,
        component=typed.component, kind=typed.kind,
        entity=extract_entity(text, customer, typed.component, gazetteer),
        symptom=symptom(text, model=symptom_model),
        priority=classification.classification.priority, confidence=confidence, model=used,
    )
