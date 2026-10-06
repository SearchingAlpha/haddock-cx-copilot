"""Load the radar's history into the working database (HADDOCK_DB, default haddock.db). Spec: docs/specs/radar.md.

    python -m uv run python -m scripts.radar_backfill            # data/radar/tickets.jsonl, ~1 min, cents
    python -m uv run python -m scripts.radar_backfill --reset    # forget signals, problems and history first
    python -m uv run python -m scripts.radar_backfill --draft    # also draft the product request of each candidate

The tickets enter as source=history: they feed /radar and never show in the queue.
"""

import argparse

from app import db, radar
from app.data import load_customers, load_radar_tickets
from app.observability import init_tracing

RADAR_TABLES = ("notices", "product_requests", "signals", "problem_events", "problems")


def reset(conn) -> None:
    with conn:
        for table in RADAR_TABLES:
            conn.execute(f"DELETE FROM {table}")
        conn.execute("DELETE FROM results WHERE ticket_id IN (SELECT id FROM tickets WHERE kind = 'proactive')")
        conn.execute("DELETE FROM tickets WHERE source = 'history' OR kind = 'proactive'")
        conn.execute("UPDATE tickets SET problem_id = NULL")


def main() -> None:
    parser = argparse.ArgumentParser(prog="scripts.radar_backfill")
    parser.add_argument("path", nargs="?", default=None)
    parser.add_argument("--reset", action="store_true")
    parser.add_argument("--limit", type=int)
    parser.add_argument("--workers", type=int, default=8)
    parser.add_argument("--draft", action="store_true", help="Sonnet drafts each candidate's request (~$0.02 each)")
    args = parser.parse_args()

    langfuse = init_tracing()
    conn = db.connect()
    if args.reset:
        reset(conn)
    tickets = (load_radar_tickets(args.path) if args.path else load_radar_tickets())[: args.limit]
    signals = radar.backfill(conn, tickets, load_customers(), workers=args.workers,
                             progress=lambda n, s: print(f"\r  {n}/{len(tickets)} {s.ticket_id}", end="", flush=True))
    if args.draft:
        customers = load_customers()
        for (pid,) in conn.execute("SELECT p.id FROM problems p LEFT JOIN product_requests r ON r.problem_id = p.id "
                                   "WHERE p.status = 'candidate' AND r.problem_id IS NULL").fetchall():
            print(f"\n  drafting {pid}: {radar.draft_for(conn, pid, customers).draft.title}", end="")
    langfuse.flush()
    print()
    for r in conn.execute("SELECT id, status, title FROM problems WHERE status != 'merged' ORDER BY id"):
        n = conn.execute("SELECT COUNT(*) FROM signals WHERE problem_id = ?", (r["id"],)).fetchone()[0]
        print(f"  {r['id']} {r['status']:9} {n:3} tickets  {r['title']}")
    print(f"{len(signals)} new signals. Open /radar.")


if __name__ == "__main__":
    main()
