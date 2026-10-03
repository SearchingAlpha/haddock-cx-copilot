"""Langfuse setup in one place. Spec: docs/specs/observability.md."""

import os

from dotenv import load_dotenv
from langfuse import Langfuse, get_client
from pydantic_ai import Agent

TRACE_ENVIRONMENT = "development"
SERVICE_NAME = "haddock-cx-copilot"


def init_tracing() -> Langfuse:
    """Load .env, connect to Langfuse and instrument pydantic-ai. Call once at startup."""
    load_dotenv()  # before get_client(): the client reads LANGFUSE_* at creation
    os.environ.setdefault("LANGFUSE_TRACING_ENVIRONMENT", TRACE_ENVIRONMENT)
    os.environ.setdefault("OTEL_SERVICE_NAME", SERVICE_NAME)

    langfuse = get_client()
    if not langfuse.auth_check():
        raise SystemExit("Langfuse auth failed: check LANGFUSE_* in .env")

    Agent.instrument_all()  # pydantic-ai -> OpenTelemetry -> Langfuse (Jev calls)
    return langfuse
