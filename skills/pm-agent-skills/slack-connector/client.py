"""
slack_connector.client
========================
A minimal Slack Web API client for posting messages via a bot token.

Deliberate design decision: this is a standalone connector using a
plain bot token (xoxb-...) and chat.postMessage, NOT Hermes's built-in
Slack gateway. The gateway is the right tool for two-way conversation
(slash commands, events, threads Hermes should react to) but is a
heavier OAuth/Events-API setup. For a one-way "post a digest" use
case, a bot token is simpler and keeps this connector consistent with
jira-connector and notion-connector's architecture: small, dumb,
testable in isolation.

Critical Slack-specific gotcha, handled explicitly here: Slack's Web
API returns HTTP 200 for almost everything, including failures. The
actual success/failure signal is the "ok" field in the JSON body, not
the status code. Treating a 200 as success (as you reasonably would
for Jira or Notion) would silently swallow real errors here.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional

import requests

BASE_URL = "https://slack.com/api"


class SlackClientError(Exception):
    def __init__(self, error_code: str, response_body: dict):
        self.error_code = error_code
        self.response_body = response_body
        super().__init__(f"Slack API error: {error_code}")


@dataclass
class SlackClient:
    token: str
    timeout: int = 20

    _session: requests.Session = field(init=False, repr=False)

    def __post_init__(self):
        self._session = requests.Session()
        self._session.headers.update(
            {
                "Authorization": f"Bearer {self.token}",
                "Content-Type": "application/json; charset=utf-8",
            }
        )

    def post_message(
        self,
        channel: str,
        text: str,
        blocks: Optional[list[dict]] = None,
    ) -> dict:
        """Posts a message to a channel (channel ID, not name — Slack
        deprecated posting by channel name).

        `text` is always required, even when `blocks` is provided —
        Slack uses it as fallback text for notifications.
        """
        payload: dict[str, Any] = {"channel": channel, "text": text}
        if blocks:
            payload["blocks"] = blocks

        resp = self._session.post(
            f"{BASE_URL}/chat.postMessage", json=payload, timeout=self.timeout
        )
        body = resp.json()

        # Slack-specific: check "ok", not just HTTP status.
        if not body.get("ok"):
            raise SlackClientError(body.get("error", "unknown_error"), body)

        return body
