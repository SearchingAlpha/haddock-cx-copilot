"""Manual tool-use loop with Sonnet: investigate a ticket and draft a reply. Spec: docs/specs/agent.md."""

from dataclasses import dataclass, field

import anthropic
from langfuse import get_client, observe

from app.config import AGENT_MAX_TOKENS, AGENT_MODEL, MAX_AGENT_ITERATIONS, PRICES_PER_MTOK
from app.domain import TicketIn
from app.prompts import AGENT_SYSTEM, Prompt, get_prompt
from app.tools import Escalation, ToolContext, execute, tool_definitions

# The system prompt lives in Langfuse (cx-agent-system); prompts/cx-agent-system.md is the fallback.

SUBMIT_DRAFT_TOOL = {
    "name": "submit_draft",
    "description": "Submit the final reply draft for human review. Call it exactly once, at the end.",
    "input_schema": {
        "type": "object",
        "properties": {
            "reply": {"type": "string"},
            "evidence": {"type": "array", "items": {"type": "string"}},
            "confidence": {"type": "string", "enum": ["low", "medium", "high"]},
        },
        "required": ["reply", "evidence", "confidence"],
        "additionalProperties": False,
    },
    "strict": True,
}

REMINDER = "Finish by calling submit_draft with the reply, the evidence and your confidence."


@dataclass
class AgentResult:
    draft: str | None
    evidence: list[str]
    confidence: str | None
    escalation: Escalation | None
    tool_calls: list[str]
    iterations: int
    stop: str  # submitted | max_iterations | refusal
    cost_usd: float = 0.0
    tool_outputs: list[dict] = field(default_factory=list)  # what the agent read; the judge checks claims against it
    prompt_version: int | None = None


def ticket_message(ticket: TicketIn, customer_name: str) -> str:
    """The ticket as the model sees it. Labels (ground truth) are never included."""
    return (
        f"Customer: {customer_name}\n"
        f"Ticket {ticket.id} via {ticket.channel}, {ticket.created_at:%Y-%m-%d %H:%M}\n"
        f"Subject: {ticket.subject}\n\n"
        f"<ticket>\n{ticket.body}\n</ticket>"
    )


def cost_usd(model: str, usage) -> float:
    p = PRICES_PER_MTOK.get(model)
    if p is None:
        return 0.0
    tokens = {
        "input": usage.input_tokens,
        "output": usage.output_tokens,
        "cache_read": usage.cache_read_input_tokens or 0,
        "cache_write": usage.cache_creation_input_tokens or 0,
    }
    return sum(tokens[k] * p[k] for k in tokens) / 1_000_000


@observe(name="agent-turn", as_type="generation", capture_input=False, capture_output=False)
def _call_model(client, messages: list, prompt: Prompt) -> tuple[object, float]:
    effort = prompt.config.get("effort", "medium")
    response = client.beta.messages.create(
        model=AGENT_MODEL,
        max_tokens=AGENT_MAX_TOKENS,
        system=prompt.text,
        tools=[*tool_definitions(), SUBMIT_DRAFT_TOOL],
        messages=messages,
        thinking={"type": "adaptive"},
        output_config={"effort": effort},
        cache_control={"type": "ephemeral"},  # system + tools are identical for every ticket
        betas=["server-side-fallback-2026-07-01"],
        fallbacks="default",
    )
    cost = cost_usd(AGENT_MODEL, response.usage)
    u = response.usage
    get_client().update_current_generation(
        model=getattr(response, "model", AGENT_MODEL),
        model_parameters={"effort": effort, "max_tokens": AGENT_MAX_TOKENS},
        input=messages[-1]["content"],
        output=[b for b in response.content if getattr(b, "type", None) in ("tool_use", "text")],
        usage_details={
            "input": u.input_tokens,
            "output": u.output_tokens,
            "cache_read_input_tokens": u.cache_read_input_tokens or 0,
            "cache_creation_input_tokens": u.cache_creation_input_tokens or 0,
        },
        cost_details={"total": cost},
        metadata={"stop_reason": response.stop_reason},
        prompt=prompt.client,  # links this generation to the prompt version in Langfuse
    )
    return response, cost


@observe(name="agent", as_type="agent")
def run_agent(ticket: TicketIn, ctx: ToolContext, *, client=None, prompt_label: str = "production") -> AgentResult:
    client = client or anthropic.Anthropic()
    prompt = get_prompt(AGENT_SYSTEM, label=prompt_label)
    version = getattr(prompt.client, "version", None)
    messages: list = [{"role": "user", "content": ticket_message(ticket, ctx.customer.name)}]
    tool_calls: list[str] = []
    tool_outputs: list[dict] = []
    escalation: Escalation | None = None
    total_cost = 0.0

    def result(stop: str, iterations: int, submit=None) -> AgentResult:
        return AgentResult(
            draft=submit.input["reply"] if submit else None,
            evidence=list(submit.input["evidence"]) if submit else [],
            confidence=submit.input["confidence"] if submit else None,
            escalation=escalation, tool_calls=tool_calls, iterations=iterations, stop=stop,
            cost_usd=total_cost, tool_outputs=tool_outputs, prompt_version=version,
        )

    for iteration in range(1, MAX_AGENT_ITERATIONS + 1):
        response, cost = _call_model(client, messages, prompt)
        total_cost += cost

        if response.stop_reason == "refusal":
            return result("refusal", iteration)

        uses = [b for b in response.content if getattr(b, "type", None) == "tool_use"]
        messages.append({"role": "assistant", "content": response.content})

        submit = next((b for b in uses if b.name == "submit_draft"), None)
        if submit:
            return result("submitted", iteration, submit)

        if not uses:  # plain text, or max_tokens: remind once per turn and continue
            messages.append({"role": "user", "content": REMINDER})
            continue

        results = []
        for use in uses:  # all tool results go back in ONE user message
            out = execute(use.name, use.input, ctx)
            tool_calls.append(use.name)
            tool_outputs.append({"tool": use.name, "input": use.input, "output": out.content})
            escalation = out.escalation or escalation
            results.append({
                "type": "tool_result",
                "tool_use_id": use.id,
                "content": out.content,
                "is_error": out.is_error,
            })
        messages.append({"role": "user", "content": results})

    return result("max_iterations", MAX_AGENT_ITERATIONS)
