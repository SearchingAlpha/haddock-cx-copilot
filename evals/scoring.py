"""Deterministic scores. Spec: docs/specs/evals.md. No network: unit-tested in tests/test_scoring.py."""

import re

from app.guardrails import BLOCKING

CLASSIFICATION_FIELDS = ("category", "priority", "sentiment", "language")


def classification_scores(output: dict, expected: dict) -> dict[str, bool]:
    predicted = output.get("classification") or {}
    return {f"{f}_correct": predicted.get(f) == expected[f] for f in CLASSIFICATION_FIELDS if predicted}


def escalation_correct(output: dict, expected: dict) -> bool:
    return (output["status"] == "escalated") == expected["should_escalate"]


def tool_recall(output: dict, expected: dict) -> float | None:
    if output.get("tool_calls") is None or "classify_only" in output.get("reasons", []):
        return None
    wanted = set(expected["expected_tools"])
    if not wanted:
        return 1.0
    return len(wanted & set(output["tool_calls"])) / len(wanted)


def format_ok(draft: str, channel: str) -> bool:
    """email: no markdown. chat: concise (150 words) and no headings. Prompt rules: prompts/cx-agent-system.md."""
    no_headings = not re.search(r"^\s*#", draft, re.MULTILINE)
    if channel == "email":
        return "**" not in draft and no_headings
    return len(draft.split()) <= 150 and no_headings


def guardrail_blocked(output: dict) -> bool:
    return bool(BLOCKING & set(output.get("reasons", [])))


def calibration(pairs: list[tuple[float, bool]], bins: int = 10) -> tuple[float, list[dict]]:
    """Expected calibration error and the per-bin table.

    pairs: (confidence, correct) per ticket. ECE = sum over bins of |avg confidence - accuracy| * share.
    """
    if not pairs:
        return 0.0, []
    table, ece = [], 0.0
    for b in range(bins):
        lo, hi = b / bins, (b + 1) / bins
        in_bin = [(c, ok) for c, ok in pairs if lo <= c < hi or (b == bins - 1 and c == 1.0)]
        if not in_bin:
            continue
        conf = sum(c for c, _ in in_bin) / len(in_bin)
        acc = sum(ok for _, ok in in_bin) / len(in_bin)
        ece += abs(conf - acc) * len(in_bin) / len(pairs)
        table.append({"bin": f"{lo:.1f}-{hi:.1f}", "n": len(in_bin), "confidence": round(conf, 3),
                      "accuracy": round(acc, 3)})
    return ece, table
