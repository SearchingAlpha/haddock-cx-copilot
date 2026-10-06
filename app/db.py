"""SQLite storage for tickets, pipeline results and human reviews. Spec: docs/specs/db.md."""

import hashlib
import json
import os
import sqlite3
from collections import Counter
from datetime import datetime
from difflib import SequenceMatcher

from app.domain import TicketIn

MANUAL_SHARE = 5  # 1 ticket in 5 (~20%) is handled without the copilot: the measured baseline

SCHEMA = """
CREATE TABLE IF NOT EXISTS tickets (
    id TEXT PRIMARY KEY, customer_id TEXT, channel TEXT, subject TEXT, body TEXT,
    created_at TEXT, mode TEXT, state TEXT
);
CREATE TABLE IF NOT EXISTS results (
    ticket_id TEXT PRIMARY KEY REFERENCES tickets(id), status TEXT, reasons TEXT, classification TEXT,
    confidence TEXT, review_category INTEGER, draft TEXT, evidence TEXT, tool_calls TEXT, trace_id TEXT,
    cost_usd REAL, prompt_version INTEGER, tool_outputs TEXT, escalation TEXT
);
CREATE TABLE IF NOT EXISTS reviews (
    id INTEGER PRIMARY KEY AUTOINCREMENT, ticket_id TEXT REFERENCES tickets(id), decision TEXT,
    final_text TEXT, edit_distance REAL, review_seconds REAL, category_final TEXT, created_at TEXT
);
CREATE TABLE IF NOT EXISTS signals (
    ticket_id TEXT PRIMARY KEY REFERENCES tickets(id), customer_id TEXT, created_at TEXT, component TEXT,
    kind TEXT, entity TEXT, symptom TEXT, priority TEXT, confidence TEXT, model TEXT, problem_id TEXT,
    match_confidence REAL, matched TEXT, trace_id TEXT
);
CREATE TABLE IF NOT EXISTS problems (
    id TEXT PRIMARY KEY, component TEXT, kind TEXT, entity TEXT, title TEXT, status TEXT,
    first_ticket_at TEXT, last_ticket_at TEXT, detected_at TEXT, detected_at_n INTEGER,
    resolved_at TEXT, github_number INTEGER, github_url TEXT, issue_customers TEXT, merged_into TEXT
);
CREATE TABLE IF NOT EXISTS product_requests (
    problem_id TEXT PRIMARY KEY REFERENCES problems(id), title TEXT, body_md TEXT, payload TEXT, dropped TEXT,
    status TEXT, trace_id TEXT, cost_usd REAL, created_at TEXT, decided_at TEXT, decision TEXT
);
CREATE TABLE IF NOT EXISTS notices (
    problem_id TEXT REFERENCES problems(id), customer_id TEXT, ticket_id TEXT REFERENCES tickets(id), created_at TEXT,
    UNIQUE (problem_id, customer_id)
);
CREATE TABLE IF NOT EXISTS problem_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT, problem_id TEXT REFERENCES problems(id), kind TEXT,
    payload TEXT, created_at TEXT
);
"""
JSON_COLUMNS = ("reasons", "classification", "confidence", "evidence", "tool_calls", "tool_outputs", "escalation",
                "matched", "payload", "dropped")
LATE_COLUMNS = {  # added after the first schema; migrated in connect()
    "results": {"tool_outputs": "TEXT", "escalation": "TEXT"},
    "tickets": {"kind": "TEXT DEFAULT 'inbound'", "source": "TEXT DEFAULT 'live'", "problem_id": "TEXT"},
    "problems": {"issue_customers": "TEXT", "merged_into": "TEXT"},
}
TICKET_COLUMNS = "id, customer_id, channel, subject, body, created_at, mode, state, kind, source, problem_id"


def connect(path: str | None = None) -> sqlite3.Connection:
    conn = sqlite3.connect(path or os.environ.get("HADDOCK_DB", "haddock.db"), check_same_thread=False, timeout=10)
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    for table, late in LATE_COLUMNS.items():
        columns = {r["name"] for r in conn.execute(f"PRAGMA table_info({table})")}
        for column, sql_type in late.items():
            if column not in columns:
                conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {sql_type}")
    return conn


def mode_for(ticket_id: str) -> str:
    """Stable per id: the same ticket is always in the same mode."""
    return "manual" if hashlib.sha256(ticket_id.encode()).digest()[0] % MANUAL_SHARE == 0 else "copilot"


def insert_ticket(conn, ticket: TicketIn, *, source: str = "live", kind: str = "inbound",
                  mode: str | None = None, problem_id: str | None = None) -> str:
    """source=history: a radar ticket from the past; it never shows in the queue (docs/specs/radar.md)."""
    mode = mode or mode_for(ticket.id)
    state = "history" if source == "history" else "processing"
    try:
        with conn:
            conn.execute(
                f"INSERT INTO tickets ({TICKET_COLUMNS}) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (ticket.id, ticket.customer_id, ticket.channel, ticket.subject, ticket.body,
                 ticket.created_at.isoformat(), mode, state, kind, source, problem_id),
            )
    except sqlite3.IntegrityError as error:
        raise ValueError(f"ticket {ticket.id} already exists") from error
    return mode


def save_result(conn, result) -> None:
    c, a = result.classification, result.agent
    with conn:
        conn.execute(
            "INSERT OR REPLACE INTO results VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (result.ticket_id, result.status, json.dumps(result.reasons),
             json.dumps(c.classification.model_dump(mode="json")) if c else None,
             json.dumps(c.confidence) if c else None, int(result.review_category),
             a.draft if a else None, json.dumps(a.evidence if a else []),
             json.dumps(a.tool_calls if a else []), result.trace_id,
             a.cost_usd if a else 0.0, a.prompt_version if a else None,
             json.dumps(getattr(a, "tool_outputs", []) if a else []),
             json.dumps(vars(a.escalation)) if a and getattr(a, "escalation", None) else None),
        )
        conn.execute("UPDATE tickets SET state = ? WHERE id = ?", (result.status, result.ticket_id))


def _row(row: sqlite3.Row | None) -> dict | None:
    if row is None:
        return None
    d = dict(row)
    for col in JSON_COLUMNS:
        if d.get(col):
            d[col] = json.loads(d[col])
    return d


TICKET_QUERY = "SELECT t.*, r.* FROM tickets t LEFT JOIN results r ON r.ticket_id = t.id"


def list_tickets(conn, *, history: bool = False) -> list[dict]:
    where = "" if history else "WHERE t.source = 'live'"
    return [_row(r) for r in conn.execute(f"{TICKET_QUERY} {where} ORDER BY t.created_at DESC")]


def get_ticket(conn, ticket_id: str) -> dict | None:
    return _row(conn.execute(f"{TICKET_QUERY} WHERE t.id = ?", (ticket_id,)).fetchone())


def record_review(conn, ticket_id: str, decision: str, final_text: str, review_seconds: float,
                  category_final: str | None) -> dict:
    draft = (get_ticket(conn, ticket_id) or {}).get("draft") or ""
    edit_distance = 1.0 - SequenceMatcher(None, draft, final_text).ratio() if draft else 1.0
    review = {
        "ticket_id": ticket_id, "decision": decision, "final_text": final_text,
        "edit_distance": round(edit_distance, 4), "review_seconds": round(review_seconds, 1),
        "category_final": category_final, "created_at": datetime.now().isoformat(timespec="seconds"),
    }
    with conn:
        conn.execute(
            "INSERT INTO reviews (ticket_id, decision, final_text, edit_distance, review_seconds, "
            "category_final, created_at) VALUES (:ticket_id, :decision, :final_text, :edit_distance, "
            ":review_seconds, :category_final, :created_at)", review,
        )
        state = "rejected" if decision == "reject" else "sent"
        conn.execute("UPDATE tickets SET state = ? WHERE id = ?", (state, ticket_id))
    return review


def _avg(values: list[float]) -> float | None:
    return round(sum(values) / len(values), 3) if values else None


def metrics(conn) -> dict:
    tickets = list_tickets(conn)
    all_reviews = [dict(r) for r in conn.execute(
        "SELECT r.*, t.mode, t.kind FROM reviews r JOIN tickets t ON t.id = r.ticket_id")]
    reviews = [r for r in all_reviews if r["kind"] != "proactive"]  # notices are not the copilot/manual baseline
    tickets = [t for t in tickets if t.get("kind") != "proactive"]
    copilot = [r for r in reviews if r["mode"] == "copilot"]
    manual = [r for r in reviews if r["mode"] == "manual"]
    processed = [t for t in tickets if t.get("status")]
    predicted = {t["id"]: (t.get("classification") or {}).get("category") for t in tickets}

    avg_copilot = _avg([r["review_seconds"] for r in copilot])
    avg_manual = _avg([r["review_seconds"] for r in manual])
    return {
        "tickets": len(tickets),
        "processed": len(processed),
        "reviewed": len(reviews),
        "approved_unedited_rate": _avg([r["decision"] == "approve" for r in copilot]),
        "avg_seconds_copilot": avg_copilot,
        "avg_seconds_manual": avg_manual,
        "seconds_saved_per_ticket": round(avg_manual - avg_copilot, 1) if avg_manual and avg_copilot else None,
        "cost_per_ticket_usd": _avg([t["cost_usd"] or 0.0 for t in processed]),
        "escalation_rate": _avg([t["status"] == "escalated" for t in processed]),
        "category_corrections": sum(
            1 for r in reviews if r["category_final"] and r["category_final"] != predicted.get(r["ticket_id"])),
        "notices_sent": sum(1 for r in all_reviews if r["kind"] == "proactive" and r["decision"] != "reject"),
        "by_category": dict(Counter(
            (t.get("classification") or {}).get("category") for t in processed if t.get("classification"))),
    }
