"""Draft the product request of every candidate problem and score it. Spec: docs/specs/product-request.md.

    python -m uv run python -m evals.run_requests evals/results/radar-jev-v4.db --run-name requests-v1

Works on a copy of the database: the drafts never touch the source. Real Sonnet calls (~$0.03 each).
"""

import argparse
import json
import shutil
from pathlib import Path

from app import db, problems, radar
from app.data import load_customers
from app.observability import init_tracing

RESULTS_DIR = Path(__file__).resolve().parent / "results"


def score(problem: dict, req, customers) -> dict:
    d = req.draft
    quotes = len(d.evidence)
    text = " ".join([d.title, d.summary, req.body_md])
    names = [n for c in customers.values() for n in (c.name, c.contact_name)]
    return {
        "quotes": quotes,
        "quotes_literal": round((quotes - len(req.dropped)) / quotes, 3) if quotes else 0.0,
        "entity_named": (problem["entity"] or "") .split()[-1].lower() in (d.title + d.summary).lower()
        if problem["entity"] else None,
        "no_pii": not any(n in text for n in names),
        "title_ok": len(d.title) <= 90,
        "steps": len(d.repro_steps),
        "criteria": len(d.acceptance_criteria),
        "cost_usd": round(req.cost_usd, 4),
    }


def main() -> None:
    parser = argparse.ArgumentParser(prog="evals.run_requests")
    parser.add_argument("db")
    parser.add_argument("--run-name", default="requests")
    args = parser.parse_args()

    langfuse = init_tracing()
    customers = load_customers()
    RESULTS_DIR.mkdir(exist_ok=True)
    work = RESULTS_DIR / f"{args.run_name}.db"
    shutil.copy(args.db, work)
    conn = db.connect(str(work))
    rows = []
    for (pid,) in conn.execute("SELECT id FROM problems WHERE status = 'candidate' ORDER BY id").fetchall():
        problem = problems.get_problem(conn, pid, customers)
        req = radar.draft_for(conn, pid, customers)
        s = score(problem, req, customers)
        for name, value in s.items():
            if isinstance(value, (bool, int, float)) and value is not None and req.trace_id:
                langfuse.create_score(trace_id=req.trace_id, name=name, value=float(value))
        rows.append({"problem": pid, "title": req.draft.title, "scores": s, "dropped": req.dropped,
                     "body_md": req.body_md})
        print(f"{pid} literal={s['quotes_literal']} entity={s['entity_named']} pii_free={s['no_pii']} "
              f"${s['cost_usd']}  {req.draft.title}")
    langfuse.flush()
    n = len(rows)
    run = {k: round(sum(float(r["scores"][k]) for r in rows if r["scores"][k] is not None)
                    / max(1, sum(1 for r in rows if r["scores"][k] is not None)), 3)
           for k in ("quotes_literal", "entity_named", "no_pii", "title_ok")}
    run["total_cost_usd"] = round(sum(r["scores"]["cost_usd"] for r in rows), 4)
    (RESULTS_DIR / f"{args.run_name}.json").write_text(
        json.dumps({"run_name": args.run_name, "run": run, "items": rows}, indent=1, ensure_ascii=False), encoding="utf-8")
    print(f"\n{args.run_name}: {n} requests  {run}")


if __name__ == "__main__":
    main()
