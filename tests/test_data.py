"""Data contract: docs/specs/data.md."""

from collections import Counter

import pytest

from app.data import load_customers, load_kb, load_tickets
from app.domain import TOOL_NAMES, Category, Trap


@pytest.fixture(scope="module")
def kb():
    return load_kb()


@pytest.fixture(scope="module")
def customers():
    return load_customers()


@pytest.fixture(scope="module")
def tickets():
    return load_tickets()


def test_kb_has_the_15_articles_of_the_spec(kb):
    assert sorted(a.id for a in kb) == [f"kb-{i:02d}" for i in range(1, 16)]


def test_kb_articles_have_body(kb):
    for article in kb:
        assert len(article.body) > 200, article.id


def test_customer_ids_are_unique_and_match_keys(customers):
    assert len(customers) >= 10
    for key, customer in customers.items():
        assert key == customer.id


def test_ticket_ids_are_unique(tickets):
    ids = [t.id for t in tickets]
    assert len(ids) == len(set(ids))


def test_every_ticket_references_a_known_customer(tickets, customers):
    for t in tickets:
        assert t.customer_id in customers, t.id


def test_expected_tools_are_known(tickets):
    for t in tickets:
        assert set(t.labels.expected_tools) <= TOOL_NAMES, t.id


def test_relevant_articles_exist(tickets, kb):
    kb_ids = {a.id for a in kb}
    for t in tickets:
        assert set(t.labels.relevant_articles) <= kb_ids, t.id


def test_every_category_has_at_least_3_tickets(tickets):
    counts = Counter(t.labels.category for t in tickets)
    for category in Category:
        assert counts[category] >= 3, f"{category.value}: {counts[category]}"


def test_every_trap_appears(tickets):
    traps = {t.labels.trap for t in tickets if t.labels.trap}
    assert traps == set(Trap)


def test_traps_that_need_a_human_are_escalated(tickets):
    must_escalate = {Trap.refund_request, Trap.cross_customer, Trap.prompt_injection}
    for t in tickets:
        if t.labels.trap in must_escalate:
            assert t.labels.should_escalate, t.id


def test_every_ticket_has_key_points(tickets):
    for t in tickets:
        assert t.labels.key_points, t.id


def test_there_are_about_40_tickets(tickets):
    assert 35 <= len(tickets) <= 50
