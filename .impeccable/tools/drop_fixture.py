"""Remove the synthetic review fixture tickets (Z-BLOCK-*) from the demo database."""

from app import db

conn = db.connect()
with conn:
    conn.execute("DELETE FROM results WHERE ticket_id LIKE 'Z-BLOCK%'")
    conn.execute("DELETE FROM reviews WHERE ticket_id LIKE 'Z-BLOCK%'")
    conn.execute("DELETE FROM tickets WHERE id LIKE 'Z-BLOCK%'")
pending = sum(t["state"] in ("ready", "escalated") for t in db.list_tickets(conn))
escalated = sum(t["state"] == "escalated" for t in db.list_tickets(conn))
print(f"pending={pending} escalated={escalated}")
