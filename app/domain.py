"""Domain models shared by data, tools, classifier and evals. Spec: docs/specs/data.md."""

from datetime import date, datetime
from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field


class Category(str, Enum):
    invoices = "invoices"
    bank = "bank"
    pos = "pos"
    inventory = "inventory"
    reports = "reports"
    account = "account"
    other = "other"


class Priority(str, Enum):
    low = "low"
    normal = "normal"
    high = "high"
    urgent = "urgent"


class Sentiment(str, Enum):
    positive = "positive"
    neutral = "neutral"
    negative = "negative"
    very_negative = "very_negative"


class Language(str, Enum):
    es = "es"
    ca = "ca"
    en = "en"


class Trap(str, Enum):
    refund_request = "refund_request"
    cross_customer = "cross_customer"
    angry = "angry"
    ambiguous = "ambiguous"
    deadline_pressure = "deadline_pressure"
    prompt_injection = "prompt_injection"


TOOL_NAMES = frozenset(
    {"search_kb", "get_customer", "get_invoices", "get_bank_sync_status", "escalate_to_human"}
)


class KBArticle(BaseModel):
    id: str
    title: str
    category: Category
    body: str


class Integration(BaseModel):
    kind: Literal["bank", "pos"]
    provider: str
    status: Literal["ok", "error", "disconnected"]
    last_sync: datetime | None = None
    error: str | None = None


class Invoice(BaseModel):
    id: str
    supplier: str
    issue_date: date
    uploaded_at: datetime
    amount_eur: float
    status: Literal["processed", "processing", "failed", "duplicate"]
    error: str | None = None


class Billing(BaseModel):
    monthly_price_eur: float
    payment_status: Literal["ok", "failed"]
    next_billing_date: date


class Customer(BaseModel):
    id: str
    name: str
    city: str
    plan: Literal["starter", "pro", "enterprise"]
    locations: int = Field(ge=1)
    contact_name: str
    contact_email: str
    signup_date: date
    billing: Billing
    integrations: list[Integration] = []
    invoices: list[Invoice] = []


class TicketLabels(BaseModel):
    """Ground truth for evals. Never shown to the classifier or the agent."""

    category: Category
    priority: Priority
    sentiment: Sentiment
    language: Language
    expected_tools: list[str]
    relevant_articles: list[str] = []
    key_points: list[str]
    should_escalate: bool
    trap: Trap | None = None


class TicketIn(BaseModel):
    """A ticket as it arrives (webhook). The pipeline only ever needs this."""

    id: str
    customer_id: str
    channel: Literal["email", "chat"]
    created_at: datetime
    subject: str
    body: str


class Ticket(TicketIn):
    """A labeled ticket from data/tickets.jsonl: the ground truth for evals."""

    labels: TicketLabels
