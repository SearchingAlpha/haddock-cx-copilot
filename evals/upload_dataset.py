"""Upload data/tickets.jsonl to the Langfuse dataset `cx-tickets`. Idempotent: item id = ticket id.

    python -m evals.upload_dataset
"""

from app.data import load_tickets
from app.observability import init_tracing

DATASET = "cx-tickets"


def ticket_input(ticket) -> dict:
    """What the pipeline gets. Labels go to expected_output, never to input."""
    return ticket.model_dump(mode="json", exclude={"labels"})


def main() -> None:
    langfuse = init_tracing()
    try:
        langfuse.get_dataset(DATASET)
    except Exception:
        langfuse.create_dataset(
            name=DATASET,
            description="40 synthetic haddock support tickets with ground-truth labels (data/tickets.jsonl).",
            metadata={"source": "data/tickets.jsonl", "spec": "docs/specs/data.md"},
        )
    tickets = load_tickets()
    for t in tickets:
        langfuse.create_dataset_item(
            dataset_name=DATASET,
            id=f"{DATASET}-{t.id}",  # same id = update, so re-running never duplicates
            input=ticket_input(t),
            expected_output=t.labels.model_dump(mode="json"),
            metadata={"trap": t.labels.trap.value if t.labels.trap else None, "customer_id": t.customer_id},
        )
    langfuse.flush()
    print(f"{DATASET}: {len(tickets)} items upserted")


if __name__ == "__main__":
    main()
