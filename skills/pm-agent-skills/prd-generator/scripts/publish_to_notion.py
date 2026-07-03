#!/usr/bin/env python3
"""
prd-generator / scripts/publish_to_notion.py
==============================================
Publishes an already-written PRD (Markdown file) as a new page in a
Notion database. This script does NOT generate any content — that's
the agent's job per SKILL.md. It only handles the mechanical publish
step, which is worth keeping in code because it's fiddly (Markdown ->
Notion block JSON) and has no judgment calls in it.

Usage:
    python publish_to_notion.py \
        --database-id <notion_database_id> \
        --title "Feature Name" \
        --markdown-file /tmp/prd_draft.md
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "notion-connector"))
from client import NotionClient  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--token", default=os.environ.get("NOTION_API_KEY"))
    ap.add_argument("--database-id", required=True)
    ap.add_argument("--title", required=True)
    ap.add_argument("--markdown-file", required=True)
    ap.add_argument(
        "--title-property",
        default="Name",
        help="Name of the title property in the target database (default: Name)",
    )
    args = ap.parse_args()

    if not args.token:
        print(
            "Missing Notion token. Set NOTION_API_KEY or pass --token.",
            file=sys.stderr,
        )
        sys.exit(1)

    md_path = Path(args.markdown_file)
    if not md_path.exists():
        print(f"Markdown file not found: {md_path}", file=sys.stderr)
        sys.exit(1)

    markdown_body = md_path.read_text()

    notion = NotionClient(token=args.token)
    result = notion.create_page_in_database(
        database_id=args.database_id,
        title=args.title,
        markdown_body=markdown_body,
        title_property_name=args.title_property,
    )

    page_url = result.get("url", "(no url returned)")
    print(f"Published: {page_url}")


if __name__ == "__main__":
    main()
