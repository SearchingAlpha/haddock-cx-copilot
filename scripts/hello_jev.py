"""Smoke test: classify 3 Spanish tickets with Jev, one Langfuse trace per ticket.

Checks two open questions before Phase 2:
1. Does Jev classify Spanish tickets correctly?
2. Does the Jev call appear in the Langfuse trace (pydantic-ai OpenTelemetry spans)?

Trace contract: docs/specs/observability.md.
"""

from enum import Enum

from langfuse import get_client, observe, propagate_attributes
from pydantic import BaseModel, Field
from pydantic_ai import Agent
from pydantic_ai.models import Model

from app.observability import init_tracing


class Category(str, Enum):
    invoices = "invoices"
    bank_reconciliation = "bank_reconciliation"
    pos_integration = "pos_integration"
    inventory = "inventory"
    billing = "billing"
    other = "other"


class Sentiment(str, Enum):
    positive = "positive"
    neutral = "neutral"
    negative = "negative"
    very_negative = "very_negative"


class Classification(BaseModel):
    category: Category = Field(description="What part of haddock is the ticket about?")
    urgent: bool = Field(description="Does the restaurant lose money or stop working until this is fixed?")
    sentiment: Sentiment = Field(description="How does the customer feel?")


TICKETS = [
    # (ticket_id, text, expected category)
    ("T-0001", "Hola, subí tres facturas de Makro el lunes y siguen en 'procesando'. ¿Es normal?", Category.invoices),
    ("T-0002", "¡Llevamos 4 días sin que se sincronice el banco y el cierre de mes es mañana! Esto es un desastre.", Category.bank_reconciliation),
    ("T-0003", "Buenas, ¿cómo conecto el TPV de Last.app con haddock para ver las ventas?", Category.pos_integration),
]


def build_classifier(model: str | Model = "typesafe:jev-latest") -> Agent[None, Classification]:
    return Agent(model, output_type=Classification, name="ticket-classifier")


@observe(name="classify-ticket", capture_input=False, capture_output=False)
def classify_ticket(
    classifier: Agent[None, Classification], ticket_id: str, text: str, expected: Category | None = None
) -> tuple[Classification, dict | None]:
    langfuse = get_client()
    langfuse.update_current_span(
        input=text,
        metadata={"expected_category": expected.value if expected else None},
    )
    with propagate_attributes(
        session_id=ticket_id,
        trace_name="classify-ticket",
        metadata={"ticket_id": ticket_id, "source": "scripts/hello_jev.py"},
    ):
        result = classifier.run_sync(text, conversation_id=ticket_id)

    out = result.output
    details = result.response.provider_details or {}
    confidence = details.get("confidence")
    langfuse.update_current_span(output={"classification": out.model_dump(mode="json"), "confidence": confidence})
    if expected is not None:
        langfuse.score_current_trace(
            name="category-correct", value=1 if out.category == expected else 0, data_type="BOOLEAN"
        )
    return out, confidence


def main() -> None:
    langfuse = init_tracing()
    classifier = build_classifier()

    correct = 0
    for ticket_id, text, expected in TICKETS:
        out, confidence = classify_ticket(classifier, ticket_id, text, expected)
        ok = out.category == expected
        correct += ok
        print(f"{'OK ' if ok else 'BAD'} {ticket_id} {out.category.value:20} urgent={out.urgent!s:5} "
              f"sentiment={out.sentiment.value:13} confidence={confidence}")

    langfuse.flush()
    print(f"\n{correct}/{len(TICKETS)} categories correct.")
    print("Open Langfuse -> Tracing -> 'classify-ticket' (environment: development).")


if __name__ == "__main__":
    main()
