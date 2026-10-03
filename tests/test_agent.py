"""Agent loop contract: docs/specs/agent.md. A scripted fake client, no network."""

from types import SimpleNamespace as NS

import pytest

from app import agent
from app.data import load_customers, load_kb, load_tickets
from app.tools import KBIndex, ToolContext


def usage():
    return NS(input_tokens=100, output_tokens=50, cache_read_input_tokens=0, cache_creation_input_tokens=0)


def tool_use(id, name, input):
    return NS(type="tool_use", id=id, name=name, input=input)


def response(*blocks, stop_reason="tool_use"):
    return NS(content=list(blocks), stop_reason=stop_reason, usage=usage(), model="claude-sonnet-5-5")


class FakeClient:
    """Returns scripted responses and records every request."""

    def __init__(self, responses):
        self.responses = list(responses)
        self.requests = []
        self.beta = NS(messages=NS(create=self.create))

    def create(self, **kwargs):
        self.requests.append({**kwargs, "messages": list(kwargs["messages"])})  # snapshot: the loop mutates it
        return self.responses.pop(0)


@pytest.fixture(scope="module")
def setup():
    customers = load_customers()
    ticket = next(t for t in load_tickets() if t.customer_id == "C-001")
    ctx = ToolContext(customer=customers["C-001"], kb=KBIndex(load_kb()))
    return ticket, ctx


def submit(id="s1"):
    return tool_use(id, "submit_draft", {"reply": "Hola", "evidence": ["F-0101"], "confidence": "high"})


def test_tool_call_is_executed_and_result_has_the_same_id(setup):
    ticket, ctx = setup
    client = FakeClient([response(tool_use("t1", "get_invoices", {})), response(submit())])

    result = agent.run_agent(ticket, ctx, client=client)

    second_request_messages = client.requests[1]["messages"]
    [tool_result] = second_request_messages[-1]["content"]
    assert tool_result["tool_use_id"] == "t1"
    assert "F-0101" in tool_result["content"]
    assert result.tool_calls == ["get_invoices"]


def test_submit_draft_ends_the_loop(setup):
    ticket, ctx = setup
    client = FakeClient([response(submit())])

    result = agent.run_agent(ticket, ctx, client=client)

    assert result.stop == "submitted"
    assert result.draft == "Hola"
    assert result.evidence == ["F-0101"]
    assert len(client.requests) == 1


def test_loop_stops_at_max_iterations(setup):
    ticket, ctx = setup
    client = FakeClient([response(tool_use(f"t{i}", "get_customer", {})) for i in range(10)])

    result = agent.run_agent(ticket, ctx, client=client)

    assert result.stop == "max_iterations"
    assert result.draft is None
    assert len(client.requests) == agent.MAX_AGENT_ITERATIONS


def test_escalation_is_recorded_and_draft_still_submitted(setup):
    ticket, ctx = setup
    escalate = tool_use("e1", "escalate_to_human", {"team": "finance", "reason": "reembolso"})
    client = FakeClient([response(escalate), response(submit())])

    result = agent.run_agent(ticket, ctx, client=client)

    assert result.escalation.team == "finance"
    assert result.draft == "Hola"


def test_refusal_stops_without_draft(setup):
    ticket, ctx = setup
    client = FakeClient([response(stop_reason="refusal")])

    result = agent.run_agent(ticket, ctx, client=client)

    assert result.stop == "refusal"
    assert result.draft is None


def test_labels_are_never_sent_to_the_model(setup):
    ticket, ctx = setup
    client = FakeClient([response(submit())])

    agent.run_agent(ticket, ctx, client=client)

    first_message = str(client.requests[0]["messages"][0]["content"])
    assert "key_points" not in first_message
    assert "expected_tools" not in first_message
