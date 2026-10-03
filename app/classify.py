"""Ticket classifier: Jev decision model, Haiku fallback. Spec: docs/specs/classify.md."""

from dataclasses import dataclass

from langfuse import get_client, observe
from pydantic import BaseModel, Field
from pydantic_ai import Agent
from pydantic_ai.models import Model

from app.config import FALLBACK_CLASSIFIER_MODEL, JEV_MODEL
from app.domain import Category, Language, Priority, Sentiment


class TicketClassification(BaseModel):
    """Jev gets no instructions: each field description is the question it answers."""

    category: Category = Field(
        description="Which part of haddock is the support ticket about? invoices = supplier invoices, OCR, "
        "suppliers; bank = bank connection, sync, reconciliation; pos = POS/TPV integration and sales; "
        "inventory = stock counts, recipes, food cost; reports = P&L and reports; account = users, "
        "permissions, the haddock plan and its billing; other = anything else."
    )
    priority: Priority = Field(
        description="How urgent is the ticket? urgent = the restaurant loses money, or an accounting close "
        "(cierre de mes, trimestre, gestoría) or a payment is blocked today or tomorrow; high = a core "
        "feature does not work but there is a manual workaround; normal = a question or a minor error; "
        "low = a suggestion or a general question."
    )
    sentiment: Sentiment = Field(description="How does the customer feel when writing the ticket?")
    language: Language = Field(description="Which language is the ticket written in?")


@dataclass
class ClassifyResult:
    classification: TicketClassification
    confidence: dict[str, float] | None
    model: str


def _agent(model: str | Model) -> Agent[None, TicketClassification]:
    # Built per call on purpose: a cached Agent keeps an async HTTP client bound to the first event loop,
    # and run_sync from another thread (evals use asyncio.to_thread) then hangs forever.
    return Agent(model, output_type=TicketClassification, name="ticket-classifier")


@observe(name="classify")
def classify(
    subject: str, body: str, *, model: str | Model | None = None, fallback_model: str | Model | None = None
) -> ClassifyResult:
    text = f"{subject}\n\n{body}"
    model = model or JEV_MODEL
    try:
        result = _agent(model).run_sync(text)
        details = result.response.provider_details or {}
        return ClassifyResult(result.output, details.get("confidence"), str(model))
    except Exception as error:  # Jev down, timeout, quota: fall back, but leave a mark in the trace
        get_client().update_current_span(level="WARNING", status_message=f"Jev failed, fallback: {error!r}")
        result = _agent(fallback_model or FALLBACK_CLASSIFIER_MODEL).run_sync(text)
        return ClassifyResult(result.output, None, "fallback")
