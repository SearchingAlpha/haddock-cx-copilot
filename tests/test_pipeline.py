"""Pipeline routing: docs/specs/pipeline.md. Classifier, agent and Jev are stubbed."""

import pytest

from app import pipeline
from app.agent import AgentResult
from app.classify import ClassifyResult, TicketClassification
from app.data import load_customers, load_kb, load_tickets
from app.domain import Category, Language, Priority, Sentiment
from app.guardrails import PromiseCheck
from app.tools import KBIndex


def classified(confidence):
    c = TicketClassification(
        category=Category.invoices, priority=Priority.normal, sentiment=Sentiment.neutral, language=Language.es
    )
    conf = None if confidence is None else {"category": confidence}
    return ClassifyResult(classification=c, confidence=conf, model="test")


def drafted(draft="Hola, la factura F-0101 está en procesando."):
    return AgentResult(
        draft=draft, evidence=["F-0101"], confidence="high", escalation=None,
        tool_calls=["get_invoices"], iterations=2, stop="submitted", cost_usd=0.01,
    )


@pytest.fixture
def stubbed(monkeypatch):
    calls = {"agent": 0}
    state = {"confidence": 0.9, "draft": drafted()}

    monkeypatch.setattr(pipeline, "classify", lambda subject, body, **kw: classified(state["confidence"]))

    def fake_agent(ticket, ctx, **kw):
        calls["agent"] += 1
        return state["draft"]

    monkeypatch.setattr(pipeline, "run_agent", fake_agent)
    monkeypatch.setattr(pipeline, "jev_promise_check", lambda text: PromiseCheck(refund=False, deadline=False))
    return calls, state


@pytest.fixture(scope="module")
def world():
    return load_customers(), KBIndex(load_kb()), next(t for t in load_tickets() if t.customer_id == "C-001")


def test_confident_ticket_with_clean_draft_is_ready(stubbed, world):
    customers, kb, ticket = world
    result = pipeline.process_ticket(ticket, customers, kb=kb)
    assert result.status == "ready"


def test_low_confidence_flags_the_category_but_never_escalates(stubbed, world):
    calls, state = stubbed
    state["confidence"] = 0.3
    customers, kb, ticket = world

    result = pipeline.process_ticket(ticket, customers, kb=kb)

    assert result.status == "ready"
    assert result.review_category
    assert calls["agent"] == 1


def test_high_confidence_is_not_flagged(stubbed, world):
    customers, kb, ticket = world
    assert not pipeline.process_ticket(ticket, customers, kb=kb).review_category


def test_fallback_without_confidence_still_runs_the_agent(stubbed, world):
    calls, state = stubbed
    state["confidence"] = None
    customers, kb, ticket = world

    pipeline.process_ticket(ticket, customers, kb=kb)
    assert calls["agent"] == 1


def test_classify_only_never_calls_the_agent(stubbed, world):
    calls, _ = stubbed
    customers, kb, ticket = world

    result = pipeline.process_ticket(ticket, customers, kb=kb, options=pipeline.RunOptions(classify_only=True))

    assert calls["agent"] == 0
    assert result.reasons == ["classify_only"]


def test_blocked_draft_is_escalated(stubbed, world):
    _, state = stubbed
    state["draft"] = drafted(draft="Te devolvemos el dinero hoy mismo.")
    customers, kb, ticket = world

    result = pipeline.process_ticket(ticket, customers, kb=kb)

    assert result.status == "escalated"
    assert "refund_promise" in result.reasons
