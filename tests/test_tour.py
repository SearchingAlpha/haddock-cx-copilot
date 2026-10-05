"""Code tour contract: docs/specs/tour.md."""

import pytest
from fastapi.testclient import TestClient

from app import main
from app.tour import TOUR, Excerpt, resolve


@pytest.mark.parametrize("stop", TOUR, ids=lambda s: s.kicker)
def test_every_stop_resolves(stop):
    assert stop.kicker and stop.title and stop.points
    assert stop.title.count("<em>") <= 1
    for excerpt in stop.excerpts:
        shown = resolve(excerpt)
        assert shown.text.strip(), excerpt


def test_python_symbol_includes_its_decorator():
    shown = resolve(Excerpt("app/agent.py", symbol="run_agent"))
    assert shown.kind == "code" and shown.language == "python"
    assert shown.text.startswith("@observe")
    assert shown.location.startswith("app/agent.py:")


def test_diagram_and_section():
    assert resolve(Excerpt("docs/specs/overview.md", diagram=1)).text.startswith("flowchart TD")
    assert resolve(Excerpt("CLAUDE.md", section="## Reglas")).text.startswith("## Reglas")


def test_missing_symbol_raises():
    with pytest.raises(LookupError):
        resolve(Excerpt("app/agent.py", symbol="no_such_function"))


def test_tour_page(tmp_path, monkeypatch):
    monkeypatch.setenv("HADDOCK_DB", str(tmp_path / "tour.db"))
    monkeypatch.setattr(main, "init_tracing", lambda: None)
    with TestClient(main.app) as client:
        r = client.get("/codigo")
    assert r.status_code == 200
    assert "def run_agent" in r.text
