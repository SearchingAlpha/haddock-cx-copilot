from pathlib import Path

import pytest

SPECS = sorted((Path(__file__).parent.parent / "docs" / "specs").glob("*.md"))


def test_overview_spec_exists():
    assert any(spec.name == "overview.md" for spec in SPECS)


@pytest.mark.parametrize("spec", SPECS, ids=lambda p: p.name)
def test_every_spec_has_a_mermaid_diagram(spec: Path):
    assert "```mermaid" in spec.read_text(encoding="utf-8")
