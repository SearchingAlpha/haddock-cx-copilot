"""Code review tour at /codigo: each stop shows real code or a real spec diagram. Spec: docs/specs/tour.md.

Excerpts are read from the repo on every request, so the tour never shows stale code.
"""

import ast
import re
from dataclasses import dataclass, field
from pathlib import Path

from markupsafe import Markup

ROOT = Path(__file__).resolve().parent.parent
MERMAID = re.compile(r"```mermaid\n(.*?)```", re.DOTALL)
LANGUAGES = {".py": "python", ".md": "markdown"}


@dataclass(frozen=True)
class Excerpt:
    path: str
    symbol: str | None = None
    diagram: int | None = None
    section: str | None = None


@dataclass(frozen=True)
class Shown:
    kind: str  # code | mermaid | text
    language: str
    text: str
    location: str


@dataclass(frozen=True)
class Stop:
    kicker: str
    title: Markup
    points: list[str]
    excerpts: list[Excerpt] = field(default_factory=list)


def _symbol(path: str, source: str, name: str) -> Shown:
    for node in ast.parse(source).body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)) and node.name == name:
            start = min([d.lineno for d in node.decorator_list] + [node.lineno])
            lines = source.splitlines()[start - 1:node.end_lineno]
            return Shown("code", "python", "\n".join(lines), f"{path}:{start}")
    raise LookupError(f"{name} not found in {path}")


def _section(path: str, source: str, heading: str) -> Shown:
    lines = source.splitlines()
    if heading not in lines:
        raise LookupError(f"{heading!r} not found in {path}")
    start = lines.index(heading)
    level = len(heading) - len(heading.lstrip("#"))
    end = next((i for i in range(start + 1, len(lines))
                if re.match(rf"#{{1,{level}}} ", lines[i])), len(lines))
    return Shown("text", "markdown", "\n".join(lines[start:end]).strip(), f"{path}:{start + 1}")


def resolve(excerpt: Excerpt) -> Shown:
    source = (ROOT / excerpt.path).read_text(encoding="utf-8")
    if excerpt.symbol:
        return _symbol(excerpt.path, source, excerpt.symbol)
    if excerpt.diagram:
        blocks = MERMAID.findall(source)
        if not 0 < excerpt.diagram <= len(blocks):
            raise LookupError(f"diagram {excerpt.diagram} not found in {excerpt.path}")
        return Shown("mermaid", "mermaid", blocks[excerpt.diagram - 1].strip(), excerpt.path)
    if excerpt.section:
        return _section(excerpt.path, source, excerpt.section)
    language = LANGUAGES.get(Path(excerpt.path).suffix, "plaintext")
    return Shown("code" if language == "python" else "text", language, source.strip(), excerpt.path)


# In the order of PLAN.md, phase 5: map, how it was built, then the pipeline from entry to feedback.
TOUR = [
    Stop("Mapa", Markup("Un ticket recorre cinco pasos y <em>una persona decide.</em>"), [
        "Entra por un webhook, Jev lo clasifica, Sonnet investiga con tools y los guardrails revisan el borrador.",
        "Nada llega al cliente sin la decisión de un agente CX.",
        "Langfuse traza cada paso.",
    ], [Excerpt("docs/specs/overview.md", diagram=1)]),
    Stop("Cómo lo construí", Markup("Claude Code trabaja con <em>las reglas del repo.</em>"), [
        "Cada sesión lee CLAUDE.md: spec antes que código y un test o un eval con cada cambio.",
        "Las skills dan el método: explaining-clearly para los specs, tdd, eval e impeccable para la UI.",
    ], [Excerpt("CLAUDE.md", section="## Reglas")]),
    Stop("Specs", Markup("Cada módulo tiene <em>un spec con diagrama</em> antes que código."), [
        "Los specs usan Mermaid y frases cortas (ASD-STE100).",
        "El diagrama cambia en el mismo commit que el código. Este recorrido los lee del repo.",
    ], [Excerpt("docs/specs/agent.md", diagram=1)]),
    Stop("Clasificar", Markup("Jev no lleva prompt: <em>cada campo es una pregunta.</em>"), [
        "Jev devuelve un objeto tipado y una confianza calibrada por campo.",
        "Cuesta unos $0.00003 por ticket; Haiku, unos $0.001.",
        "La confianza baja de la categoría solo pide revisarla. Nunca escala.",
    ], [Excerpt("app/classify.py", symbol="TicketClassification")]),
    Stop("El agente", Markup("El bucle del agente está <em>escrito a mano</em>, sin framework."), [
        "Seis iteraciones como máximo. Todos los resultados de las tools vuelven en un solo mensaje.",
        "Termina con submit_draft: respuesta, evidencia citada y confianza, con un schema.",
    ], [Excerpt("app/agent.py", symbol="run_agent")]),
    Stop("Tools", Markup("Ninguna tool acepta un customer_id: <em>la fuga es imposible por diseño.</em>"), [
        "El pipeline crea el contexto con el cliente del ticket. El modelo no puede pedir otro.",
        "Pydantic valida cada input. Un error vuelve al modelo como is_error, para que se corrija.",
    ], [Excerpt("app/tools/__init__.py", symbol="ToolContext"),
        Excerpt("app/tools/__init__.py", symbol="get_invoices"),
        Excerpt("app/tools/__init__.py", symbol="execute")]),
    Stop("Prompts", Markup("Los prompts viven en <em>Langfuse</em>, con un label."), [
        "production y staging son labels: cambiar de versión no necesita deploy.",
        "Si Langfuse no responde, la app usa la copia local.",
    ], [Excerpt("app/prompts.py", symbol="get_prompt"), Excerpt("prompts/cx-agent-system.md")]),
    Stop("Guardrails", Markup("Primero un regex, <em>después Jev.</em>"), [
        "Una promesa de reembolso o de plazo bloquea el envío: el servidor responde 409.",
        "Los datos de otro cliente también bloquean. Todos los motivos se ven a la vez.",
    ], [Excerpt("docs/specs/guardrails.md", diagram=1), Excerpt("app/guardrails.py", symbol="_promises")]),
    Stop("Trazas", Markup("Cada ticket es <em>una traza</em>, cada turno una generation."), [
        "@observe en el pipeline, en cada tool y en cada turno del agente.",
        "Cada generation lleva el coste y la versión del prompt.",
    ], [Excerpt("docs/specs/observability.md", diagram=1), Excerpt("app/agent.py", symbol="_call_model")]),
    Stop("Evals", Markup("40 tickets etiquetados y <em>12 scores</em> por ticket."), [
        "Scores deterministas y un juez LLM para la cobertura y la groundedness.",
        "El primer resultado malo (0.63) era del juez, no del agente.",
        "La v2 del prompt mejoró el formato y empeoró el escalado: production sigue en la v1.",
    ], [Excerpt("evals/run_experiment.py", symbol="deterministic"),
        Excerpt("evals/run_experiment.py", symbol="judged")]),
    Stop("Feedback", Markup("La decisión del agente CX vuelve a Langfuse <em>como score.</em>"), [
        "human_decision, edit_distance y review_seconds en la traza del ticket.",
        "Uno de cada cinco tickets va sin copilot: es la línea base de tiempo.",
    ], [Excerpt("app/main.py", symbol="send_scores"), Excerpt("app/db.py", symbol="mode_for")]),
    Stop("Deploy", Markup("La demo pública <em>no puede gastar tokens.</em>"), [
        "Cloudflare Containers, una sola instancia, la base de datos dentro de la imagen.",
        "Con HADDOCK_PUBLIC=1 no hay pipeline: el webhook responde 403.",
    ], [Excerpt("docs/specs/deploy.md", diagram=1), Excerpt("app/main.py", symbol="accept")]),
]
