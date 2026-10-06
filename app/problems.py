"""Group signals into product problems, and measure their impact. Spec: docs/specs/radar.md."""

import json
import threading
from collections import Counter
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime, timedelta

from langfuse import get_client, observe
from pydantic import BaseModel, Field
from pydantic_ai import Agent
from pydantic_ai.models import Model
from rank_bm25 import BM25Okapi

from app.config import (
    FALLBACK_CLASSIFIER_MODEL, MATCH_MODEL, RADAR_BM25_TOP_K, RADAR_MATCH_CONFIDENCE, RADAR_PROBLEM_SYMPTOMS,
    RADAR_THRESHOLD, TREND_WINDOW_DAYS,
)
from app.domain import CLUSTERED_KINDS, Customer
from app.signals import Signal
from app.tools import _tokens

ACTIVE = ("open", "candidate", "requested")  # a dismissed or resolved problem takes no new tickets
_lock = threading.Lock()  # one uvicorn process: two tickets at once must not open the same problem twice


# --- matcher: one yes/no question per candidate ---------------------------------------------------

class _SameProblem(BaseModel):
    same: bool = Field(
        description="Do the new ticket and the known product problem have the same cause in haddock, so that "
        "one fix in the product solves both? The same symptom with another cause is not the same problem: "
        "a blurry photo is not an OCR bug, a changed password is not a bank outage."
    )


@dataclass
class Match:
    same: bool
    confidence: float | None  # None: the fallback answered, no calibrated confidence


def _match_agent(model: str | Model) -> Agent[None, _SameProblem]:
    # Not cached: see app/classify.py::_agent (async client bound to one event loop).
    return Agent(model, output_type=_SameProblem, name="same-problem")


def match_text(problem_doc: str, signal: Signal) -> str:
    return (f"Known product problem:\n{problem_doc}\n\n"
            f"New ticket (symptom: {signal.symptom}):\n<ticket>\n{signal.text}\n</ticket>")


@observe(name="same_problem")
def jev_same_problem(text: str, *, model: str | Model | None = None,
                     fallback_model: str | Model | None = None) -> Match:
    try:
        result = _match_agent(model or MATCH_MODEL).run_sync(text)
        confidence = (result.response.provider_details or {}).get("confidence") or {}
        return Match(result.output.same, confidence.get("same"))
    except Exception as error:
        get_client().update_current_span(level="WARNING", status_message=f"Jev failed, fallback: {error!r}")
        result = _match_agent(fallback_model or FALLBACK_CLASSIFIER_MODEL).run_sync(text)
        return Match(result.output.same, None)


# --- storage helpers ------------------------------------------------------------------------------

def _event(conn, problem_id: str, kind: str, payload: dict, at: str) -> None:
    conn.execute("INSERT INTO problem_events (problem_id, kind, payload, created_at) VALUES (?, ?, ?, ?)",
                 (problem_id, kind, json.dumps(payload, ensure_ascii=False), at))


def save_signal(conn, s: Signal) -> None:
    with conn:
        conn.execute(
            "INSERT OR REPLACE INTO signals VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (s.ticket_id, s.customer_id, s.created_at, s.component.value, s.kind.value, s.entity, s.symptom,
             s.priority.value if s.priority else None, json.dumps(s.confidence), s.model, s.problem_id,
             s.match_confidence, json.dumps(s.matched, ensure_ascii=False), s.trace_id),
        )
        conn.execute("UPDATE tickets SET problem_id = ? WHERE id = ?", (s.problem_id, s.ticket_id))


def problem_signals(conn, problem_id: str) -> list[dict]:
    return [dict(r) for r in conn.execute(
        "SELECT * FROM signals WHERE problem_id = ? ORDER BY created_at", (problem_id,))]


def problem_doc(conn, problem: dict) -> str:
    """What BM25 and the matcher read: the title and the last symptoms."""
    rows = conn.execute("SELECT symptom FROM signals WHERE problem_id = ? ORDER BY created_at DESC LIMIT ?",
                        (problem["id"], RADAR_PROBLEM_SYMPTOMS)).fetchall()
    return "\n".join([problem["title"], *(f"- {r['symptom']}" for r in rows)])


def candidates(conn, signal: Signal) -> list[dict]:
    """Active problems of the same kind that the matcher should see.

    With an entity: the same area or the same entity, and a compatible entity (equal, or the problem has none).
    Jev puts some Garrido tickets in invoices.suppliers, and "el P&L infla las ventas de Revo" in reports.pnl.
    Without an entity: the same component only. "El Excel del P&L suma el IVA" must not reach a Revo problem.
    """
    active = f"kind = ? AND status IN ({','.join('?' * len(ACTIVE))})"
    if signal.entity is None:
        rows = conn.execute(f"SELECT * FROM problems WHERE {active} AND component = ? ORDER BY id",
                            (signal.kind.value, *ACTIVE, signal.component.value))
    else:
        rows = conn.execute(
            f"SELECT * FROM problems WHERE {active} AND (entity IS NULL OR entity = ?) "
            "AND (component LIKE ? OR entity = ?) ORDER BY id",
            (signal.kind.value, *ACTIVE, signal.entity, f"{signal.component.category.value}.%", signal.entity))
    return [dict(r) for r in rows]


def _relabel(conn, problem_id: str) -> None:
    """A problem's component and entity are the most common among its tickets, not the first ticket's."""
    rows = conn.execute("SELECT component, entity FROM signals WHERE problem_id = ?", (problem_id,)).fetchall()
    component = Counter(r["component"] for r in rows).most_common(1)[0][0]
    entities = Counter(r["entity"] for r in rows if r["entity"])
    entity = entities.most_common(1)[0][0] if entities else None
    conn.execute("UPDATE problems SET component = ?, entity = ? WHERE id = ?", (component, entity, problem_id))


def rank(problems: list[dict], docs: dict[str, str], signal: Signal, top_k: int = RADAR_BM25_TOP_K) -> list[dict]:
    if len(problems) <= top_k:  # few documents: BM25's IDF is flat or negative, send them all
        return problems
    bm25 = BM25Okapi([_tokens(docs[p["id"]]) for p in problems])
    scores = bm25.get_scores(_tokens(f"{signal.symptom} {signal.text}"))
    ranked = sorted(zip(scores, range(len(problems))), key=lambda pair: (-pair[0], pair[1]))
    return [problems[i] for _, i in ranked[:top_k]]


def _new_problem(conn, signal: Signal) -> str:
    n = conn.execute("SELECT COUNT(*) FROM problems").fetchone()[0] + 1
    pid = f"P-{n:04d}"
    conn.execute(
        "INSERT INTO problems (id, component, kind, entity, title, status, first_ticket_at, last_ticket_at) "
        "VALUES (?, ?, ?, ?, ?, 'open', ?, ?)",
        (pid, signal.component.value, signal.kind.value, signal.entity, signal.symptom, signal.created_at,
         signal.created_at),
    )
    _event(conn, pid, "opened", {"ticket_id": signal.ticket_id}, signal.created_at)
    return pid


# --- assignment -------------------------------------------------------------------------------------

@observe(name="assign-problem")
def assign(conn, signal: Signal, *, matcher: Callable[[str], Match] = jev_same_problem,
           threshold: float = RADAR_MATCH_CONFIDENCE) -> str | None:
    """Put the signal in a problem: the best "yes" of the matcher, or a new problem. how_to/user_error: none."""
    if signal.kind not in CLUSTERED_KINDS:
        save_signal(conn, signal)
        return None
    with _lock:
        found = candidates(conn, signal)
        docs = {p["id"]: problem_doc(conn, p) for p in found}
        yes: list[tuple[float, dict]] = []
        for p in rank(found, docs, signal):
            try:
                m = matcher(match_text(docs[p["id"]], signal))
            except Exception as error:  # a failed question never merges: at worst we split
                get_client().update_current_span(level="WARNING", status_message=f"matcher failed: {error!r}")
                continue
            conf = m.confidence if m.confidence is not None else threshold
            signal.matched.append({"problem_id": p["id"], "same": m.same, "confidence": m.confidence})
            if m.same and conf >= threshold:
                yes.append((conf, p))
        with conn:
            if yes:
                yes.sort(key=lambda pair: -pair[0])
                best, best_conf = yes[0][1]["id"], yes[0][0]
                if len(yes) > 1:  # "yes" to two problems: they are one problem, split by an earlier weak answer
                    best = merge(conn, [p for _, p in yes], signal.created_at)
                conn.execute("UPDATE problems SET last_ticket_at = MAX(last_ticket_at, ?) WHERE id = ?",
                             (signal.created_at, best))
                _event(conn, best, "ticket_added", {"ticket_id": signal.ticket_id, "confidence": best_conf},
                       signal.created_at)
                signal.match_confidence = best_conf
            else:
                best = _new_problem(conn, signal)
        signal.problem_id = best
        save_signal(conn, signal)
        with conn:
            _relabel(conn, best)
    get_client().update_current_span(output={"problem_id": best, "matched": signal.matched})
    return best


STATUS_RANK = {"requested": 0, "candidate": 1, "open": 2}  # the survivor of a merge keeps its issue


def merge(conn, group: list[dict], at: str) -> str:
    """Fold the problems of `group` into one. Survivor: the one with an issue, then the biggest, then the oldest."""
    sizes = {p["id"]: conn.execute("SELECT COUNT(*) FROM signals WHERE problem_id = ?", (p["id"],)).fetchone()[0]
             for p in group}
    group = sorted(group, key=lambda p: (STATUS_RANK.get(p["status"], 3), -sizes[p["id"]], p["id"]))
    survivor, rest = group[0], group[1:]
    for p in rest:
        if p["status"] == "requested":  # two issues already: a human merges them, not the radar
            continue
        conn.execute("UPDATE signals SET problem_id = ? WHERE problem_id = ?", (survivor["id"], p["id"]))
        conn.execute("UPDATE tickets SET problem_id = ? WHERE problem_id = ?", (survivor["id"], p["id"]))
        conn.execute("UPDATE problems SET status = 'merged', merged_into = ? WHERE id = ?", (survivor["id"], p["id"]))
        conn.execute("UPDATE problems SET first_ticket_at = MIN(first_ticket_at, ?) WHERE id = ?",
                     (p["first_ticket_at"], survivor["id"]))
        _event(conn, survivor["id"], "merged", {"from": p["id"], "tickets": sizes[p["id"]]}, at)
        _event(conn, p["id"], "merged", {"into": survivor["id"]}, at)
    return survivor["id"]


# --- impact and threshold ---------------------------------------------------------------------------

@dataclass
class Impact:
    tickets: int
    customers: list[str]
    mrr_eur: float
    severity: float  # share of urgent or high tickets
    trend: float  # last 7 days against the weekly mean of the 3 weeks before, clamped to 0.5-2
    score: float
    weekly: list[int] = field(default_factory=list)  # tickets per week, oldest first, for the sparkline


def impact(signals: list[dict], customers: dict[str, Customer], now: datetime, weeks: int = 6) -> Impact:
    ids = sorted({s["customer_id"] for s in signals})
    mrr = sum(customers[c].billing.monthly_price_eur for c in ids if c in customers)
    severity = sum(s["priority"] in ("urgent", "high") for s in signals) / len(signals) if signals else 0.0
    window = timedelta(days=TREND_WINDOW_DAYS)
    at = [datetime.fromisoformat(s["created_at"]) for s in signals]
    weekly = [sum(now - (w + 1) * window < t <= now - w * window for t in at) for w in reversed(range(weeks))]
    # One week against one week lies with small numbers (1 ticket after a quiet week = x2): compare the last
    # week with the mean of the 3 before. +1 on both sides: a brand-new problem is "up", not infinite.
    recent, before = weekly[-1], sum(weekly[-4:-1]) / 3
    trend = min(2.0, max(0.5, (recent + 1) / (before + 1)))
    return Impact(len(signals), ids, round(mrr, 2), round(severity, 3), round(trend, 2),
                  round(mrr * (1 + 0.5 * severity) * trend, 1), weekly)


def crosses_threshold(imp: Impact) -> bool:
    t = RADAR_THRESHOLD
    return len(imp.customers) >= t["customers"] or (
        len(imp.customers) >= t["mrr_min_customers"] and imp.mrr_eur >= t["mrr_eur"])


def now_of(conn) -> datetime:
    """'Now' for the radar: the newest ticket in the database, so the same data gives the same numbers."""
    latest = conn.execute("SELECT MAX(created_at) FROM tickets").fetchone()[0]
    return datetime.fromisoformat(latest) if latest else datetime.now()


def refresh_status(conn, problem_id: str, customers: dict[str, Customer], at: str) -> str:
    """open -> candidate when the threshold is crossed. Guarded UPDATE: running it twice changes nothing."""
    signals = problem_signals(conn, problem_id)
    imp = impact(signals, customers, datetime.fromisoformat(at))
    if crosses_threshold(imp):
        with conn:
            changed = conn.execute(
                "UPDATE problems SET status = 'candidate', detected_at = ?, detected_at_n = ? "
                "WHERE id = ? AND status = 'open'", (at, imp.tickets, problem_id)).rowcount
            if changed:
                _event(conn, problem_id, "threshold", {"tickets": imp.tickets, "customers": len(imp.customers),
                                                       "mrr_eur": imp.mrr_eur}, at)
    return conn.execute("SELECT status FROM problems WHERE id = ?", (problem_id,)).fetchone()[0]


# --- read side: what /radar shows -------------------------------------------------------------------

def list_problems(conn, customers: dict[str, Customer], *, include_merged: bool = False) -> list[dict]:
    """Every problem with its impact and its customers, best score first. 'Now' = newest ticket."""
    now = now_of(conn)
    where = "" if include_merged else "WHERE status != 'merged'"
    out = []
    for row in conn.execute(f"SELECT * FROM problems {where}").fetchall():
        p = dict(row)
        signals = problem_signals(conn, p["id"])
        p["impact"] = impact(signals, customers, now)
        p["by_customer"] = dict(Counter(s["customer_id"] for s in signals))
        out.append(p)
    out.sort(key=lambda p: (-p["impact"].score, p["id"]))
    return out


def get_problem(conn, problem_id: str, customers: dict[str, Customer]) -> dict | None:
    row = conn.execute("SELECT * FROM problems WHERE id = ?", (problem_id,)).fetchone()
    if row is None:
        return None
    p = dict(row)
    p["signals"] = problem_signals(conn, problem_id)
    for s in p["signals"]:
        s["matched"] = json.loads(s["matched"] or "[]")
        t = conn.execute("SELECT subject, body, channel FROM tickets WHERE id = ?", (s["ticket_id"],)).fetchone()
        s.update(dict(t) if t else {})
    p["impact"] = impact(p["signals"], customers, now_of(conn))
    p["by_customer"] = dict(Counter(s["customer_id"] for s in p["signals"]))
    p["events"] = [dict(r) | {"payload": json.loads(r["payload"] or "{}")} for r in conn.execute(
        "SELECT * FROM problem_events WHERE problem_id = ? ORDER BY created_at, id", (problem_id,))]
    return p
