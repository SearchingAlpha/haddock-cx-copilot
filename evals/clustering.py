"""Scores for the radar's clustering against the planted truth. Pure functions. Spec: docs/specs/evals.md (Radar)."""

from collections import Counter, defaultdict
from datetime import datetime
from math import comb


def ari(truth: list, pred: list) -> float:
    """Adjusted Rand index, from the contingency table. 1 = same partition, ~0 = chance."""
    n = len(truth)
    if n < 2:
        return 1.0
    pairs = Counter(zip(truth, pred))
    index = sum(comb(c, 2) for c in pairs.values())
    sum_a = sum(comb(c, 2) for c in Counter(truth).values())
    sum_b = sum(comb(c, 2) for c in Counter(pred).values())
    expected = sum_a * sum_b / comb(n, 2)
    maximum = (sum_a + sum_b) / 2
    return 1.0 if maximum == expected else (index - expected) / (maximum - expected)


def scores(pred: dict[str, str | None], truth: dict[str, str | None]) -> dict:
    """pred/truth: ticket id -> problem id, or None (no problem: noise, decoy, how_to)."""
    ids = sorted(truth)
    # For ARI a ticket without a problem is its own singleton: leaving noise out is right, not a cluster.
    t = [truth[i] or f"_t{i}" for i in ids]
    p = [pred.get(i) or f"_p{i}" for i in ids]

    clusters: dict[str, list[str]] = defaultdict(list)
    for i in ids:
        if pred.get(i):
            clusters[pred[i]].append(i)
    clustered = sum(len(v) for v in clusters.values())
    purity = (sum(Counter(truth[i] or "noise" for i in members).most_common(1)[0][1]
                  for members in clusters.values()) / clustered) if clustered else 0.0
    mixed = sum(1 for members in clusters.values() if len({truth[i] for i in members if truth[i]}) > 1)

    noise = [i for i in ids if truth[i] is None]
    planted = [i for i in ids if truth[i]]
    return {
        "ari": round(ari(t, p), 3),
        "purity": round(purity, 3),
        "planted_recall": round(sum(1 for i in planted if pred.get(i)) / len(planted), 3) if planted else None,
        "noise_kept_out": round(sum(1 for i in noise if not pred.get(i)) / len(noise), 3) if noise else None,
        "noise_in_problems": sum(1 for i in noise if pred.get(i)),
        "problems_found": len(clusters),
        "mixed_problems": mixed,  # a predicted problem that holds two planted problems
    }


def per_problem(pred: dict[str, str | None], truth: dict[str, str | None], planted: dict[str, dict],
                found: dict[str, dict], created_at: dict[str, str]) -> list[dict]:
    """For each planted problem: its main predicted problem, the split, and when it was detected.

    found: predicted problem id -> row of the problems table (status, detected_at, detected_at_n).
    """
    out = []
    for pid, p in planted.items():
        tickets = [i for i in sorted(truth) if truth[i] == pid]
        preds = Counter(pred.get(i) for i in tickets if pred.get(i))
        main = preds.most_common(1)[0][0] if preds else None
        row = found.get(main) or {}
        detected = row.get("detected_at")
        start = datetime.fromisoformat(p["start"])
        out.append({
            "planted": pid,
            "title": p["title"],
            "tickets": len(tickets),
            "main_problem": main,
            "main_share": round(preds[main] / len(tickets), 3) if main else 0.0,
            "splits": len(preds),
            "status": row.get("status"),
            "detected_at_n": row.get("detected_at_n"),
            "planted_before_detection": sum(1 for i in tickets if detected and created_at[i] <= detected),
            "days_to_detect": round((datetime.fromisoformat(detected) - start).total_seconds() / 86400, 1)
            if detected else None,
        })
    return out


def accuracy(signals: list[dict], labels: dict[str, dict], field: str, only_planted: bool = False) -> float | None:
    rows = [s for s in signals if not only_planted or labels[s["ticket_id"]]["problem_id"]]
    if not rows:
        return None
    return round(sum(s[field] == labels[s["ticket_id"]][field] for s in rows) / len(rows), 3)
