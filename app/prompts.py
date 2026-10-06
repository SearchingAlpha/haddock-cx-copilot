"""Prompts from Langfuse by label, with the local file as fallback. Spec: docs/specs/observability.md."""

import os
from dataclasses import dataclass, field
from pathlib import Path

from langfuse import get_client

from app.config import JUDGE_MODEL

PROMPTS_DIR = Path(__file__).resolve().parent.parent / "prompts"

AGENT_SYSTEM = "cx-agent-system"
JUDGE = "eval-key-points-judge"
SYMPTOM = "ticket-symptom"  # radar: docs/specs/radar.md
ALL = [AGENT_SYSTEM, JUDGE, SYMPTOM]  # what scripts/push_prompts.py pushes by default

# Defaults stored in the prompt's Langfuse config: change them in Langfuse, no deploy needed.
DEFAULT_CONFIG = {
    AGENT_SYSTEM: {"effort": "medium"},
    JUDGE: {"model": JUDGE_MODEL},
}


@dataclass
class Prompt:
    name: str
    text: str
    config: dict = field(default_factory=dict)
    client: object | None = None  # Langfuse prompt client; None when the local fallback is used

    def compile(self, **variables: str) -> str:
        if self.client is not None:
            return self.client.compile(**variables)
        text = self.text
        for key, value in variables.items():
            text = text.replace("{{" + key + "}}", value)
        return text


def local_text(name: str) -> str:
    return (PROMPTS_DIR / f"{name}.md").read_text(encoding="utf-8")


def get_prompt(name: str, label: str = "production") -> Prompt:
    fallback = Prompt(name, local_text(name), DEFAULT_CONFIG.get(name, {}))
    if not os.environ.get("LANGFUSE_PUBLIC_KEY"):
        return fallback
    try:
        p = get_client().get_prompt(
            name, label=label, cache_ttl_seconds=60, fallback=fallback.text,
            max_retries=1, fetch_timeout_seconds=5,
        )
    except Exception:
        return fallback
    if p.is_fallback:
        return fallback
    return Prompt(name, p.prompt, {**fallback.config, **(p.config or {})}, p)
