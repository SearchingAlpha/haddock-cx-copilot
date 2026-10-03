"""Stories contract: docs/specs/story.md."""

import re
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app import main
from app.story import STORIES

MACROS = set(re.findall(r"{%\s*macro\s+(\w+)\(",
                        (Path(main.__file__).parent / "templates" / "_scenes.html").read_text(encoding="utf-8")))


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("HADDOCK_DB", str(tmp_path / "story.db"))
    monkeypatch.setattr(main, "init_tracing", lambda: None)
    with TestClient(main.app) as c:
        yield c


@pytest.mark.parametrize("slug", STORIES)
def test_every_scene_has_kicker_title_and_an_existing_visual(slug):
    for scene in STORIES[slug].scenes:
        assert scene.kicker and scene.title, scene
        assert scene.title.count("<em>") <= 1, f"one accent per scene: {scene.kicker}"
        assert scene.visual is None or scene.visual in MACROS, scene.visual


@pytest.mark.parametrize("slug", STORIES)
def test_story_route_renders_every_scene_and_the_cta(client, slug):
    story = STORIES[slug]
    page = client.get(f"/{slug}")
    assert page.status_code == 200
    assert page.text.count('class="scene"') == len(story.scenes)
    assert story.cta in page.text


def test_presentation_does_not_claim_simulated_review_times():
    text = " ".join(str(s.title) + (s.note or "") for s in STORIES["presentacion"].scenes)
    assert "61" not in text and "288" not in text  # simulated seconds from phase 4 must never be shown as results
