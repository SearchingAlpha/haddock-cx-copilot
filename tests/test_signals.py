"""Signal and entity contract: docs/specs/radar.md. No network: pydantic-ai TestModel / FunctionModel."""

from datetime import datetime

import pytest
from pydantic_ai.models.function import FunctionModel
from pydantic_ai.models.test import TestModel

from app.classify import ClassifyResult, TicketClassification
from app.data import load_customers
from app.domain import Category, Component, Language, Priority, Sentiment, TicketIn
from app.entities import Gazetteer, extract_entity
from app.signals import TicketSignal, extract_signal, typed_signal


@pytest.fixture(scope="module")
def customers():
    return load_customers()


@pytest.fixture(scope="module")
def gazetteer(customers):
    return Gazetteer.from_customers(customers)


def broken_model(messages, info):
    raise TimeoutError("Jev is down")


def test_entity_named_in_the_text(customers, gazetteer):
    text = "Las facturas de Garrido no se leen"
    assert extract_entity(text, customers["C-018"], Component.invoices_ocr, gazetteer) == "Distribuciones Garrido"


def test_entity_defaults_to_the_customers_own_bank_or_pos(customers, gazetteer):
    assert extract_entity("no sincroniza", customers["C-011"], Component.bank_sync, gazetteer) == "Kutxabank"
    assert extract_entity("ventas dobles", customers["C-003"], Component.pos_sales, gazetteer) == "Revo"


def test_invoices_have_no_default_entity(customers, gazetteer):
    assert extract_entity("la factura no se lee", customers["C-018"], Component.invoices_ocr, gazetteer) is None


def test_signature_names_are_not_entities(customers, gazetteer):
    """C-021's contact is Elena Ruiz: not the supplier Frutas Hermanos Ruiz."""
    text = "El OCR no lee la factura\n\nElena Ruiz"
    assert extract_entity(text, customers["C-021"], Component.invoices_ocr, gazetteer) is None


def test_the_app_is_not_last_app(customers, gazetteer):
    text = "No veo las ventas en la app del TPV Revo"
    assert extract_entity(text, customers["C-001"], Component.pos_sync, gazetteer) == "Revo"


def test_typed_signal_falls_back_without_confidence():
    out, confidence, model = typed_signal("x", model=FunctionModel(broken_model), fallback_model=TestModel())
    assert isinstance(out, TicketSignal)
    assert (confidence, model) == (None, "fallback")


def test_extract_signal_uses_the_given_classification(customers, gazetteer, monkeypatch):
    monkeypatch.delenv("LANGFUSE_PUBLIC_KEY", raising=False)
    ticket = TicketIn(id="R-1", customer_id="C-011", channel="email", created_at=datetime(2026, 9, 16, 9),
                      subject="Banco", body="Kutxabank no sincroniza")
    c = ClassifyResult(TicketClassification(category=Category.bank, priority=Priority.urgent,
                                            sentiment=Sentiment.negative, language=Language.es), None, "jev")
    s = extract_signal(ticket, customers["C-011"], gazetteer, classification=c,
                       model=TestModel(custom_output_args={"component": "bank.sync", "kind": "bug"}),
                       symptom_model=TestModel(custom_output_args={"symptom": "Kutxabank no sincroniza"}))
    assert (s.component, s.kind.value, s.entity) == (Component.bank_sync, "bug", "Kutxabank")
    assert s.priority == Priority.urgent
    assert s.symptom == "Kutxabank no sincroniza"


def test_component_prefix_is_a_category():
    for c in Component:
        assert isinstance(c.category, Category)


def test_other_areas_take_an_entity_named_anywhere(customers, gazetteer):
    text = "El P&L infla las ventas: Revo registra la mitad"
    assert extract_entity(text, customers["C-021"], Component.reports_pnl, gazetteer) == "Revo"
    assert extract_entity("El escandallo no cambia", customers["C-021"], Component.inventory_recipes,
                          gazetteer) is None
