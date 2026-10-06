"""Closed-loop contract: docs/specs/notify.md. Fake Anthropic and fake GitHub: no network."""

from types import SimpleNamespace

import pytest

from app import db, notify, product_request, radar, views
from app.guardrails import PromiseCheck
from app.notify import Notice
from tests.test_product_request import FakeAnthropic, FakeGitHub, conn, customers, draft  # noqa: F401


def no_promise(text):
    return PromiseCheck(refund=False, deadline=False)


class NoticeWriter:
    """Writes one notice per call; `bad` customers get a draft that names another restaurant."""

    def __init__(self, bad=(), fail=()):
        self.bad, self.fail, self.inputs = set(bad), set(fail), []
        self.messages = SimpleNamespace(parse=self.parse)

    def parse(self, **kw):
        text = kw["messages"][0]["content"]
        self.inputs.append(text)
        if any(f in text for f in self.fail):
            raise TimeoutError
        body = "Hola, el 2 de septiembre nos escribiste por las facturas de Garrido. Ya está resuelto."
        if any(b in text for b in self.bad):
            body += " A Mesón El Fogón también le pasaba."
        usage = SimpleNamespace(input_tokens=500, output_tokens=120, cache_read_input_tokens=0,
                                cache_creation_input_tokens=0)
        return SimpleNamespace(parsed_output=Notice(subject="Facturas de Garrido: resuelto", body=body),
                               stop_reason="end_turn", usage=usage)


@pytest.fixture
def requested(conn, customers):  # noqa: F811
    radar.draft_for(conn, "P-0001", customers, client=FakeAnthropic(draft()))
    req = product_request.load(conn, "P-0001")
    radar.approve(conn, "P-0001", customers, FakeGitHub(), title=req["title"], body=req["body_md"])
    return conn


def test_closed_as_completed_resolves_once(requested):
    assert radar.issue_changed(requested, "P-0001", "closed", "completed") == "notify"
    assert radar.issue_changed(requested, "P-0001", "closed", "completed") is None  # a repeated webhook
    assert requested.execute("SELECT status FROM problems WHERE id = 'P-0001'").fetchone()[0] == "resolved"


def test_not_planned_dismisses_and_never_notifies(requested):
    assert radar.issue_changed(requested, "P-0001", "closed", "not_planned") is None
    assert requested.execute("SELECT status FROM problems WHERE id = 'P-0001'").fetchone()[0] == "dismissed"


def test_reopened_goes_back_to_requested(requested):
    radar.issue_changed(requested, "P-0001", "closed", "completed")
    radar.issue_changed(requested, "P-0001", "open", "reopened")
    assert requested.execute("SELECT status FROM problems WHERE id = 'P-0001'").fetchone()[0] == "requested"


def test_one_notice_per_customer_and_only_their_own_tickets(requested, customers):  # noqa: F811
    radar.issue_changed(requested, "P-0001", "closed", "completed")
    writer = NoticeWriter()
    created = notify.on_resolved(requested, "P-0001", customers, client=writer, promise_checker=no_promise)
    assert created == ["N-P0001-C019", "N-P0001-C021", "N-P0001-C022"]
    for text in writer.inputs:  # each input names one customer only
        assert sum(customers[c].name in text for c in ("C-019", "C-021", "C-022")) == 1
    t = db.get_ticket(requested, "N-P0001-C021")
    assert (t["kind"], t["mode"], t["state"], t["problem_id"]) == ("proactive", "copilot", "ready", "P-0001")
    assert notify.on_resolved(requested, "P-0001", customers, client=writer, promise_checker=no_promise) == []


def test_guardrails_block_a_notice_that_names_another_customer(requested, customers):  # noqa: F811
    radar.issue_changed(requested, "P-0001", "closed", "completed")
    notify.on_resolved(requested, "P-0001", customers, client=NoticeWriter(bad=[customers["C-019"].name]),
                       promise_checker=no_promise)
    t = db.get_ticket(requested, "N-P0001-C019")
    assert t["state"] == "escalated" and "other_customer_data" in t["reasons"]


def test_a_failing_customer_is_skipped_and_retried_later(requested, customers):  # noqa: F811
    radar.issue_changed(requested, "P-0001", "closed", "completed")
    fail = NoticeWriter(fail=[customers["C-022"].name])
    assert len(notify.on_resolved(requested, "P-0001", customers, client=fail, promise_checker=no_promise)) == 2
    again = notify.on_resolved(requested, "P-0001", customers, client=NoticeWriter(), promise_checker=no_promise)
    assert again == ["N-P0001-C022"]


def test_notices_come_first_in_the_queue_and_stay_out_of_metrics(requested, customers):  # noqa: F811
    radar.issue_changed(requested, "P-0001", "closed", "completed")
    notify.on_resolved(requested, "P-0001", customers, client=NoticeWriter(), promise_checker=no_promise)
    groups = views.queue_groups(db.list_tickets(requested))
    assert groups[0]["label"] == "Avisos proactivos" and len(groups[0]["tickets"]) == 3
    db.record_review(requested, "N-P0001-C019", "approve", "Hola", 20.0, None)
    m = db.metrics(requested)
    assert m["notices_sent"] == 1 and m["reviewed"] == 0


def test_sync_reads_issues_and_finds_problems_by_marker(requested):
    class Issues:
        def list_issues(self, state="all"):
            return [{"number": 7, "state": "closed", "state_reason": "completed", "body": ""},
                    {"number": 99, "state": "closed", "state_reason": "completed", "body": "no marker"}]

    assert radar.sync_issues(requested, Issues()) == ["P-0001"]
    requested.execute("UPDATE problems SET github_number = NULL")
    assert radar.problem_for_issue(requested, 7, "<!-- haddock-problem:P-0001 -->\n## Resumen") == "P-0001"
