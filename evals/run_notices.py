"""Resolve one problem on a copy of the database and score its proactive notices. Spec: docs/specs/notify.md.

    python -m uv run python -m evals.run_notices evals/results/requests-v1.db P-0004 --run-name notices-v1

Real Sonnet (one call per customer) and real Jev for the promise check.
"""

import argparse
import json
import shutil
from datetime import datetime
from pathlib import Path

from app import db, notify, problems
from app.data import load_customers
from app.observability import init_tracing
from evals.scoring import format_ok

RESULTS_DIR = Path(__file__).resolve().parent / "results"
MONTHS = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre", "octubre",
          "noviembre", "diciembre"]


def spanish_date(iso: str) -> str:
    d = datetime.fromisoformat(iso)
    return f"{d.day} de {MONTHS[d.month - 1]}"


def main() -> None:
    parser = argparse.ArgumentParser(prog="evals.run_notices")
    parser.add_argument("db")
    parser.add_argument("problem_id")
    parser.add_argument("--run-name", default="notices")
    args = parser.parse_args()

    langfuse = init_tracing()
    customers = load_customers()
    work = RESULTS_DIR / f"{args.run_name}.db"
    shutil.copy(args.db, work)
    conn = db.connect(str(work))
    with conn:  # producto closed the issue: skip GitHub, the eval is about the notices
        conn.execute("UPDATE problems SET status = 'resolved', resolved_at = '2026-10-05T10:00:00' WHERE id = ?",
                     (args.problem_id,))
    problem = problems.get_problem(conn, args.problem_id, customers)
    created = notify.on_resolved(conn, args.problem_id, customers)
    items = []
    for tid in created:
        t = db.get_ticket(conn, tid)
        own = [s for s in problem["signals"] if s["customer_id"] == t["customer_id"]]
        dates = {spanish_date(s["created_at"]) for s in own}
        s = {"guardrails_pass": t["state"] == "ready", "cites_own_date": any(d in t["draft"] for d in dates),
             "format_ok": format_ok(t["draft"], "email"), "words": len(t["draft"].split())}
        if t["trace_id"]:
            for name in ("guardrails_pass", "cites_own_date", "format_ok"):
                langfuse.create_score(trace_id=t["trace_id"], name=name, value=float(s[name]))
        items.append({"ticket": tid, "customer": t["customer_id"], "subject": t["subject"], "draft": t["draft"],
                      "reasons": t["reasons"], "scores": s})
        print(f"{tid} pass={s['guardrails_pass']} date={s['cites_own_date']} format={s['format_ok']} "
              f"words={s['words']} {t['reasons'] or ''}")
    langfuse.flush()
    run = {k: round(sum(i["scores"][k] for i in items) / len(items), 3) for k in
           ("guardrails_pass", "cites_own_date", "format_ok")} if items else {}
    run["notices"], run["customers"] = len(items), len(problem["impact"].customers)
    (RESULTS_DIR / f"{args.run_name}.json").write_text(
        json.dumps({"run_name": args.run_name, "problem": args.problem_id, "run": run, "items": items},
                   indent=1, ensure_ascii=False), encoding="utf-8")
    print(f"\n{args.run_name}: {run}")


if __name__ == "__main__":
    main()
