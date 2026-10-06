"""Run the radar over data/radar/tickets.jsonl on a fresh database and score it. Spec: docs/specs/evals.md (Radar).

    python -m uv run python -m evals.run_clustering --run-name radar-jev
    python -m uv run python -m evals.run_clustering --matcher haiku --run-name radar-haiku-match
    python -m uv run python -m evals.run_clustering --limit 60          # a quick run on the first 60 tickets

Writes evals/results/<run>.json and logs the aggregate scores on a `radar-eval` trace in Langfuse.
The database stays in evals/results/<run>.db (not committed): open it with HADDOCK_DB to see /radar.
"""

import argparse
import json
from datetime import datetime
from pathlib import Path

from app import db, radar
from app.config import FALLBACK_CLASSIFIER_MODEL
from app.data import load_customers, load_radar_tickets, load_radar_truth
from app.observability import init_tracing
from app.problems import jev_same_problem
from evals.clustering import accuracy, per_problem, scores

RESULTS_DIR = Path(__file__).resolve().parent / "results"


def main() -> None:
    parser = argparse.ArgumentParser(prog="evals.run_clustering")
    parser.add_argument("--run-name")
    parser.add_argument("--matcher", choices=["jev", "haiku"], default="jev")
    parser.add_argument("--limit", type=int)
    parser.add_argument("--workers", type=int, default=8)
    args = parser.parse_args()
    run_name = args.run_name or f"radar-{args.matcher}-{datetime.now():%m%d-%H%M}"

    langfuse = init_tracing()
    customers, truth_problems = load_customers(), load_radar_truth()
    tickets = load_radar_tickets()[: args.limit]
    RESULTS_DIR.mkdir(exist_ok=True)
    path = RESULTS_DIR / f"{run_name}.db"
    path.unlink(missing_ok=True)
    conn = db.connect(str(path))

    if args.matcher == "haiku":
        def matcher(text):
            return jev_same_problem(text, model=FALLBACK_CLASSIFIER_MODEL)
    else:
        matcher = jev_same_problem

    def progress(n, s):
        print(f"\r  {n}/{len(tickets)} {s.ticket_id} {s.kind.value:10} {s.problem_id or '-':7}", end="", flush=True)

    started = datetime.now()
    radar.backfill(conn, tickets, customers, workers=args.workers, matcher=matcher, progress=progress)
    print()
    seconds = (datetime.now() - started).total_seconds()

    signals = [dict(r) for r in conn.execute("SELECT * FROM signals")]
    labels = {t.id: t.labels.model_dump(mode="json") for t in tickets}
    pred = {s["ticket_id"]: s["problem_id"] for s in signals}
    truth = {t.id: t.labels.problem_id for t in tickets}
    found = {r["id"]: dict(r) for r in conn.execute("SELECT * FROM problems")}
    created = {t.id: t.created_at.isoformat() for t in tickets}
    planted = {pid: p for pid, p in truth_problems.items() if any(truth[i] == pid for i in truth)}

    run = scores(pred, truth) | {
        "component_accuracy": accuracy(signals, labels, "component"),
        "kind_accuracy": accuracy(signals, labels, "kind"),
        "entity_accuracy_planted": accuracy(signals, labels, "entity", only_planted=True),
        "candidates": sum(1 for r in found.values() if r["status"] == "candidate"),
        "seconds": round(seconds, 1),
    }
    problems = per_problem(pred, truth, planted, found, created)
    # The threshold must fire for every planted problem but the small one (P7), and only for planted ones.
    should = {p["planted"] for p in problems if p["planted"] != "P7"}
    fired = {p["planted"] for p in problems if p["status"] == "candidate"}
    run["planted_detected"] = round(len(should & fired) / len(should), 3) if should else None
    main_ids = {p["main_problem"] for p in problems}
    run["false_candidates"] = sum(1 for pid, r in found.items() if r["status"] == "candidate" and pid not in main_ids)

    with langfuse.start_as_current_observation(name="radar-eval", as_type="span",
                                               input={"run_name": run_name, "options": vars(args)}) as span:
        trace_id = langfuse.get_current_trace_id()
        span.update(output={"run": run, "problems": problems})
    for name, value in run.items():
        if isinstance(value, (int, float)) and value is not None:
            langfuse.create_score(trace_id=trace_id, name=name, value=float(value))
    langfuse.flush()

    report = {"run_name": run_name, "options": vars(args), "run": run, "problems": problems,
              "found": list(found.values()),
              "errors": [{"ticket": s["ticket_id"], "expected": {k: labels[s["ticket_id"]][k] for k in
                                                                 ("problem_id", "component", "kind", "entity")},
                          "got": {k: s[k] for k in ("problem_id", "component", "kind", "entity")},
                          "symptom": s["symptom"]}
                         for s in signals if s["kind"] != labels[s["ticket_id"]]["kind"]
                         or s["component"] != labels[s["ticket_id"]]["component"]]}
    (RESULTS_DIR / f"{run_name}.json").write_text(json.dumps(report, indent=1, ensure_ascii=False), encoding="utf-8")

    print(f"\n{run_name}: {len(tickets)} tickets in {seconds:.0f} s")
    for k, v in run.items():
        print(f"  {k:26} {v}")
    print("\n  planted  tickets  main      share  splits  status     detected_at_n  days")
    for p in problems:
        print(f"  {p['planted']:8} {p['tickets']:7}  {p['main_problem'] or '-':8}  {p['main_share']:5}  "
              f"{p['splits']:6}  {p['status'] or '-':9}  {p['detected_at_n'] or '-':>13}  {p['days_to_detect'] or '-'}")
    print(f"\n  trace: {langfuse.get_trace_url(trace_id=trace_id)}")


if __name__ == "__main__":
    main()
