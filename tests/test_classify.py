"""Classifier contract: docs/specs/classify.md. No network."""

from pydantic_ai.models.function import FunctionModel
from pydantic_ai.models.test import TestModel

from app.classify import ClassifyResult, TicketClassification, classify


def broken_model(messages, info):
    raise TimeoutError("Jev is down")


def test_classify_returns_a_typed_result():
    result = classify("Factura", "Mi factura sigue en procesando", model=TestModel())
    assert isinstance(result, ClassifyResult)
    assert isinstance(result.classification, TicketClassification)


def test_fallback_is_used_when_jev_fails():
    result = classify(
        "Factura", "Mi factura sigue en procesando",
        model=FunctionModel(broken_model), fallback_model=TestModel(),
    )
    assert result.confidence is None
    assert result.model == "fallback"


def test_priority_description_contains_the_urgent_definition():
    description = TicketClassification.model_fields["priority"].description
    assert "cierre" in description
