# db

## Purpose
`app/db.py` guarda en SQLite los tickets, los resultados del pipeline y las revisiones de los agentes CX. Las métricas de impacto (`/metrics`) se calculan con estas tablas.

## Diagram

```mermaid
erDiagram
    TICKETS ||--o| RESULTS : "procesado por el pipeline"
    TICKETS ||--o{ REVIEWS : "revisado por un agente CX"

    TICKETS {
        string id PK
        string customer_id
        string channel
        string subject
        string body
        datetime created_at
        string mode "copilot | manual"
        string state "processing | ready | escalated | sent | rejected"
    }
    RESULTS {
        string ticket_id PK
        string status "ready | escalated"
        json reasons
        json classification
        json confidence
        bool review_category
        string draft
        json evidence
        json tool_calls
        string trace_id
        float cost_usd
        int prompt_version
    }
    REVIEWS {
        int id PK
        string ticket_id
        string decision "approve | edit | reject | manual"
        string final_text
        float edit_distance
        float review_seconds
        string category_final
        datetime created_at
    }
```

## Interface

```python
def connect(path: str | None = None) -> sqlite3.Connection   # HADDOCK_DB, por defecto haddock.db
def insert_ticket(db, ticket: TicketIn) -> str                 # devuelve el mode
def save_result(db, result: TicketResult) -> None
def list_tickets(db) -> list[dict]
def get_ticket(db, ticket_id) -> dict | None
def record_review(db, ticket_id, decision, final_text, review_seconds, category_final) -> Review
def metrics(db) -> dict
def mode_for(ticket_id: str) -> str                          # manual para ~20% de los ids
```

## Behavior

1. `insert_ticket()` guarda el ticket con `state = processing` y le asigna un `mode`.
2. `mode_for()` usa un hash estable del id: el mismo ticket siempre tiene el mismo modo. Un 20% de los tickets va a modo `manual`.
3. `save_result()` guarda el resultado y cambia el `state` a `ready` o `escalated`.
4. `record_review()` guarda la decisión y cambia el `state` a `sent` o `rejected`.
5. La distancia de edición es `1 - SequenceMatcher(borrador, texto final).ratio()`. 0 significa sin cambios.
6. `metrics()` calcula las métricas de impacto.

**Métricas de `metrics()`:**

| Métrica | Definición |
|---|---|
| `approved_unedited_rate` | approve / revisiones en modo copilot |
| `avg_seconds_copilot` | segundos medios por ticket en modo copilot |
| `avg_seconds_manual` | segundos medios por ticket en modo manual: la línea base medida |
| `seconds_saved_per_ticket` | `avg_seconds_manual - avg_seconds_copilot` |
| `cost_per_ticket_usd` | coste medio del agente |
| `escalation_rate` | tickets escalados / tickets procesados |
| `category_corrections` | revisiones donde el agente CX cambió la categoría |
| `by_category` | tickets por categoría |

Sin revisiones manuales, `avg_seconds_manual` es `None`. La UI lo dice; no inventa una línea base.

## Errors and edge cases
- Un webhook con un id que ya existe: `insert_ticket()` lanza `ValueError`. El endpoint responde 409.
- Una segunda revisión del mismo ticket: se guarda y la última decide el `state`.

## Done when
- [ ] Tests: los estados cambian según el diagrama; `mode_for()` es estable; las métricas son correctas con datos conocidos; la distancia de edición es 0 sin cambios.
