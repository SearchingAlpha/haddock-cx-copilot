"""Build haddock.golden.db for the public demo: the live queue plus a precomputed radar. Spec: docs/specs/deploy.md.

    python -m uv run python -m scripts.build_golden
    python -m uv run python -m scripts.build_golden --base haddock.db --radar evals/results/notices-v1.db \\
        --requested P-0009=7

The public demo never calls an LLM, so every radar state must be in the file:
- candidate problems with their drafted product request,
- one problem `requested` (optional, --requested P-xxxx=<issue number>, needs GITHUB_REPO for the link),
- one problem `resolved` with its proactive notices in the queue.
Reviews are dropped: every session starts from the same state.
"""

import argparse
import os
import shutil
import sqlite3
from pathlib import Path

from app import db

RADAR_TABLES = ("signals", "problems", "problem_events", "product_requests", "notices")


def build(base: str, radar_db: str, out: str, requested: dict[str, int]) -> dict:
    Path(out).unlink(missing_ok=True)
    shutil.copy(base, out)
    db.connect(out).close()  # migrate the copy to the current schema
    conn = sqlite3.connect(out)
    db.connect(radar_db).close()
    conn.execute("ATTACH DATABASE ? AS radar", (radar_db,))
    with conn:
        conn.execute("DELETE FROM reviews")
        conn.execute("UPDATE tickets SET state = (SELECT r.status FROM results r WHERE r.ticket_id = tickets.id) "
                     "WHERE state IN ('sent', 'rejected')")  # back to «to review»
        for table in RADAR_TABLES:
            conn.execute(f"DELETE FROM {table}")
            cols = ", ".join(r[1] for r in conn.execute(f"PRAGMA main.table_info({table})"))
            conn.execute(f"INSERT INTO main.{table} ({cols}) SELECT {cols} FROM radar.{table}")
        cols = ", ".join(r[1] for r in conn.execute("PRAGMA main.table_info(tickets)"))
        conn.execute(f"INSERT OR IGNORE INTO main.tickets ({cols}) SELECT {cols} FROM radar.tickets "
                     "WHERE source = 'history' OR kind = 'proactive'")
        rcols = ", ".join(r[1] for r in conn.execute("PRAGMA main.table_info(results)"))
        conn.execute(f"INSERT OR IGNORE INTO main.results ({rcols}) SELECT {rcols} FROM radar.results r "
                     "WHERE r.ticket_id IN (SELECT id FROM radar.tickets WHERE kind = 'proactive')")
        repo = os.environ.get("GITHUB_REPO", "")
        for pid, number in requested.items():
            url = f"https://github.com/{repo}/issues/{number}" if repo else None
            conn.execute("UPDATE problems SET status = 'requested', github_number = ?, github_url = ? WHERE id = ?",
                         (number, url, pid))
            conn.execute("UPDATE product_requests SET status = 'approved', decision = 'approve' WHERE problem_id = ?",
                         (pid,))
    counts = {s: n for s, n in conn.execute("SELECT status, COUNT(*) FROM problems GROUP BY status")}
    counts["notices"] = conn.execute("SELECT COUNT(*) FROM notices").fetchone()[0]
    counts["live_tickets"] = conn.execute("SELECT COUNT(*) FROM tickets WHERE source = 'live' AND kind = 'inbound'"
                                          ).fetchone()[0]
    conn.close()
    return counts


def main() -> None:
    parser = argparse.ArgumentParser(prog="scripts.build_golden")
    parser.add_argument("--base", default="haddock.db", help="The live queue: processed T- tickets")
    parser.add_argument("--radar", default="evals/results/notices-v1.db", help="A radar run with drafts and notices")
    parser.add_argument("--out", default="haddock.golden.db")
    parser.add_argument("--requested", nargs="*", default=[], help="P-xxxx=<issue number>")
    args = parser.parse_args()
    requested = {k: int(v) for k, v in (r.split("=") for r in args.requested)}
    print(build(args.base, args.radar, args.out, requested))


if __name__ == "__main__":
    main()
