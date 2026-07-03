#!/usr/bin/env python3
"""
sprint-digest / scripts/generate_digest.py
=============================================
Pulls recent Jira activity (+ optionally recent Notion PRDs), formats
a digest, and posts it to Slack. Fully stateless per run — takes an
explicit lookback window rather than relying on any memory of the
previous run, which is what makes this safe to run from Hermes cron
(fresh session every time, no carryover context).
"""

from __future__ import annotations

import argparse
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import importlib.util


def _load_module(module_name: str, file_path: Path):
    """Loads a Python file as a uniquely-named module, sidestepping
    the collision that would occur from three different connectors
    all being named client.py on the same sys.path — plain `import
    client` after multiple sys.path.insert calls silently reuses
    whichever module was cached first under that name. This was
    caught by testing the import logic in isolation before shipping,
    not assumed to work."""
    spec = importlib.util.spec_from_file_location(module_name, file_path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module  # required before exec: dataclass
    # annotation resolution looks the module up in sys.modules by name.
    spec.loader.exec_module(module)
    return module


_skills_root = Path(__file__).resolve().parents[2]
_jira_mod = _load_module("jira_connector_client", _skills_root / "jira-connector" / "client.py")
_notion_mod = _load_module("notion_connector_client", _skills_root / "notion-connector" / "client.py")
_slack_mod = _load_module("slack_connector_client", _skills_root / "slack-connector" / "client.py")

JiraClient = _jira_mod.JiraClient
NotionClient = _notion_mod.NotionClient
SlackClient = _slack_mod.SlackClient
SlackClientError = _slack_mod.SlackClientError


def build_digest_text(
    days: int,
    resolved: list[dict],
    created: list[dict],
    stale_in_progress: list[dict],
    recent_prds: list[dict],
) -> tuple[str, list[dict]]:
    """Returns (fallback_text, slack_blocks)."""
    lines = [f"*Sprint Digest — last {days} days*", ""]

    lines.append(f"*Resolved ({len(resolved)})*")
    if resolved:
        for issue in resolved[:10]:
            lines.append(f"• <{issue['url']}|{issue['key']}> {issue['summary']}")
        if len(resolved) > 10:
            lines.append(f"  _...and {len(resolved) - 10} more_")
    else:
        lines.append("_none_")
    lines.append("")

    lines.append(f"*New ({len(created)})*")
    if created:
        for issue in created[:10]:
            lines.append(f"• <{issue['url']}|{issue['key']}> {issue['summary']}")
        if len(created) > 10:
            lines.append(f"  _...and {len(created) - 10} more_")
    else:
        lines.append("_none_")
    lines.append("")

    if stale_in_progress:
        lines.append(f"*In progress, no update in {days}+ days ({len(stale_in_progress)})*")
        for issue in stale_in_progress[:10]:
            lines.append(f"• <{issue['url']}|{issue['key']}> {issue['summary']}")
        lines.append("")

    if recent_prds:
        lines.append(f"*New PRDs ({len(recent_prds)})*")
        for prd in recent_prds:
            lines.append(f"• <{prd['url']}|{prd['title']}>")
        lines.append("")

    if not resolved and not created and not stale_in_progress and not recent_prds:
        lines = [f"*Sprint Digest — last {days} days*", "", "Nothing to report."]

    text = "\n".join(lines)
    blocks = [{"type": "section", "text": {"type": "mrkdwn", "text": text}}]
    return text, blocks


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--jira-site", default=os.environ.get("JIRA_SITE_URL"))
    ap.add_argument("--jira-email", default=os.environ.get("JIRA_EMAIL"))
    ap.add_argument("--jira-token", default=os.environ.get("JIRA_API_TOKEN"))
    ap.add_argument("--jql", required=True, help="Base JQL, e.g. 'project = KAN'")
    ap.add_argument("--days", type=int, default=7)
    ap.add_argument("--slack-token", default=os.environ.get("SLACK_BOT_TOKEN"))
    ap.add_argument("--slack-channel", required=True)
    ap.add_argument("--notion-token", default=os.environ.get("NOTION_API_KEY"))
    ap.add_argument("--notion-database-id", default=None)
    ap.add_argument("--apply", default="false")
    args = ap.parse_args()

    if not (args.jira_site and args.jira_email and args.jira_token):
        print("Missing Jira credentials.", file=sys.stderr)
        sys.exit(1)
    if not args.slack_token:
        print("Missing Slack credentials (SLACK_BOT_TOKEN).", file=sys.stderr)
        sys.exit(1)

    apply_changes = args.apply.lower() == "true"
    since_date = (datetime.now(timezone.utc) - timedelta(days=args.days)).strftime("%Y-%m-%d")
    since_iso = (datetime.now(timezone.utc) - timedelta(days=args.days)).isoformat()

    jira = JiraClient(site_url=args.jira_site, email=args.jira_email, api_token=args.jira_token)

    resolved_raw = jira.search_issues(
        f"{args.jql} AND statusCategory = Done AND resolved >= -{args.days}d",
        fields=["summary"],
    )
    created_raw = jira.search_issues(
        f"{args.jql} AND created >= -{args.days}d", fields=["summary"]
    )
    stale_raw = jira.search_issues(
        f"{args.jql} AND statusCategory = \"In Progress\" AND updated <= -{args.days}d",
        fields=["summary"],
    )

    def shape(raw):
        return [
            {
                "key": i["key"],
                "summary": i["fields"]["summary"],
                "url": f"{args.jira_site}/browse/{i['key']}",
            }
            for i in raw
        ]

    resolved = shape(resolved_raw)
    created = shape(created_raw)
    stale_in_progress = shape(stale_raw)

    recent_prds: list[dict] = []
    if args.notion_database_id and args.notion_token:
        notion = NotionClient(token=args.notion_token)
        recent_prds = notion.query_recent_pages(args.notion_database_id, since_date)

    text, blocks = build_digest_text(args.days, resolved, created, stale_in_progress, recent_prds)

    print(text)

    if apply_changes:
        slack = SlackClient(token=args.slack_token)
        try:
            slack.post_message(channel=args.slack_channel, text=text, blocks=blocks)
            print("\n---\nPosted to Slack.", file=sys.stderr)
        except SlackClientError as e:
            print(f"\n---\nSlack post FAILED: {e.error_code}", file=sys.stderr)
            sys.exit(1)


if __name__ == "__main__":
    main()
