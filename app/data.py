"""Load and validate data/ files. Spec: docs/specs/data.md."""

import json
from pathlib import Path

from app.domain import Customer, KBArticle, RadarTicket, Ticket

DATA_DIR = Path(__file__).resolve().parent.parent / "data"


def load_kb(path: str | Path = DATA_DIR / "kb") -> list[KBArticle]:
    return [_parse_article(f) for f in sorted(Path(path).glob("*.md"))]


def load_customers(path: str | Path = DATA_DIR / "customers.json") -> dict[str, Customer]:
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    customers = [Customer.model_validate(c) for c in raw]
    return {c.id: c for c in customers}


def load_tickets(path: str | Path = DATA_DIR / "tickets.jsonl") -> list[Ticket]:
    lines = Path(path).read_text(encoding="utf-8").splitlines()
    return [Ticket.model_validate_json(line) for line in lines if line.strip()]


def load_radar_tickets(path: str | Path = DATA_DIR / "radar" / "tickets.jsonl") -> list[RadarTicket]:
    lines = Path(path).read_text(encoding="utf-8").splitlines()
    return [RadarTicket.model_validate_json(line) for line in lines if line.strip()]


def load_radar_truth(path: str | Path = DATA_DIR / "radar" / "truth.json") -> dict[str, dict]:
    """Planted problems by id: title, component, entity, kind, start, customers."""
    return {p["id"]: p for p in json.loads(Path(path).read_text(encoding="utf-8"))}


def _parse_article(file: Path) -> KBArticle:
    text = file.read_text(encoding="utf-8")
    parts = text.split("---", 2)
    if not text.startswith("---") or len(parts) < 3:
        raise ValueError(f"{file.name}: missing '---' header")
    header = {}
    for line in parts[1].strip().splitlines():
        key, _, value = line.partition(":")
        header[key.strip()] = value.strip()
    return KBArticle(**header, body=parts[2].strip())
