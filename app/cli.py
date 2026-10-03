"""Run the pipeline from the terminal. Spec: docs/specs/pipeline.md.

    python -m app.cli process data/tickets.jsonl --limit 5
    python -m app.cli process data/tickets.jsonl --ids T-020,T-021 -v
"""

import argparse
import textwrap

from app.data import load_customers, load_kb, load_tickets
from app.observability import init_tracing
from app.pipeline import process_ticket
from app.tools import KBIndex


def main() -> None:
    parser = argparse.ArgumentParser(prog="app.cli")
    sub = parser.add_subparsers(dest="command", required=True)
    proc = sub.add_parser("process", help="Process tickets and print a summary")
    proc.add_argument("path")
    proc.add_argument("--limit", type=int)
    proc.add_argument("--ids", help="Comma-separated ticket ids")
    proc.add_argument("-v", "--verbose", action="store_true", help="Print every draft")
    args = parser.parse_args()

    langfuse = init_tracing()
    tickets = load_tickets(args.path)
    if args.ids:
        wanted = set(args.ids.split(","))
        tickets = [t for t in tickets if t.id in wanted]
    tickets = tickets[: args.limit]
    customers, kb = load_customers(), KBIndex(load_kb())

    total_cost, correct = 0.0, 0
    for ticket in tickets:
        r = process_ticket(ticket, customers, kb=kb)
        total_cost += r.cost_usd
        predicted = r.classification.classification.category.value if r.classification else "-"
        expected = ticket.labels.category.value
        correct += predicted == expected
        tools = ",".join(r.agent.tool_calls) if r.agent else "-"
        print(f"{ticket.id} {r.status:9} cat={predicted:9}({'ok' if predicted == expected else expected:9}) "
              f"tools=[{tools}] ${r.cost_usd:.4f} {' '.join(r.reasons)}")
        if args.verbose and r.agent and r.agent.draft:
            print(textwrap.indent(textwrap.fill(r.agent.draft, 100), "    | "))
            print(f"    evidence={r.agent.evidence} confidence={r.agent.confidence}\n")

    langfuse.flush()
    print(f"\n{len(tickets)} tickets, category {correct}/{len(tickets)}, agent cost ${total_cost:.4f}")
    print("Langfuse -> Tracing -> 'process-ticket'")


if __name__ == "__main__":
    main()
