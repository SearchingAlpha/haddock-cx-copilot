"""Review evidence for guardrail blocking: insert a synthetic blocked ticket (no LLM) and capture both send states."""

from datetime import datetime
from types import SimpleNamespace

from playwright.sync_api import sync_playwright

from app import db
from app.classify import ClassifyResult, TicketClassification
from app.domain import Category, Language, Priority, Sentiment, TicketIn
from app.pipeline import TicketResult

conn = db.connect()
with conn:  # drop earlier evidence tickets
    conn.execute("DELETE FROM results WHERE ticket_id LIKE 'Z-BLOCK%'")
    conn.execute("DELETE FROM tickets WHERE id LIKE 'Z-BLOCK%'")
TID = next(f"Z-BLOCK-{i}" for i in range(100) if db.mode_for(f"Z-BLOCK-{i}") == "copilot")
ticket = TicketIn(id=TID, customer_id="C-004", channel="email", created_at=datetime(2026, 10, 3, 9, 30),
                  subject="Cobro duplicado del plan",
                  body="Hola, me habéis cobrado dos veces el plan este mes. ¿Me devolvéis uno?\n\nLaura")
db.insert_ticket(conn, ticket)
cls = TicketClassification(category=Category.account, priority=Priority.high, sentiment=Sentiment.negative,
                           language=Language.es)
result = TicketResult(TID, "escalated",
                      ClassifyResult(cls, {"category": 0.97, "priority": 0.8, "sentiment": 0.9, "language": 0.99}, "jev"),
                      reasons=["refund_promise"], trace_id="")
result.agent = SimpleNamespace(
    draft="Hola Laura:\n\nTranquila, te devolvemos el cobro duplicado esta misma semana.\n\nUn saludo,\n"
          "Equipo de soporte de haddock",
    evidence=["customer"], tool_calls=["get_customer"], cost_usd=0.01, prompt_version=1, tool_outputs=[],
    escalation=None)
db.save_result(conn, result)
print("ticket:", TID, db.get_ticket(conn, TID)["state"], db.get_ticket(conn, TID)["reasons"])

with sync_playwright() as pw:
    browser = pw.chromium.launch()
    page = browser.new_page(viewport={"width": 1440, "height": 900})
    page.goto("http://localhost:8000/tickets/" + TID, wait_until="networkidle")
    page.wait_for_timeout(400)
    print("send disabled before edit:", page.is_disabled("#send-btn"))
    page.screenshot(path=".impeccable/review/blocked-before-edit.png")
    page.keyboard.press("e")
    page.wait_for_timeout(200)
    page.locator("#final_text").fill(
        "Hola Laura:\n\nHe pasado tu caso al equipo de Finanzas, que revisará el cobro duplicado y te "
        "responderá por correo.\n\nUn saludo,\nEquipo de soporte de haddock")
    page.wait_for_timeout(200)
    print("send disabled after edit:", page.is_disabled("#send-btn"))
    page.screenshot(path=".impeccable/review/blocked-after-edit.png")
    browser.close()
