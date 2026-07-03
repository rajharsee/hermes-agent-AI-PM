"""
jira_connector.client
======================
A small, dependency-light Jira Cloud REST API client authenticated via
API token (email + token), rather than OAuth. This is the deliberately
"boring" and stable path — no token refresh, no browser flow, works
identically from a cron job on a headless VPS.

Usage:
    from jira_connector.client import JiraClient

    jira = JiraClient(
        site_url="https://altbeing.atlassian.net",
        email="rajrkblr@gmail.com",
        api_token=os.environ["JIRA_API_TOKEN"],
    )
    issues = jira.search_issues('project = KAN AND statusCategory != Done')

Design notes (why it's built this way):
- Single class, no framework. Easy to unit-test with mocked `requests`.
- Every method returns plain dicts/lists (raw-ish JSON), not custom
  objects — keeps this layer dumb and the triage skill smart.
- Auth is API token only. OAuth is intentionally out of scope here;
  the Atlassian community reports OAuth/SSE tokens expiring mid-session
  for exactly this kind of long-running agent use case.
"""

from __future__ import annotations

import base64
import json
from dataclasses import dataclass, field
from typing import Any, Optional

import requests


class JiraClientError(Exception):
    """Raised for non-2xx responses, with the Jira error body attached."""

    def __init__(self, status_code: int, body: Any):
        self.status_code = status_code
        self.body = body
        super().__init__(f"Jira API error {status_code}: {body}")


@dataclass
class JiraClient:
    site_url: str  # e.g. "https://altbeing.atlassian.net"
    email: str
    api_token: str
    timeout: int = 20

    _session: requests.Session = field(init=False, repr=False)

    def __post_init__(self):
        self.site_url = self.site_url.rstrip("/")
        auth_str = f"{self.email}:{self.api_token}"
        b64 = base64.b64encode(auth_str.encode()).decode()
        self._session = requests.Session()
        self._session.headers.update(
            {
                "Authorization": f"Basic {b64}",
                "Accept": "application/json",
                "Content-Type": "application/json",
            }
        )

    # -- internal ---------------------------------------------------

    def _request(self, method: str, path: str, **kwargs) -> Any:
        url = f"{self.site_url}/rest/api/3{path}"
        resp = self._session.request(method, url, timeout=self.timeout, **kwargs)
        if resp.status_code >= 300:
            try:
                body = resp.json()
            except ValueError:
                body = resp.text
            raise JiraClientError(resp.status_code, body)
        if not resp.content:
            return None
        return resp.json()

    # -- read ---------------------------------------------------------

    def search_issues(
        self,
        jql: str,
        fields: Optional[list[str]] = None,
        max_results: int = 100,
    ) -> list[dict]:
        """Run a JQL search, paginating until all results are collected.

        Uses Jira's current /search/jql endpoint, which pages via
        nextPageToken rather than the deprecated startAt/isLast model.
        """
        fields = fields or [
            "summary",
            "description",
            "status",
            "priority",
            "issuetype",
            "labels",
            "created",
            "updated",
            "assignee",
            "comment",
        ]
        issues: list[dict] = []
        next_page_token: Optional[str] = None
        while True:
            body: dict[str, Any] = {
                "jql": jql,
                "fields": fields,
                "maxResults": min(max_results - len(issues), 100),
            }
            if next_page_token:
                body["nextPageToken"] = next_page_token
            page = self._request("POST", "/search/jql", data=json.dumps(body))
            batch = page.get("issues", [])
            issues.extend(batch)
            next_page_token = page.get("nextPageToken")
            if len(batch) == 0 or len(issues) >= max_results or not next_page_token:
                break
        return issues

    def get_issue(self, issue_key: str, fields: Optional[list[str]] = None) -> dict:
        params = {"fields": ",".join(fields)} if fields else None
        return self._request("GET", f"/issue/{issue_key}", params=params)

    # -- write ----------------------------------------------------------

    def add_comment(self, issue_key: str, markdown_body: str) -> dict:
        """Adds a plain-text/markdown-ish comment (wrapped as ADF paragraph)."""
        adf_body = {
            "type": "doc",
            "version": 1,
            "content": [
                {
                    "type": "paragraph",
                    "content": [{"type": "text", "text": markdown_body}],
                }
            ],
        }
        return self._request(
            "POST",
            f"/issue/{issue_key}/comment",
            data=json.dumps({"body": adf_body}),
        )

    def add_labels(self, issue_key: str, labels: list[str]) -> None:
        self._request(
            "PUT",
            f"/issue/{issue_key}",
            data=json.dumps({"update": {"labels": [{"add": l} for l in labels]}}),
        )

    def set_priority(self, issue_key: str, priority_name: str) -> None:
        self._request(
            "PUT",
            f"/issue/{issue_key}",
            data=json.dumps({"fields": {"priority": {"name": priority_name}}}),
        )

    def get_transitions(self, issue_key: str) -> list[dict]:
        data = self._request("GET", f"/issue/{issue_key}/transitions")
        return data.get("transitions", [])

    def transition_issue(self, issue_key: str, transition_id: str) -> None:
        self._request(
            "POST",
            f"/issue/{issue_key}/transitions",
            data=json.dumps({"transition": {"id": transition_id}}),
        )
