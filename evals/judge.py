"""LLM-as-judge for key points and groundedness. Spec: docs/specs/evals.md. Prompt: eval-key-points-judge."""

import json
from functools import cache

import anthropic
from langfuse import get_client, observe
from pydantic import BaseModel, Field

from app.agent import cost_usd
from app.prompts import JUDGE, get_prompt


class KeyPointVerdict(BaseModel):
    key_point: str
    covered: bool
    reason: str = Field(description="One short sentence.")


class JudgeVerdict(BaseModel):
    key_points: list[KeyPointVerdict]
    unsupported_claims: list[str] = Field(description="Claims about the account with no support in the evidence.")

    @property
    def coverage(self) -> float:
        return sum(k.covered for k in self.key_points) / len(self.key_points) if self.key_points else 1.0

    @property
    def grounded(self) -> float:
        return 0.0 if self.unsupported_claims else 1.0


@cache
def _client() -> anthropic.Anthropic:
    return anthropic.Anthropic()


def readable_evidence(tool_outputs: list[dict]) -> str:
    """Tool outputs are JSON strings; parse them so the judge reads objects, not escaped text."""
    def parse(text: str):
        try:
            return json.loads(text)
        except (TypeError, ValueError):
            return text

    return json.dumps(
        [{"tool": t["tool"], "input": t["input"], "output": parse(t["output"])} for t in tool_outputs],
        ensure_ascii=False, indent=1,
    )


@observe(name="judge", as_type="generation", capture_input=False, capture_output=False)
def judge(ticket: str, key_points: list[str], draft: str, evidence: list[dict], *, model: str | None = None) -> JudgeVerdict:
    prompt = get_prompt(JUDGE)
    model = model or prompt.config["model"]
    text = prompt.compile(
        ticket=ticket,
        key_points="\n".join(f"- {k}" for k in key_points),
        draft=draft,
        evidence=readable_evidence(evidence),
    )
    response = _client().messages.parse(
        model=model, max_tokens=4000, messages=[{"role": "user", "content": text}], output_format=JudgeVerdict,
    )
    verdict = response.parsed_output
    get_client().update_current_generation(
        model=model, input=text, output=verdict.model_dump(), prompt=prompt.client,
        usage_details={"input": response.usage.input_tokens, "output": response.usage.output_tokens},
        cost_details={"total": cost_usd(model, response.usage)},
    )
    return verdict
