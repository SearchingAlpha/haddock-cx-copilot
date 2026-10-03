"""Prompt fallback: docs/specs/observability.md -> Prompt management."""

from app import prompts


def test_without_langfuse_the_local_file_is_used(monkeypatch):
    monkeypatch.delenv("LANGFUSE_PUBLIC_KEY", raising=False)
    p = prompts.get_prompt(prompts.AGENT_SYSTEM)
    assert p.client is None
    assert p.text == prompts.local_text(prompts.AGENT_SYSTEM)
    assert p.config["effort"] == "medium"


def test_langfuse_error_falls_back_to_local(monkeypatch):
    monkeypatch.setenv("LANGFUSE_PUBLIC_KEY", "pk-lf-test")

    class Broken:
        def get_prompt(self, *a, **kw):
            raise ConnectionError

    monkeypatch.setattr(prompts, "get_client", lambda: Broken())
    assert prompts.get_prompt(prompts.JUDGE).client is None


def test_local_compile_fills_variables(monkeypatch):
    monkeypatch.delenv("LANGFUSE_PUBLIC_KEY", raising=False)
    text = prompts.get_prompt(prompts.JUDGE).compile(ticket="T", key_points="K", draft="D", evidence="E")
    assert "{{" not in text
    assert "<draft>\nD\n</draft>" in text
