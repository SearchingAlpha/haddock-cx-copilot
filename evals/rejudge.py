"""Re-judge saved experiment outputs with another judge model, without re-running the pipeline.

    python -m evals.rejudge evals/results/prompt-v1-judge-v3.json --model claude-sonnet-5-5

Used to check the judge itself: if two judges disagree a lot, the score is noise, not signal.
"""

import argparse
import json
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from app.data import load_tickets
from app.observability import init_tracing
from evals.judge import judge


def main() -> None:
    parser = argparse.ArgumentParser(prog="evals.rejudge")
    parser.add_argument("results", nargs="+")
    parser.add_argument("--model", required=True)
    args = parser.parse_args()

    langfuse = init_tracing()
    tickets = {t.id: t for t in load_tickets()}
    for path in args.results:
        report = json.loads(Path(path).read_text(encoding="utf-8"))
        items = [i for i in report["items"] if i["output"].get("draft")]

        def rejudge(item):
            t = tickets[item["ticket"]]
            v = judge(f"{t.subject}\n\n{t.body}", t.labels.key_points, item["output"]["draft"],
                      item["output"]["tool_outputs"], model=args.model)
            return item["ticket"], v

        with ThreadPoolExecutor(4) as pool:
            verdicts = dict(pool.map(rejudge, items))
        old = {i["ticket"]: i["scores"].get("groundedness") for i in items}
        new = {t: v.grounded for t, v in verdicts.items()}
        agree = sum(old[t] == new[t] for t in new) / len(new)
        print(f"\n{report['run_name']} judged by {args.model}: n={len(new)}")
        print(f"  groundedness  old judge {sum(old.values()) / len(old):.3f}  new judge {sum(new.values()) / len(new):.3f}"
              f"  agreement {agree:.0%}")
        print(f"  key_points    new judge {sum(v.coverage for v in verdicts.values()) / len(verdicts):.3f}")
        for t, v in sorted(verdicts.items()):
            if v.unsupported_claims:
                print(f"    {t}: {'; '.join(v.unsupported_claims)[:200]}")
    langfuse.flush()


if __name__ == "__main__":
    main()
