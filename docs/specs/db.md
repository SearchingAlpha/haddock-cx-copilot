# db

## Purpose
`app/db.py` guarda en SQLite los tickets, los resultados del pipeline y las revisiones de los agentes CX. Las métricas de impacto (`/metrics`) se calculan con estas tablas.

## Diagram

```mermaid
erDiagram
    TICKETS ||--o| RESULTS : "procesado por el pipeline"
    TICKETS ||--o{ REVIEWS : "revisado por un agente CX"
    TICKETS ||--o| SIGNALS : "leído por el radar"
    PROBLEMS ||--o{ SIGNALS : "agrupa"
    PROBLEMS ||--o{ PROBLEM_EVENTS : "historial"

    TICKETS {
        string id PK
        string customer_id
        string channel
        string subject
        string body
        datetime created_at
        string mode "copilot | manual"
        string state "processing | ready | escalated | sent | rejected | history"
        string kind "inbound | proactive"
        string source "live | history"
        string problem_id
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
    SIGNALS {
        string ticket_id PK
        string component "invoices.ocr, bank.sync..."
        string kind "bug | feature | how_to | user_error"
        string entity "banco, TPV o proveedor"
        string symptom
        string priority
        string problem_id
        float match_confidence
        json matched "respuestas del matcher"
    }
    PROBLEMS {
        string id PK "P-0001"
        string component
        string kind
        string entity
        string title
        string status "open | candidate | requested | resolved | dismissed | merged"
        datetime detected_at
        int detected_at_n
        string merged_into
        int github_number
    }
    PROBLEM_EVENTS {
        int id PK
        string problem_id
        string kind "opened | ticket_added | threshold | merged"
        json payload
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
7. `connect()` añade las columnas nuevas (`LATE_COLUMNS`) a una base de datos antigua. `insert_ticket()` nombra sus columnas, así funciona con las dos.
8. `insert_ticket(source="history")` guarda un ticket del pasado para el radar, con `state = history`. `list_tickets()` lo excluye: no aparece en la cola ni en `/metrics`. `get_ticket()` sí lo devuelve.

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
