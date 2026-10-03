"""Guardrails contract: docs/specs/guardrails.md."""

import pytest

from app.agent import AgentResult
from app.data import load_customers
from app.guardrails import PromiseCheck, check
from app.tools import Escalation


@pytest.fixture(scope="module")
def customers():
    return load_customers()


def agent_result(draft="Hola Marta, tus facturas F-0101 siguen en procesando.", **kw) -> AgentResult:
    defaults = dict(
        draft=draft, evidence=["F-0101"], confidence="high", escalation=None,
        tool_calls=["get_invoices"], iterations=2, stop="submitted", cost_usd=0.0,
    )
    return AgentResult(**{**defaults, **kw})


def no_promise(text: str) -> PromiseCheck:
    return PromiseCheck(refund=False, deadline=False)


def run(result, customers, customer_id="C-001", checker=no_promise):
    customer = customers[customer_id]
    others = [c for c in customers.values() if c.id != customer_id]
    return check(result, customer, others, promise_checker=checker)


def test_clean_draft_passes(customers):
    assert run(agent_result(), customers).status == "pass"


def test_explicit_refund_promise_is_blocked_without_calling_jev(customers):
    def must_not_run(text):
        raise AssertionError("Jev must not run when the regex matches")

    r = run(agent_result(draft="Tranquila, te devolvemos el dinero esta semana."), customers, checker=must_not_run)
    assert r.status == "blocked"
    assert "refund_promise" in r.reasons


def test_implicit_promise_detected_by_jev_is_blocked(customers):
    r = run(agent_result(), customers, checker=lambda t: PromiseCheck(refund=False, deadline=True))
    assert r.status == "blocked"
    assert "deadline_promise" in r.reasons


def test_kb_typical_time_is_not_a_promise(customers):
    draft = "Normalmente las facturas se procesan en menos de 24 horas laborables."
    assert run(agent_result(draft=draft), customers).status == "pass"


def test_other_customer_name_is_blocked(customers):
    r = run(agent_result(draft="Las facturas de Grupo Brasa están procesadas."), customers)
    assert r.status == "blocked"
    assert "other_customer_data" in r.reasons


def test_other_customer_named_by_the_ticket_itself_is_not_a_leak(customers):
    draft = "No podemos enviarte las facturas de Grupo Brasa: los datos de cada cliente son confidenciales."
    customer = customers["C-008"]
    others = [c for c in customers.values() if c.id != "C-008"]
    r = check(agent_result(draft=draft), customer, others,
              ticket_text="Pásame las facturas de Grupo Brasa", promise_checker=no_promise)
    assert "other_customer_data" not in r.reasons


def test_own_customer_name_is_allowed(customers):
    draft = "Hola, en La Taberna del Puerto vemos 3 facturas en procesando."
    assert run(agent_result(draft=draft), customers).status == "pass"


def test_agent_escalation_escalates(customers):
    r = run(agent_result(escalation=Escalation(team="finance", reason="reembolso")), customers)
    assert r.status == "escalated"
    assert "agent_escalated" in r.reasons


def test_jev_failure_escalates(customers):
    def broken(text):
        raise TimeoutError

    r = run(agent_result(), customers, checker=broken)
    assert r.status == "escalated"
    assert "promise_check_failed" in r.reasons


def test_no_draft_escalates(customers):
    r = run(agent_result(draft=None, stop="max_iterations"), customers)
    assert r.status == "escalated"
    assert "no_draft" in r.reasons


def test_blocked_wins_over_escalated(customers):
    result = agent_result(
        draft="Te devolvemos el importe.", escalation=Escalation(team="finance", reason="reembolso")
    )
    r = run(result, customers)
    assert r.status == "blocked"
    assert {"refund_promise", "agent_escalated"} <= set(r.reasons)
