"""Tools contract: docs/specs/tools.md."""

import json

import pytest

from app.data import load_customers, load_kb
from app.tools import KBIndex, ToolContext, execute, tool_definitions


@pytest.fixture(scope="module")
def kb():
    return KBIndex(load_kb())


@pytest.fixture(scope="module")
def customers():
    return load_customers()


def ctx_for(customers, kb, customer_id):
    return ToolContext(customer=customers[customer_id], kb=kb)


def test_search_kb_finds_the_bank_sync_article(kb):
    ids = [hit["id"] for hit in kb.search("el banco no se sincroniza desde hace días")]
    assert "kb-07" in ids


def test_search_kb_ignores_accents_and_case(kb):
    assert kb.search("CONCILIACIÓN bancaria")[0]["id"] == kb.search("conciliacion bancaria")[0]["id"]


def test_get_invoices_only_returns_the_context_customer(customers, kb):
    result = execute("get_invoices", {}, ctx_for(customers, kb, "C-001"))
    invoices = json.loads(result.content)
    assert {i["id"] for i in invoices} == {"F-0101", "F-0102", "F-0103", "F-0104"}


def test_get_invoices_filters_by_status(customers, kb):
    result = execute("get_invoices", {"status": "processing"}, ctx_for(customers, kb, "C-001"))
    assert len(json.loads(result.content)) == 3


def test_get_bank_sync_status_shows_the_error(customers, kb):
    result = execute("get_bank_sync_status", {}, ctx_for(customers, kb, "C-002"))
    [bank] = json.loads(result.content)
    assert bank["status"] == "error"
    assert "PSD2" in bank["error"]


def test_no_tool_accepts_a_customer_id():
    for tool in tool_definitions():
        assert "customer_id" not in tool["input_schema"].get("properties", {}), tool["name"]


def test_unknown_tool_returns_an_error(customers, kb):
    result = execute("delete_customer", {}, ctx_for(customers, kb, "C-001"))
    assert result.is_error


def test_invalid_input_returns_an_error(customers, kb):
    result = execute("get_invoices", {"status": "lost"}, ctx_for(customers, kb, "C-001"))
    assert result.is_error


def test_escalate_to_human_records_the_escalation(customers, kb):
    result = execute(
        "escalate_to_human", {"team": "finance", "reason": "Pide reembolso"}, ctx_for(customers, kb, "C-004")
    )
    assert result.escalation.team == "finance"
