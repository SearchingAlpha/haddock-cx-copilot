"""Trace contract from docs/specs/observability.md. No network, no real LLM."""

import json

import pytest
from langfuse import Langfuse
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
from pydantic_ai import Agent
from pydantic_ai.models.instrumented import InstrumentationSettings
from pydantic_ai.models.test import TestModel

from app import observability
from scripts.hello_jev import Classification, build_classifier, classify_ticket


class FakeClient:
    def __init__(self, ok: bool):
        self.ok = ok

    def auth_check(self) -> bool:
        return self.ok


@pytest.fixture
def no_side_effects(monkeypatch):
    """Record the call order of init_tracing() without touching .env, the network or pydantic-ai."""
    calls = []
    monkeypatch.delenv("LANGFUSE_TRACING_ENVIRONMENT", raising=False)
    monkeypatch.delenv("OTEL_SERVICE_NAME", raising=False)
    monkeypatch.setattr(observability, "load_dotenv", lambda: calls.append("load_dotenv"))
    monkeypatch.setattr(observability.Agent, "instrument_all", lambda: calls.append("instrument_all"))
    return calls


def test_init_tracing_loads_env_before_client_and_sets_defaults(no_side_effects, monkeypatch):
    client = FakeClient(ok=True)
    monkeypatch.setattr(observability, "get_client", lambda: no_side_effects.append("get_client") or client)

    assert observability.init_tracing() is client
    assert no_side_effects == ["load_dotenv", "get_client", "instrument_all"]
    assert observability.os.environ["LANGFUSE_TRACING_ENVIRONMENT"] == "development"
    assert observability.os.environ["OTEL_SERVICE_NAME"] == "haddock-cx-copilot"


def test_init_tracing_keeps_an_environment_that_is_already_set(no_side_effects, monkeypatch):
    monkeypatch.setenv("LANGFUSE_TRACING_ENVIRONMENT", "production")
    monkeypatch.setattr(observability, "get_client", lambda: FakeClient(ok=True))

    observability.init_tracing()
    assert observability.os.environ["LANGFUSE_TRACING_ENVIRONMENT"] == "production"


def test_init_tracing_stops_on_bad_credentials(no_side_effects, monkeypatch):
    monkeypatch.setattr(observability, "get_client", lambda: FakeClient(ok=False))

    with pytest.raises(SystemExit, match="LANGFUSE_"):
        observability.init_tracing()
    assert "instrument_all" not in no_side_effects


@pytest.fixture
def exported_spans(monkeypatch):
    """A Langfuse client that exports to memory, and pydantic-ai spans on the same provider."""
    monkeypatch.delenv("LANGFUSE_PUBLIC_KEY", raising=False)
    monkeypatch.delenv("LANGFUSE_SECRET_KEY", raising=False)
    exporter = InMemorySpanExporter()
    provider = TracerProvider()
    langfuse = Langfuse(
        public_key="pk-lf-test", secret_key="sk-lf-test", base_url="http://localhost:9",
        tracer_provider=provider, span_exporter=exporter,
    )
    Agent.instrument_all(InstrumentationSettings(tracer_provider=provider))

    def finished():
        langfuse.flush()
        return {span.name: span for span in exporter.get_finished_spans()}

    yield finished
    Agent.instrument_all(False)
    langfuse.shutdown()


def test_one_ticket_makes_one_readable_trace(exported_spans):
    classify_ticket(build_classifier(TestModel()), "T-9", "texto del ticket")
    spans = exported_spans()

    root = spans["classify-ticket"]
    agent = spans["invoke_agent ticket-classifier"]
    assert root.parent is None
    assert agent.context.trace_id == root.context.trace_id

    assert root.attributes["langfuse.observation.input"] == "texto del ticket"
    output = json.loads(root.attributes["langfuse.observation.output"])
    assert set(output) == {"classification", "confidence"}
    assert output["classification"]["category"] in {c.value for c in Classification.model_fields["category"].annotation}

    for span in (root, agent):
        assert span.attributes["session.id"] == "T-9"
        assert span.attributes["langfuse.trace.name"] == "classify-ticket"
        assert span.attributes["langfuse.trace.metadata.ticket_id"] == "T-9"
