"""Product request contract: docs/specs/product-request.md. A fake Anthropic client: no network."""

from datetime import datetime, timedelta
from types import SimpleNamespace

import pytest

from app import db, problems, product_request, radar
from app.data import load_customers
from app.domain import Component, Kind, Priority, TicketIn
from app.product_request import Evidence, RequestDraft, check_quotes, scrub
from app.signals import Signal

T0 = datetime(2026, 9, 2, 10)
BODY = "Las facturas de Distribuciones Garrido salen en rojo desde septiembre. Llamadme al 612 345 678.\n\nElena Ruiz"


@pytest.fixture(scope="module")
def customers():
    return load_customers()


@pytest.fixture
def conn(tmp_path, customers):
    c = db.connect(str(tmp_path / "req.db"))
    for i, cid in enumerate(["C-021", "C-019", "C-022"]):
        when = T0 + timedelta(days=i)
        db.insert_ticket(c, TicketIn(id=f"R-{i}", customer_id=cid, channel="email", created_at=when,
                                     subject="Garrido", body=BODY), source="history")
        s = Signal(f"R-{i}", cid, when.isoformat(), BODY, Component.invoices_ocr, Kind.bug, "Distribuciones Garrido",
                   "El OCR no lee Garrido", priority=Priority.high)
        problems.assign(c, s, matcher=lambda text: problems.Match(True, 0.9))
        problems.refresh_status(c, "P-0001", customers, s.created_at)
    yield c
    c.close()


class FakeAnthropic:
    def __init__(self, draft: RequestDraft):
        self.draft, self.calls = draft, []
        self.messages = SimpleNamespace(parse=self.parse)

    def parse(self, **kw):
        self.calls.append(kw)
        usage = SimpleNamespace(input_tokens=1000, output_tokens=300, cache_read_input_tokens=0,
                                cache_creation_input_tokens=0)
        return SimpleNamespace(parsed_output=self.draft, stop_reason="end_turn", usage=usage)


def draft(**kw) -> RequestDraft:
    return RequestDraft(**{
        "title": "El OCR no lee Garrido", "summary": "Elena Ruiz dice que falla.", "repro_steps": ["Subir"],
        "suspected_component": "OCR", "acceptance_criteria": ["Se lee el total"],
        "evidence": [Evidence(ticket_id="R-0", quote="salen en  ROJO desde septiembre"),
                     Evidence(ticket_id="R-1", quote="el OCR explota con los PDF"),
                     Evidence(ticket_id="R-9", quote="Las facturas")], **kw})


def test_scrub_removes_names_contacts_emails_and_phones(customers):
    text = "Soy Elena Ruiz de Grupo Alcalá Food (elena@grupoalcalafood.es, 612 345 678). Elena."
    out = scrub(text, customers)
    for leaked in ("Elena", "Ruiz", "Alcalá", "@", "612"):
        assert leaked not in out
    assert "2026-09-01" in scrub("desde el 2026-09-01, 1.839 €", customers)  # dates and amounts survive


def test_only_literal_quotes_survive():
    texts = {"R-0": BODY, "R-1": BODY}
    kept, dropped = check_quotes(draft().evidence, texts)
    assert [e.ticket_id for e in kept] == ["R-0"]  # case and spaces aside
    assert [e.ticket_id for e in dropped] == ["R-1", "R-9"]  # invented, and a ticket that is not in the problem


def test_draft_request_writes_a_clean_issue_with_code_numbers(conn, customers, monkeypatch):
    monkeypatch.delenv("LANGFUSE_PUBLIC_KEY", raising=False)
    fake = FakeAnthropic(draft())
    req = radar.draft_for(conn, "P-0001", customers, client=fake)
    sent = fake.calls[0]["messages"][0]["content"]
    assert "Elena" not in sent and "612 345 678" not in sent  # Sonnet never sees PII
    assert "MRR de clientes afectados: 678 €" in sent  # 560 + 59 + 59: the facts come from code
    body = req.body_md
    assert body.startswith("<!-- haddock-problem:P-0001 -->")
    assert "| Clientes afectados | 3 |" in body and "C-021 · enterprise · 4 locales" in body
    assert "Elena" not in body and "Grupo Alcalá" not in body
    assert "salen en  ROJO" in body and "explota" not in body
    assert len(req.dropped) == 2
    assert product_request.load(conn, "P-0001")["status"] == "draft"
    assert conn.execute("SELECT title FROM problems WHERE id = 'P-0001'").fetchone()[0] == "El OCR no lee Garrido"


def test_a_refusal_leaves_no_draft(conn, customers):
    fake = FakeAnthropic(draft())
    fake.messages = SimpleNamespace(parse=lambda **kw: SimpleNamespace(parsed_output=None, stop_reason="refusal"))
    with pytest.raises(RuntimeError):
        radar.draft_for(conn, "P-0001", customers, client=fake)
    assert product_request.load(conn, "P-0001") is None


class FakeGitHub:
    def __init__(self):
        self.issues, self.comments = [], []

    def create_issue(self, title, body, labels):
        self.issues.append((title, body, labels))
        return {"number": 7, "url": "https://github.com/acme/demo/issues/7"}

    def comment(self, number, body):
        self.comments.append((number, body))
        return f"https://github.com/acme/demo/issues/{number}#c{len(self.comments)}"


def test_approve_creates_the_issue_and_new_customers_are_commented_once(conn, customers):
    radar.draft_for(conn, "P-0001", customers, client=FakeAnthropic(draft()))
    req = product_request.load(conn, "P-0001")
    gh = FakeGitHub()
    out = radar.approve(conn, "P-0001", customers, gh, title=req["title"], body=req["body_md"])
    assert out["decision"] == "approve" and gh.issues[0][2] == ["radar", "bug"]
    row = conn.execute("SELECT status, github_number FROM problems WHERE id = 'P-0001'").fetchone()
    assert tuple(row) == ("requested", 7)

    assert radar.comment_new_customers(conn, "P-0001", customers, gh) is None  # nobody new yet
    db.insert_ticket(conn, TicketIn(id="R-9", customer_id="C-008", channel="email", created_at=T0 + timedelta(days=9),
                                    subject="Garrido", body="otra vez"), source="history")
    s = Signal("R-9", "C-008", (T0 + timedelta(days=9)).isoformat(), "x", Component.invoices_ocr, Kind.bug,
               "Distribuciones Garrido", "El OCR no lee Garrido", priority=Priority.high)
    problems.assign(conn, s, matcher=lambda text: problems.Match(True, 0.9))
    assert radar.comment_new_customers(conn, "P-0001", customers, gh)
    assert gh.comments[0][0] == 7 and "+1 cliente" in gh.comments[0][1] and "C-008 · enterprise" in gh.comments[0][1]
    assert "4 clientes, 1.098 €/mes" in gh.comments[0][1]  # 560 + 59 + 59 + 420: the comma stays a comma
    assert radar.comment_new_customers(conn, "P-0001", customers, gh) is None  # once per new customer


def test_an_edited_request_is_recorded_as_edit(conn, customers):
    radar.draft_for(conn, "P-0001", customers, client=FakeAnthropic(draft()))
    req = product_request.load(conn, "P-0001")
    out = radar.approve(conn, "P-0001", customers, FakeGitHub(), title="Otro título", body=req["body_md"])
    assert out["decision"] == "edit"


def test_reject_dismisses_the_problem(conn, customers):
    radar.reject(conn, "P-0001")
    assert conn.execute("SELECT status FROM problems WHERE id = 'P-0001'").fetchone()[0] == "dismissed"
