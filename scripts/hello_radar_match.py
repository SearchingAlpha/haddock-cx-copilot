"""Spike for the radar (docs/specs/radar.md): can Jev answer the signal and the "same problem?" questions?

    python -m uv run python -m scripts.hello_radar_match [--n 30]

Part A: component and kind on a sample of radar tickets, Jev against Haiku.
Part B: 20 ticket/problem pairs (10 same, 10 hard negatives from decoys), Jev against Haiku.
"""

import argparse
import random

from app.config import FALLBACK_CLASSIFIER_MODEL
from app.data import load_radar_tickets, load_radar_truth
from app.observability import init_tracing
from app.problems import jev_same_problem, match_text
from app.signals import Signal, typed_signal

# The decoy component -> the planted problem it looks like
LOOKS_LIKE = {"invoices.ocr": "P1", "invoices.duplicates": "P1", "bank.sync": "P2", "pos.sync": "P3",
              "pos.sales": "P3", "inventory.recipes": "P4", "reports.export": "P5"}


def _signal(t) -> Signal:
    return Signal(t.id, t.customer_id, t.created_at.isoformat(), f"{t.subject}\n\n{t.body}",
                  t.labels.component, t.labels.kind, t.labels.entity, symptom=t.subject)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--n", type=int, default=30)
    args = parser.parse_args()
    langfuse = init_tracing()
    rng = random.Random(1)
    tickets, truth = load_radar_tickets(), load_radar_truth()

    print("== A: component and kind")
    sample = rng.sample(tickets, args.n)
    for label, model in (("jev", None), ("haiku", FALLBACK_CLASSIFIER_MODEL)):
        comp = kind = 0
        for t in sample:
            out, conf, _ = typed_signal(f"{t.subject}\n\n{t.body}", model=model)
            comp += out.component == t.labels.component
            kind += out.kind == t.labels.kind
            if label == "jev" and (out.kind != t.labels.kind or out.component != t.labels.component):
                print(f"  {t.id} expected {t.labels.component.value}/{t.labels.kind.value} "
                      f"got {out.component.value}/{out.kind.value} conf={conf}")
        print(f"  {label}: component {comp}/{len(sample)}  kind {kind}/{len(sample)}")

    print("== B: same problem?")
    planted = [t for t in tickets if t.labels.problem_id and t.labels.problem_id != "P7"]
    decoys = [t for t in tickets if t.labels.decoy and t.labels.component.value in LOOKS_LIKE]
    pairs = [(t, t.labels.problem_id, True) for t in rng.sample(planted, 10)]
    pairs += [(t, LOOKS_LIKE[t.labels.component.value], False) for t in rng.sample(decoys, 10)]
    for label, model in (("jev", None), ("haiku", FALLBACK_CLASSIFIER_MODEL)):
        right = 0
        for t, pid, same in pairs:
            example = next(x for x in tickets if x.labels.problem_id == pid and x.id != t.id)
            doc = f"{truth[pid]['title']}\n- {example.subject}: {example.body[:200]}"
            m = jev_same_problem(match_text(doc, _signal(t)), model=model)
            right += m.same == same
            if m.same != same or label == "jev":
                print(f"  {label} {t.id} vs {pid} expected={same} got={m.same} conf={m.confidence}")
        print(f"  {label}: {right}/{len(pairs)}")
    langfuse.flush()


if __name__ == "__main__":
    main()
