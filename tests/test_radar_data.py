"""Radar dataset contract: docs/specs/data.md (Radar) and docs/specs/radar.md."""

from collections import Counter
from datetime import datetime

import pytest

from app.data import load_customers, load_radar_tickets, load_radar_truth
from app.domain import CLUSTERED_KINDS, TOOL_NAMES


@pytest.fixture(scope="module")
def customers():
    return load_customers()


@pytest.fixture(scope="module")
def tickets():
    return load_radar_tickets()


@pytest.fixture(scope="module")
def truth():
    return load_radar_truth()


def _has_entity(customer, entity: str) -> bool:
    return entity in {i.supplier for i in customer.invoices} | {i.provider for i in customer.integrations}


def test_size_and_unique_ids(tickets):
    assert 200 <= len(tickets) <= 300
    assert len({t.id for t in tickets}) == len(tickets)


def test_first_ten_customers_are_unchanged(customers):
    assert customers["C-001"].name == "La Taberna del Puerto"
    assert customers["C-010"].name == "Tacos La Güera"
    assert len(customers) == 50


def test_customers_and_tools_are_known(tickets, customers):
    for t in tickets:
        assert t.customer_id in customers, t.id
        assert set(t.labels.expected_tools) <= TOOL_NAMES, t.id


def test_ids_follow_time_order(tickets):
    assert [t.created_at for t in tickets] == sorted(t.created_at for t in tickets)


def test_planted_tickets_match_their_problem(tickets, truth, customers):
    for t in tickets:
        pid = t.labels.problem_id
        if pid is None:
            continue
        p = truth[pid]
        assert t.labels.component.value == p["component"], t.id
        assert t.labels.kind.value == p["kind"], t.id
        assert t.created_at >= datetime.fromisoformat(p["start"]), t.id
        if p["entity"]:
            assert _has_entity(customers[t.customer_id], p["entity"]), t.id


def test_truth_lists_every_planted_ticket(tickets, truth):
    by_problem = Counter(t.labels.problem_id for t in tickets if t.labels.problem_id)
    assert {pid: len(p["tickets"]) for pid, p in truth.items()} == dict(by_problem)


def test_only_bugs_and_features_are_planted(tickets):
    for t in tickets:
        assert (t.labels.problem_id is not None) == (t.labels.kind in CLUSTERED_KINDS), t.id


def test_decoys_share_a_planted_component(tickets, truth):
    planted = {p["component"] for p in truth.values()}
    decoys = [t for t in tickets if t.labels.decoy]
    assert len(decoys) >= 30
    assert sum(t.labels.component.value in planted for t in decoys) >= 25


def test_one_problem_stays_below_the_threshold(truth, customers):
    """P7 has 2 starter customers: the radar must not ask product for it."""
    small = truth["P7"]
    assert len(small["customers"]) < 3
    assert sum(customers[c].billing.monthly_price_eur for c in small["customers"]) < 400
