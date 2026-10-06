"""GitHub issues for product requests, over the REST API with httpx. Spec: docs/specs/github.md."""

import hashlib
import hmac
import os
import secrets

import httpx
from langfuse import get_client, observe

from app.config import GITHUB_API


class GitHubError(Exception):
    def __init__(self, status: int, message: str):
        super().__init__(f"GitHub {status}: {message}")
        self.status = status


class GitHub:
    def __init__(self, token: str, repo: str, *, api: str = GITHUB_API, transport: httpx.BaseTransport | None = None):
        self._token, self.repo, self._api, self._transport = token, repo, api, transport

    def _request(self, method: str, path: str, **kwargs) -> dict | list:
        headers = {"Authorization": f"Bearer {self._token}", "Accept": "application/vnd.github+json",
                   "X-GitHub-Api-Version": "2022-11-28"}
        with httpx.Client(base_url=self._api, headers=headers, timeout=10, transport=self._transport) as client:
            r = client.request(method, path, **kwargs)
        if r.status_code >= 400:  # no retries: creating an issue twice is worse than failing once
            try:
                body = r.json()
                message = body.get("message", "") + (f" {body['errors']}" if body.get("errors") else "")
            except ValueError:
                message = r.text[:200]
            raise GitHubError(r.status_code, message)
        return r.json()

    @observe(name="github.create_issue", as_type="tool", capture_input=False, capture_output=False)
    def create_issue(self, title: str, body: str, labels: list[str]) -> dict:
        get_client().update_current_span(input={"repo": self.repo, "title": title, "labels": labels})
        issue = self._request("POST", f"/repos/{self.repo}/issues", json={"title": title, "body": body, "labels": labels})
        out = {"number": issue["number"], "url": issue["html_url"]}
        get_client().update_current_span(output=out)
        return out

    @observe(name="github.comment", as_type="tool", capture_input=False, capture_output=False)
    def comment(self, number: int, body: str) -> str:
        get_client().update_current_span(input={"repo": self.repo, "number": number, "body": body})
        url = self._request("POST", f"/repos/{self.repo}/issues/{number}/comments", json={"body": body})["html_url"]
        get_client().update_current_span(output={"url": url})
        return url

    @observe(name="github.get_issue", as_type="tool", capture_input=False, capture_output=False)
    def get_issue(self, number: int) -> dict:
        get_client().update_current_span(input={"repo": self.repo, "number": number})
        out = _issue(self._request("GET", f"/repos/{self.repo}/issues/{number}"))
        get_client().update_current_span(output=out)
        return out

    @observe(name="github.list_issues", as_type="tool", capture_input=False, capture_output=False)
    def list_issues(self, *, state: str = "all", labels: str = "radar", since: str | None = None) -> list[dict]:
        params = {"state": state, "labels": labels, "per_page": 100, **({"since": since} if since else {})}
        get_client().update_current_span(input={"repo": self.repo, **params})
        out = [_issue(i) for i in self._request("GET", f"/repos/{self.repo}/issues", params=params)
               if "pull_request" not in i]
        get_client().update_current_span(output={"issues": len(out)})
        return out


def _issue(i: dict) -> dict:
    return {"number": i["number"], "state": i["state"], "state_reason": i.get("state_reason"),
            "url": i["html_url"], "title": i.get("title", ""), "body": i.get("body") or ""}


def from_env() -> GitHub | None:
    token, repo = os.environ.get("GITHUB_TOKEN"), os.environ.get("GITHUB_REPO")
    return GitHub(token, repo) if token and repo else None


def verify_signature(body: bytes, header: str | None, secret: str) -> bool:
    """X-Hub-Signature-256 = "sha256=" + HMAC-SHA256(secret, body)."""
    if not header or not secret:
        return False
    expected = "sha256=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    return secrets.compare_digest(expected, header)
