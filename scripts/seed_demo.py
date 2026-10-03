"""Send a chosen set of dataset tickets through the webhook, for the demo or for UI work.

    python -m scripts.seed_demo                      # the default demo mix
    python -m scripts.seed_demo T-001 T-011 T-020
"""

import sys
import time

import httpx

from app.data import load_tickets

DEMO = ["T-001", "T-002", "T-006", "T-011", "T-020", "T-021", "T-026"]  # every state the UI must show


def main() -> None:
    wanted = sys.argv[1:] or DEMO
    base = "http://localhost:8000"
    for _ in range(30):  # wait for the server
        try:
            httpx.get(base + "/queue", timeout=2)
            break
        except httpx.HTTPError:
            time.sleep(1)
    tickets = {t.id: t for t in load_tickets()}
    for tid in wanted:
        r = httpx.post(base + "/webhooks/ticket", json=tickets[tid].model_dump(mode="json", exclude={"labels"}))
        print(tid, r.status_code, r.json().get("mode", r.text[:80]))


if __name__ == "__main__":
    main()
