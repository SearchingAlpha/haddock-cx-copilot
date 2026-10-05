# haddock CX Triage Copilot

Copilot de soporte CX: clasifica el ticket, investiga con tools, escribe un borrador y un agente CX lo revisa. Langfuse traza, versiona los prompts y evalúa.

- Plan y fases: `PLAN.md`.
- Arquitectura: `docs/specs/overview.md`.

## Comandos

```
python -m uv sync                                   # instalar dependencias
python -m uv run pytest                             # tests
python -m uv run python scripts/hello_langfuse.py   # smoke test de Langfuse
python -m uv run python -m scripts.hello_jev        # smoke test de Jev en español, una traza por ticket
python -m uv run python -m app.cli process data/tickets.jsonl --limit 5
python -m uv run uvicorn app.main:app --reload      # UI en http://localhost:8000
python -m uv run python -m scripts.push_prompts     # prompts/ -> Langfuse (versión nueva solo si cambian)
python -m uv run python -m evals.upload_dataset     # data/tickets.jsonl -> dataset cx-tickets
python -m uv run python -m evals.run_experiment --run-name X [--prompt-label staging] [--classify-only --classifier haiku]
python -m uv run python -m evals.rejudge evals/results/X.json --model claude-sonnet-5-5
cd deploy && npx wrangler deploy                    # demo pública en Cloudflare Containers (Docker en marcha)
```

Demo pública: https://haddock-demo.morvegpablo.workers.dev (basic auth, sin pipeline). Spec: `docs/specs/deploy.md`.

## Reglas

1. **Spec antes que código.** Cada módulo tiene `docs/specs/<module>.md` con diagramas Mermaid y texto en ASD-STE100 (skill `explaining-clearly`). Escribe o actualiza el spec antes de cambiar el código. Actualiza el diagrama en el mismo commit que el código.
2. **Test o eval con cada funcionalidad.** Lógica determinista: un test en `tests/`, sin llamadas reales al LLM. Comportamiento del LLM: un item en `data/tickets.jsonl` y un score en `evals/`.
3. **Todo se traza.** Cada función que llama a un LLM o a una tool lleva `@observe`. No uses `print` para depurar el pipeline; mira la traza.
4. **Los prompts viven en Langfuse.** Lee los prompts con `app/prompts.py`. La copia local es solo un fallback.
5. **Sin frameworks de agentes.** El bucle de tool use está escrito a mano en `app/agent.py`, para que se lea en la revisión de código.
6. **Modelos:** Jev (TypeSafe, vía `pydantic-ai`) para las decisiones tipadas: clasificar y las preguntas sí/no de los guardrails. Haiku como fallback de Jev y para LLM-as-judge. Sonnet para el agente. Los ids de los modelos están en un solo sitio. Fija la versión de Jev; no uses `jev-latest` fuera de `scripts/`.
7. **Langfuse v4 (organización nueva):** los endpoints legacy (`api.trace.get`, `/api/public/traces`) devuelven 410. Para leer trazas usa `langfuse.api.observations.get_many(trace_id=..., from_start_time=..., to_start_time=...)`. Comprueba la documentación actual antes de usar otra API de lectura.
8. **Un término = un significado.** Usa los términos de la tabla de `docs/specs/overview.md` en el código, los specs y los commits.

## Estructura

```
app/          FastAPI, pipeline, classify, agent, guardrails, prompts, db
app/tools/    tools del agente (registry)
data/         KB, clientes y tickets sintéticos
evals/        dataset y experimentos de Langfuse
tests/        pytest
docs/specs/   un spec por módulo
scripts/      utilidades
```
