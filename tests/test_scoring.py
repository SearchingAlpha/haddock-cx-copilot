"""Deterministic eval scores: docs/specs/evals.md."""

import pytest

from evals.scoring import (
    calibration, classification_scores, escalation_correct, format_ok, guardrail_blocked, tool_recall,
)

EXPECTED = {
    "category": "invoices", "priority": "urgent", "sentiment": "negative", "language": "es",
    "expected_tools": ["get_invoices", "search_kb"], "should_escalate": True,
}


def output(**kw):
    base = {
        "status": "escalated", "reasons": ["agent_escalated"], "tool_calls": ["get_invoices"],
        "classification": {"category": "invoices", "priority": "high", "sentiment": "negative", "language": "es"},
    }
    return {**base, **kw}


def test_classification_scores_per_field():
    scores = classification_scores(output(), EXPECTED)
    assert scores == {"category_correct": True, "priority_correct": False,
                      "sentiment_correct": True, "language_correct": True}


def test_escalation_correct():
    assert escalation_correct(output(), EXPECTED)
    assert not escalation_correct(output(status="ready"), EXPECTED)


def test_tool_recall_is_a_fraction():
    assert tool_recall(output(), EXPECTED) == 0.5


def test_tool_recall_with_no_expected_tools_is_1():
    assert tool_recall(output(tool_calls=[]), {**EXPECTED, "expected_tools": []}) == 1.0


def test_tool_recall_is_skipped_when_the_agent_did_not_run():
    assert tool_recall(output(reasons=["classify_only"], tool_calls=[]), EXPECTED) is None


def test_format_ok_email_rejects_markdown():
    assert format_ok("Hola,\n1. Abre Ajustes.\nUn saludo", "email")
    assert not format_ok("Hola, abre **Ajustes**", "email")
    assert not format_ok("# Pasos\nAbre Ajustes", "email")


def test_format_ok_chat_rejects_long_replies():
    assert format_ok("Hola " * 120, "chat")
    assert not format_ok("Hola " * 200, "chat")
    assert not format_ok("# Pasos\nAbre Ajustes", "chat")


def test_judge_evidence_is_parsed_not_double_escaped():
    from evals.judge import readable_evidence

    text = readable_evidence([{"tool": "get_customer", "input": {}, "output": '{"plan": "pro"}'}])
    assert '"plan": "pro"' in text
    assert '\\"plan\\"' not in text


def test_guardrail_blocked():
    assert guardrail_blocked(output(reasons=["refund_promise", "agent_escalated"]))
    assert not guardrail_blocked(output())


def test_calibration_perfect_and_overconfident():
    perfect = [(0.95, True)] * 19 + [(0.95, False)]
    ece, table = calibration(perfect)
    assert ece == pytest.approx(0.0)
    assert table == [{"bin": "0.9-1.0", "n": 20, "confidence": 0.95, "accuracy": 0.95}]

    overconfident = [(0.9, False)] * 10
    assert calibration(overconfident)[0] == pytest.approx(0.9)


def test_confidence_of_exactly_1_falls_in_the_last_bin():
    assert calibration([(1.0, True)])[1][0]["bin"] == "0.9-1.0"
