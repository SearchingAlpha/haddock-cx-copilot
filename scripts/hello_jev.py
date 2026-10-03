"""Smoke test: classify 3 Spanish tickets with Jev inside one Langfuse trace.

Checks two open questions before Phase 2:
1. Does Jev classify Spanish tickets correctly?
2. Does the Jev call appear in the Langfuse trace (pydantic-ai OpenTelemetry spans)?
"""

from enum import Enum

from dotenv import load_dotenv
from langfuse import get_client, observe
from pydantic import BaseModel, Field
from pydantic_ai import Agent

load_dotenv()


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
    # (text, expected category)
    ("Hola, subí tres facturas de Makro el lunes y siguen en 'procesando'. ¿Es normal?", Category.invoices),
    ("¡Llevamos 4 días sin que se sincronice el banco y el cierre de mes es mañana! Esto es un desastre.", Category.bank_reconciliation),
    ("Buenas, ¿cómo conecto el TPV de Last.app con haddock para ver las ventas?", Category.pos_integration),
]

classifier = Agent("typesafe:jev-latest", output_type=Classification)


@observe(name="hello-jev")
def run() -> tuple[int, str]:
    correct = 0
    for text, expected in TICKETS:
        result = classifier.run_sync(text)
        out = result.output
        confidence = result.response.provider_details.get("confidence") if result.response.provider_details else None
        ok = out.category == expected
        correct += ok
        print(f"{'OK ' if ok else 'BAD'} {out.category.value:20} urgent={out.urgent!s:5} "
              f"sentiment={out.sentiment.value:13} confidence={confidence}")
    return correct, get_client().get_current_trace_id() or ""


def main() -> None:
    langfuse = get_client()
    if not langfuse.auth_check():
        raise SystemExit("Langfuse auth failed: check LANGFUSE_* in .env")
    Agent.instrument_all()  # pydantic-ai -> OpenTelemetry -> Langfuse

    correct, trace_id = run()
    langfuse.flush()
    print(f"\n{correct}/{len(TICKETS)} categories correct.")
    if trace_id:
        print(langfuse.get_trace_url(trace_id=trace_id))


if __name__ == "__main__":
    main()
