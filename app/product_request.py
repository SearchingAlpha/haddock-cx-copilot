"""Product request: the GitHub issue for one problem. Sonnet writes, code counts and checks. Spec: docs/specs/product-request.md."""

import json
import re
from dataclasses import dataclass, field
from datetime import datetime
from functools import cache

import anthropic
from langfuse import get_client, observe
from pydantic import BaseModel, Field

from app.agent import cost_usd
from app.config import REQUEST_MAX_TICKETS, REQUEST_MODEL
from app.domain import Customer
from app.prompts import PRODUCT_REQUEST, get_prompt

EMAIL = re.compile(r"[\w.+-]+@[\w-]+(\.[\w-]+)+")
PHONE = re.compile(r"(?<![\w-])(?:\+34[ .]?)?[6789]\d{2}[ .]?\d{3}[ .]?\d{3}(?![\w-])")  # Spanish phones, not dates
MARKER = "<!-- haddock-problem:{} -->"


class Evidence(BaseModel):
    ticket_id: str
    quote: str = Field(description="Exact copy of 5 to 25 consecutive words from that ticket's body.")


class RequestDraft(BaseModel):
    title: str = Field(description="At most 90 characters, in Spanish.")
    summary: str
    repro_steps: list[str]
    suspected_component: str
    acceptance_criteria: list[str]
    evidence: list[Evidence]


@dataclass
class ProductRequest:
    draft: RequestDraft
    body_md: str
    dropped: list[dict] = field(default_factory=list)  # quotes that were not literal
    cost_usd: float = 0.0
    trace_id: str = ""


@cache
def _client() -> anthropic.Anthropic:
    return anthropic.Anthropic()


def scrub(text: str, customers: dict[str, Customer]) -> str:
    """No customer, restaurant or contact names, emails or phones: not for Sonnet, not for GitHub."""
    text = EMAIL.sub("[email]", text)
    text = PHONE.sub("[teléfono]", text)
    names = []
    for c in customers.values():
        names += [(c.name, "[cliente]"), (c.contact_name, "[contacto]")]
        first = c.contact_name.split()[0]
        if len(first) > 3:
            names.append((first, "[contacto]"))
    for name, mask in sorted(names, key=lambda pair: -len(pair[0])):  # "Elena Ruiz" before "Elena"
        text = re.sub(rf"(?<!\w){re.escape(name)}(?!\w)", mask, text)
    return text


def _norm(text: str) -> str:
    return " ".join(text.lower().split())


def check_quotes(evidence: list[Evidence], texts: dict[str, str]) -> tuple[list[Evidence], list[Evidence]]:
    """A quote counts only if it is literal text of the ticket it cites (case and spaces aside)."""
    kept, dropped = [], []
    for e in evidence:
        source = texts.get(e.ticket_id)
        (kept if source and e.quote.strip() and _norm(e.quote) in _norm(source) else dropped).append(e)
    return kept, dropped


def sample(signals: list[dict], n: int = REQUEST_MAX_TICKETS) -> list[dict]:
    """The first 3 tickets (how it started) and the last ones (how it is now)."""
    if len(signals) <= n:
        return signals
    return signals[:3] + signals[-(n - 3):]


def customer_line(c: Customer | None, cid: str) -> str:
    if c is None:
        return cid
    return f"{cid} · {c.plan} · {c.locations} {'local' if c.locations == 1 else 'locales'}"


def facts(problem: dict, customers: dict[str, Customer]) -> str:
    imp = problem["impact"]
    return "\n".join([
        f"Problema {problem['id']} · componente {problem['component']} · tipo {problem['kind']}"
        + (f" · entidad {problem['entity']}" if problem.get("entity") else ""),
        f"Tickets: {imp.tickets} · clientes distintos: {len(imp.customers)} · MRR de clientes afectados: "
        f"{imp.mrr_eur:.0f} € · severidad {imp.severity:.0%} · tendencia {imp.trend:.1f}",
        f"Primer ticket: {problem['first_ticket_at'][:10]} · último: {problem['last_ticket_at'][:10]}",
        "Clientes: " + ", ".join(customer_line(customers.get(c), c) for c in imp.customers),
    ])


def request_input(problem: dict, customers: dict[str, Customer]) -> tuple[str, dict[str, str]]:
    texts = {s["ticket_id"]: scrub(s.get("body") or "", customers) for s in problem["signals"]}
    blocks = []
    for s in sample(problem["signals"]):
        c = customers.get(s["customer_id"])
        blocks.append(f'<ticket id="{s["ticket_id"]}" date="{s["created_at"][:10]}" '
                      f'customer="{customer_line(c, s["customer_id"])}">\n'
                      f'{scrub(s.get("subject") or "", customers)}\n\n{texts[s["ticket_id"]]}\n</ticket>')
    return f"<facts>\n{facts(problem, customers)}\n</facts>\n\n" + "\n\n".join(blocks), texts


def _tickets(n: int) -> str:
    return f"{n} ticket" if n == 1 else f"{n} tickets"


def _without_prefix(text: str, component: str) -> str:
    """The model often repeats the component: "invoices.ocr: la extracción..." -> "la extracción..."."""
    stripped = re.sub(rf"^`?{re.escape(component)}`?\s*[:\-—]\s*", "", text.strip())
    return stripped[:1].upper() + stripped[1:] if stripped else text


def render_issue_md(problem: dict, draft: RequestDraft, customers: dict[str, Customer], *,
                    evidence: list[Evidence] | None = None) -> str:
    """Numbers come from the impact, never from the model. Customers appear by id and plan only."""
    imp = problem["impact"]
    evidence = draft.evidence if evidence is None else evidence
    lines = [
        MARKER.format(problem["id"]),
        "## Resumen", draft.summary, "",
        "## Impacto",
        "| Medida | Valor |", "|---|---|",
        f"| Tickets | {imp.tickets} |",
        f"| Clientes afectados | {len(imp.customers)} |",
        f"| MRR de clientes afectados | {imp.mrr_eur:,.0f} €/mes |".replace(",", "."),
        f"| Tickets urgentes o altos | {imp.severity:.0%} |",
        f"| Tickets por semana (6 semanas) | {' · '.join(str(w) for w in imp.weekly)} |",
        f"| Primer ticket | {problem['first_ticket_at'][:10]} |",
        "",
        "## Pasos para reproducir", *(f"{i}. {s}" for i, s in enumerate(draft.repro_steps, 1)), "",
        "## Componente sospechoso", f"`{problem['component']}`: {_without_prefix(draft.suspected_component, problem['component'])}", "",
        "## Criterios de aceptación", *(f"- [ ] {a}" for a in draft.acceptance_criteria), "",
        "## Lo que dicen los clientes",
        *(f"> {e.quote}\n>\n> — ticket `{e.ticket_id}`\n" for e in evidence),
        "## Clientes afectados",
        *(f"- {customer_line(customers.get(c), c)} · {_tickets(problem['by_customer'].get(c, 0))}"
          for c in sorted(imp.customers, key=lambda c: (-problem['by_customer'].get(c, 0), c))),
        "",
        "---",
        f"Redactado por el radar de producto de haddock-cx-copilot a partir de {imp.tickets} tickets. "
        "Un agente CX lo revisó antes de crear esta issue.",
    ]
    return "\n".join(lines)


def _scrubbed(d: RequestDraft, customers: dict[str, Customer]) -> RequestDraft:
    def s(text: str) -> str:
        return scrub(text, customers)
    return RequestDraft(title=s(d.title)[:120], summary=s(d.summary), repro_steps=[s(x) for x in d.repro_steps],
                        suspected_component=s(d.suspected_component),
                        acceptance_criteria=[s(x) for x in d.acceptance_criteria], evidence=d.evidence)


@observe(name="quote-check", as_type="guardrail")
def _quote_check(evidence: list[Evidence], texts: dict[str, str]) -> tuple[list[Evidence], list[Evidence]]:
    kept, dropped = check_quotes(evidence, texts)
    get_client().update_current_span(output={"kept": len(kept), "dropped": [e.model_dump() for e in dropped]},
                                     level="WARNING" if dropped else "DEFAULT")
    return kept, dropped


@observe(name="request-draft", as_type="generation", capture_input=False, capture_output=False)
def _write(text: str, client) -> tuple[RequestDraft, float]:
    prompt = get_prompt(PRODUCT_REQUEST)
    response = client.messages.parse(
        model=REQUEST_MODEL, max_tokens=4000, system=prompt.text,
        messages=[{"role": "user", "content": text}], output_format=RequestDraft,
    )
    if response.stop_reason == "refusal" or response.parsed_output is None:
        raise RuntimeError(f"no request draft: stop_reason={response.stop_reason}")
    cost = cost_usd(REQUEST_MODEL, response.usage)
    get_client().update_current_generation(
        model=REQUEST_MODEL, input=text, output=response.parsed_output.model_dump(), prompt=prompt.client,
        usage_details={"input": response.usage.input_tokens, "output": response.usage.output_tokens},
        cost_details={"total": cost},
    )
    return response.parsed_output, cost


@observe(name="product-request", capture_input=False)
def draft_request(problem: dict, customers: dict[str, Customer], *, client=None) -> ProductRequest:
    """problem: problems.get_problem() output (signals with ticket text, impact, by_customer)."""
    text, texts = request_input(problem, customers)
    draft, cost = _write(text, client or _client())
    kept, dropped = _quote_check(draft.evidence, texts)
    draft = _scrubbed(draft, customers)  # the model never saw a name, but never trust that
    body = render_issue_md(problem, draft, customers, evidence=kept)
    trace_id = get_client().get_current_trace_id() or ""
    get_client().update_current_span(output={"title": draft.title, "kept": len(kept), "dropped": len(dropped)})
    return ProductRequest(draft, body, [e.model_dump() for e in dropped], cost, trace_id)


# --- storage ------------------------------------------------------------------------------------

def save(conn, problem_id: str, req: ProductRequest) -> None:
    with conn:
        conn.execute(
            "INSERT OR REPLACE INTO product_requests (problem_id, title, body_md, payload, dropped, status, trace_id, "
            "cost_usd, created_at) VALUES (?, ?, ?, ?, ?, 'draft', ?, ?, ?)",
            (problem_id, req.draft.title, req.body_md, req.draft.model_dump_json(), json.dumps(req.dropped),
             req.trace_id, req.cost_usd, datetime.now().isoformat(timespec="seconds")))


def load(conn, problem_id: str) -> dict | None:
    row = conn.execute("SELECT * FROM product_requests WHERE problem_id = ?", (problem_id,)).fetchone()
    if row is None:
        return None
    d = dict(row)
    d["dropped"] = json.loads(d["dropped"] or "[]")
    d["payload"] = json.loads(d["payload"] or "{}")
    return d
