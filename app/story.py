"""Full-screen stories: the CX agent onboarding and the interview presentation. Spec: docs/specs/story.md.

One sentence per scene, one accent (<em>) per sentence. Every number comes from docs/results.md or the code.
"""

from dataclasses import dataclass

from markupsafe import Markup


@dataclass(frozen=True)
class Scene:
    kicker: str
    title: Markup
    visual: str | None = None
    note: str | None = None


@dataclass(frozen=True)
class Story:
    slug: str
    title: str
    cta: str
    scenes: list[Scene]


INTRO = Story("intro", "Introducción", "Entrar a la cola", [
    Scene("El problema", Markup("Muchos tickets piden <em>los mismos datos</em> una y otra vez.")),
    Scene("Hoy", Markup("Para responder uno, buscas en la cuenta, en el banco <em>y en el centro de ayuda.</em>"),
          "intro_sources"),
    Scene("El copilot", Markup("El copilot investiga cada ticket <em>antes de que lo abras.</em>"), "intro_trail"),
    Scene("Tú decides", Markup("Nada llega al cliente <em>sin tu decisión.</em>"), "intro_decide"),
    Scene("Evidencia", Markup("Cada dato del borrador tiene <em>su evidencia al lado.</em>"), "intro_evidence"),
    Scene("Riesgo", Markup("Lo que tiene riesgo <em>salta a la vista.</em>"), "intro_risk"),
    Scene("Teclado", Markup("Revisas sin ratón: <em>A, E, R y J.</em>"), "intro_keys"),
    Scene("Medimos", Markup("Medimos el tiempo que ahorras. <em>No lo suponemos.</em>"), "intro_measure",
          "Uno de cada cinco tickets se responde sin copilot: es la línea base."),
    Scene("Empezar", Markup("Tu cola <em>te espera.</em>"), "mark"),
])

PRESENTATION = Story("presentacion", "Presentación", "Ver la demo", [
    Scene("Portada", Markup("CX Triage <em>Copilot</em>"), "cover"),
    Scene("Por qué CX", Markup("Soporte es trabajo repetido: <em>mismos datos, mismas respuestas.</em>"), "why_cx",
          "La oferta de haddock: «Support, onboarding, finance operations… are still on the list»."),
    Scene("Tesis", Markup("Cada problema con su herramienta: <em>Jev decide, Sonnet investiga.</em>"), "system12"),
    Scene("Arquitectura", Markup("Un ticket recorre cinco pasos y <em>una persona decide.</em>"), "pipeline"),
    Scene("Seguridad", Markup("Ninguna tool acepta un customer_id: <em>la fuga es imposible por diseño.</em>"),
          "code_ctx"),
    Scene("Guardrails", Markup("Un borrador que promete un reembolso <em>no se envía sin editarlo.</em>"),
          "guardrail", "Regex y una pregunta sí/no a Jev. Enviar se desactiva y el servidor responde 409."),
    Scene("Observabilidad", Markup("Cada ticket es <em>una traza</em> en Langfuse."), "trace_tree"),
    Scene("Evals", Markup("40 tickets etiquetados y <em>12 scores</em> por ticket."), "eval_scores",
          "Dataset cx-tickets en Langfuse. Detalle en docs/results.md."),
    Scene("El juez", Markup("El primer resultado malo era <em>del juez, no del agente.</em>"), "judge",
          "Haiku como juez coincidía con Sonnet solo en el 56 % de los casos de la v2."),
    Scene("Jev o Haiku", Markup("Con confianza de 0,9 o más, Jev acierta <em>el 97 %.</em>"), "jev_table",
          "4 ejecuciones sobre 40 tickets. docs/results.md."),
    Scene("Decisión", Markup("Los datos dijeron: <em>no escalar por confianza.</em>"), "threshold"),
    Scene("Impacto", Markup("El impacto se mide contra <em>una línea base real.</em>"), "impact",
          "Aún no hay revisiones reales: el tiempo ahorrado se medirá en un piloto."),
    Scene("Cómo lo construí", Markup("Spec antes que código y <em>un test o un eval</em> con cada cambio."), "build"),
    Scene("En haddock", Markup("Lo siguiente: <em>Zendesk real, un MCP y Slack.</em>"), "next"),
    Scene("Demo", Markup("Vamos a verlo <em>funcionando.</em>"), "mark"),
])

STORIES = {s.slug: s for s in (INTRO, PRESENTATION)}
