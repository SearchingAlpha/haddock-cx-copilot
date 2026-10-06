"""GitHub client contract: docs/specs/github.md. httpx.MockTransport: no network."""

import hashlib
import hmac
import json

import httpx
import pytest

from app.github import GitHub, GitHubError, verify_signature


def gh(handler) -> GitHub:
    return GitHub("tok-secret", "acme/demo", transport=httpx.MockTransport(handler))


def test_create_issue_sends_title_body_labels_and_headers():
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["path"], seen["headers"], seen["json"] = request.url.path, request.headers, json.loads(request.content)
        return httpx.Response(201, json={"number": 12, "html_url": "https://github.com/acme/demo/issues/12"})

    assert gh(handler).create_issue("T", "B", ["radar", "bug"]) == {
        "number": 12, "url": "https://github.com/acme/demo/issues/12"}
    assert seen["path"] == "/repos/acme/demo/issues"
    assert seen["json"] == {"title": "T", "body": "B", "labels": ["radar", "bug"]}
    assert seen["headers"]["authorization"] == "Bearer tok-secret"
    assert seen["headers"]["x-github-api-version"] == "2022-11-28"


@pytest.mark.parametrize("status", [401, 403, 422])
def test_errors_raise_with_githubs_message(status):
    def handler(request):
        return httpx.Response(status, json={"message": "nope", "errors": [{"field": "labels"}]})

    with pytest.raises(GitHubError) as e:
        gh(handler).comment(1, "x")
    assert e.value.status == status and "nope" in str(e.value)


def test_list_issues_skips_pull_requests():
    def handler(request):
        assert request.url.params["labels"] == "radar"
        return httpx.Response(200, json=[
            {"number": 1, "state": "closed", "state_reason": "completed", "html_url": "u1", "title": "a", "body": "b"},
            {"number": 2, "state": "open", "html_url": "u2", "pull_request": {}},
        ])

    assert [i["number"] for i in gh(handler).list_issues(state="closed")] == [1]


def test_the_token_never_reaches_the_span(monkeypatch):
    captured = []

    class Client:
        def update_current_span(self, **kw):
            captured.append(kw)

    monkeypatch.setattr("app.github.get_client", lambda: Client())
    gh(lambda r: httpx.Response(201, json={"number": 1, "html_url": "u"})).create_issue("T", "B", ["radar"])
    assert captured and "tok-secret" not in json.dumps(captured)


def test_webhook_signature():
    body = b'{"action":"closed"}'
    good = "sha256=" + hmac.new(b"s3cret", body, hashlib.sha256).hexdigest()
    assert verify_signature(body, good, "s3cret")
    assert not verify_signature(body, good, "other")
    assert not verify_signature(body, None, "s3cret")
    assert not verify_signature(body, good, "")
