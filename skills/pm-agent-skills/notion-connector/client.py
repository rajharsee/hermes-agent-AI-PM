"""
notion_connector.client
=========================
A small Notion API client for creating pages inside a database, with a
minimal Markdown-to-Notion-blocks converter attached.

Deliberate design decision: pinned to Notion-Version "2022-06-28".
Notion's 2025-09-03+ API versions restructured databases into
"data sources" and expect parent={"data_source_id": ...} instead of
parent={"database_id": ...}. Notion explicitly supports pinning an
older version per-request during migration, and the older
database_id-based flow is simpler and has fewer moving parts for a
single-user tool like this one. If Notion deprecates 2022-06-28
outright, this is the first place to look — see references/config.md.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Optional

import requests

NOTION_VERSION = "2022-06-28"
BASE_URL = "https://api.notion.com/v1"


class NotionClientError(Exception):
    def __init__(self, status_code: int, body: Any):
        self.status_code = status_code
        self.body = body
        super().__init__(f"Notion API error {status_code}: {body}")


def markdown_to_blocks(markdown_text: str) -> list[dict]:
    """Minimal Markdown -> Notion block converter.

    Supports only what a PRD template needs: #/##/### headings,
    "- " bulleted list items, "---" dividers, and plain paragraphs.
    Not a general-purpose Markdown parser by design — the PRD template
    in references/template.md is deliberately restricted to these.
    """
    blocks: list[dict] = []

    def text_obj(content: str) -> list[dict]:
        return [{"type": "text", "text": {"content": content}}]

    for raw_line in markdown_text.splitlines():
        line = raw_line.rstrip()
        if not line.strip():
            continue

        heading_match = re.match(r"^(#{1,3})\s+(.*)", line)
        if heading_match:
            level = len(heading_match.group(1))
            heading_type = f"heading_{level}"
            blocks.append(
                {
                    "object": "block",
                    "type": heading_type,
                    heading_type: {"rich_text": text_obj(heading_match.group(2))},
                }
            )
            continue

        if line.strip() == "---":
            blocks.append({"object": "block", "type": "divider", "divider": {}})
            continue

        bullet_match = re.match(r"^[-*]\s+(.*)", line.strip())
        if bullet_match:
            blocks.append(
                {
                    "object": "block",
                    "type": "bulleted_list_item",
                    "bulleted_list_item": {"rich_text": text_obj(bullet_match.group(1))},
                }
            )
            continue

        blocks.append(
            {
                "object": "block",
                "type": "paragraph",
                "paragraph": {"rich_text": text_obj(line)},
            }
        )

    return blocks


@dataclass
class NotionClient:
    token: str
    timeout: int = 20

    _session: requests.Session = field(init=False, repr=False)

    def __post_init__(self):
        self._session = requests.Session()
        self._session.headers.update(
            {
                "Authorization": f"Bearer {self.token}",
                "Notion-Version": NOTION_VERSION,
                "Content-Type": "application/json",
            }
        )

    def _request(self, method: str, path: str, **kwargs) -> Any:
        url = f"{BASE_URL}{path}"
        resp = self._session.request(method, url, timeout=self.timeout, **kwargs)
        if resp.status_code >= 300:
            try:
                body = resp.json()
            except ValueError:
                body = resp.text
            raise NotionClientError(resp.status_code, body)
        return resp.json()

    def create_page_in_database(
        self,
        database_id: str,
        title: str,
        markdown_body: str,
        title_property_name: str = "Name",
        extra_properties: Optional[dict] = None,
    ) -> dict:
        """Creates a page as a row in `database_id`, titled `title`,
        with `markdown_body` converted to page content blocks."""
        properties: dict[str, Any] = {
            title_property_name: {"title": [{"text": {"content": title}}]}
        }
        if extra_properties:
            properties.update(extra_properties)

        payload = {
            "parent": {"database_id": database_id},
            "properties": properties,
            "children": markdown_to_blocks(markdown_body),
        }
        return self._request("POST", "/pages", json=payload)

    def list_accessible_databases(self) -> list[dict]:
        """Lists every database this integration's token can actually
        see (i.e. has been explicitly shared with it). This is the
        reliable way to find a correct database_id — copying it from
        a browser URL is error-prone, especially for inline databases
        embedded in a page, where the URL points to the wrapping page
        instead of the database itself."""
        payload = {"filter": {"property": "object", "value": "database"}}
        result = self._request("POST", "/search", json=payload)
        return [
            {
                "id": item["id"],
                "title": "".join(
                    t.get("plain_text", "") for t in item.get("title", [])
                )
                or "(untitled)",
                "url": item.get("url"),
            }
            for item in result.get("results", [])
        ]

    def query_recent_pages(
        self, database_id: str, since_iso: str, title_property_name: str = "Name"
    ) -> list[dict]:
        """Returns pages in `database_id` created on/after `since_iso`
        (an ISO 8601 date string). Used by sprint-digest to surface
        recently published PRDs alongside Jira activity."""
        payload = {
            "filter": {
                "timestamp": "created_time",
                "created_time": {"on_or_after": since_iso},
            },
            "sorts": [{"timestamp": "created_time", "direction": "descending"}],
        }
        result = self._request(
            "POST", f"/databases/{database_id}/query", json=payload
        )
        pages = []
        for item in result.get("results", []):
            title_prop = item.get("properties", {}).get(title_property_name, {})
            title_parts = title_prop.get("title", [])
            title = "".join(t.get("plain_text", "") for t in title_parts) or "(untitled)"
            pages.append({"title": title, "url": item.get("url")})
        return pages
