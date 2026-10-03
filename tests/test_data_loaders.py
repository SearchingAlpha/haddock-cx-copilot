"""Loader edge cases: docs/specs/data.md -> Errors and edge cases."""

import json

import pytest
from pydantic import ValidationError

from app.data import load_kb, load_tickets


def test_kb_article_without_header_raises(tmp_path):
    (tmp_path / "kb-99.md").write_text("Sin cabecera.", encoding="utf-8")
    with pytest.raises(ValueError, match="kb-99.md"):
        load_kb(tmp_path)


def test_kb_article_header_is_parsed(tmp_path):
    (tmp_path / "kb-99.md").write_text(
        '---\nid: kb-99\ntitle: Mi factura sigue en "procesando"\ncategory: invoices\n---\nTexto.\n',
        encoding="utf-8",
    )
    [article] = load_kb(tmp_path)
    assert article.id == "kb-99"
    assert article.title == 'Mi factura sigue en "procesando"'
    assert article.body == "Texto."


def _ticket(**labels) -> dict:
    return {
        "id": "T-999",
        "customer_id": "C-001",
        "channel": "email",
        "created_at": "2026-09-28T09:15:00",
        "subject": "Hola",
        "body": "Texto",
        "labels": {
            "category": "invoices",
            "priority": "normal",
            "sentiment": "neutral",
            "language": "es",
            "expected_tools": ["search_kb"],
            "relevant_articles": ["kb-02"],
            "key_points": ["algo"],
            "should_escalate": False,
            **labels,
        },
    }


def test_blank_lines_in_tickets_are_ignored(tmp_path):
    path = tmp_path / "tickets.jsonl"
    path.write_text("\n" + json.dumps(_ticket()) + "\n\n", encoding="utf-8")
    assert len(load_tickets(path)) == 1


def test_unknown_category_fails_validation(tmp_path):
    path = tmp_path / "tickets.jsonl"
    path.write_text(json.dumps(_ticket(category="pizza")), encoding="utf-8")
    with pytest.raises(ValidationError):
        load_tickets(path)
