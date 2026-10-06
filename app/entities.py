"""Affected entity of a ticket: bank, POS or supplier. Deterministic, no LLM. Spec: docs/specs/radar.md."""

from dataclasses import dataclass

from app.domain import Component, Customer
from app.tools import _tokens

# Words that do not identify a supplier: "Distribuciones Garrido" is matched by "garrido".
GENERIC = set(
    "distribuciones distribucion pescados frutas fruites hermanos carnes selectas cooperativa huerta cafes "
    "carniceria mariscos rias sidra sidras profesional tortilleria app".split()  # "app": Last.app vs "la app"
)


@dataclass(frozen=True)
class Gazetteer:
    banks: dict[str, str]  # token -> provider name
    pos: dict[str, str]
    suppliers: dict[str, str]

    @classmethod
    def from_customers(cls, customers: dict[str, Customer]) -> "Gazetteer":
        banks, pos, suppliers = {}, {}, {}
        for c in customers.values():
            for i in c.integrations:
                for token in _keys(i.provider):
                    (banks if i.kind == "bank" else pos)[token] = i.provider
            for inv in c.invoices:
                for token in _keys(inv.supplier):
                    suppliers[token] = inv.supplier
        return cls(banks, pos, suppliers)


def _keys(name: str) -> list[str]:
    tokens = _tokens(name)
    distinctive = [t for t in tokens if t not in GENERIC]
    return distinctive or tokens


def _find(text_tokens: list[str], table: dict[str, str]) -> str | None:
    for token in text_tokens:  # first mention wins
        if token in table:
            return table[token]
    return None


def extract_entity(text: str, customer: Customer, component: Component, gazetteer: Gazetteer) -> str | None:
    """A named bank, POS or supplier in the text; else the customer's own bank or POS for that area.

    The area's own table goes first; then any table: "el P&L infla las ventas de Revo" is about Revo."""
    own = set(_tokens(f"{customer.name} {customer.contact_name}"))  # a signature "Elena Ruiz" is not "Frutas Ruiz"
    tokens = [t for t in _tokens(text) if t not in own]
    area = component.category.value
    tables = {"bank": gazetteer.banks, "pos": gazetteer.pos, "invoices": gazetteer.suppliers}
    if area in tables and (found := _find(tokens, tables[area])):
        return found
    if area in ("bank", "pos"):  # the customer has one bank and one POS: a safe default
        return next((i.provider for i in customer.integrations if i.kind == area), None)
    if area == "invoices":
        return None  # a customer has many suppliers: no default, and a bank named here is not the cause
    for table in tables.values():
        if found := _find(tokens, table):
            return found
    return None
