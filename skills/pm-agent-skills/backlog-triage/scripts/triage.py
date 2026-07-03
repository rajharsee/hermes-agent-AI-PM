#!/usr/bin/env python3
"""
backlog-triage / scripts/triage.py
===================================
Fetches a Jira backlog via JQL, scores each issue for info-completeness,
duplication risk, and staleness, and either prints a report (default)
or applies labels/comments (--apply=true).

This script deliberately does its own scoring in plain Python rather
than delegating the whole judgment to an LLM call — the scoring rubric
is simple and cheap to run directly, which makes it fast, free, and
100% reproducible. If you later want the *language* in the triage
comments to be more natural/PM-voiced, that's a good place to layer
in an LLM call on top of this script's structured output — but the
flagging logic itself should stay deterministic.

Usage:
    python triage.py --site https://x.atlassian.net --email me@x.com \
        --jql "project = KAN AND statusCategory != Done" --apply=false
"""

from __future__ import annotations

import argparse
import os
import re
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from difflib import SequenceMatcher
from pathlib import Path

# Import the connector. Assumes jira-connector/ sits alongside
# backlog-triage/ in the same skills root — adjust sys.path if your
# fork lays things out differently.
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "jira-connector"))
from client import JiraClient  # noqa: E402

STALE_WATCH_DAYS = 7
STALE_DAYS = 14
STALE_URGENT_DAYS = 30
DUPLICATE_SIMILARITY_THRESHOLD = 0.6
VAGUE_TITLE_MAX_WORDS = 4
MIN_DESCRIPTION_WORDS = 15

SIMULATED_STALE_RE = re.compile(
    r"Simulated last-touched:\s*(\d+)\s*days? ago", re.IGNORECASE
)


@dataclass
class TriageFinding:
    key: str
    summary: str
    reasons: list[str] = field(default_factory=list)
    category: str = "ok"  # needs_info | stale | ok
    stale_days: int | None = None


def word_count(text: str | None) -> int:
    if not text:
        return 0
    return len(text.split())


def extract_description_text(description_field) -> str:
    """Jira v3 descriptions are ADF (dict), not plain strings. Flatten
    to plain text for length checks."""
    if description_field is None:
        return ""
    if isinstance(description_field, str):
        return description_field
    # Minimal ADF text extraction
    texts: list[str] = []

    def walk(node):
        if isinstance(node, dict):
            if node.get("type") == "text":
                texts.append(node.get("text", ""))
            for child in node.get("content", []) or []:
                walk(child)
        elif isinstance(node, list):
            for item in node:
                walk(item)

    walk(description_field)
    return " ".join(texts)


def days_since(iso_ts: str) -> int:
    dt = datetime.fromisoformat(iso_ts.replace("Z", "+00:00"))
    return (datetime.now(timezone.utc) - dt).days


def simulated_stale_days(issue: dict) -> int | None:
    """Look for our own '[SIMULATED DATA]' comment marker, used only
    for sandbox testing before real backlog age exists. Real usage
    should rely purely on `updated`/comment timestamps."""
    comments = (issue.get("fields", {}).get("comment") or {}).get("comments", [])
    best = None
    for c in comments:
        body = c.get("body", "")
        if isinstance(body, dict):
            body = extract_description_text(body)
        match = SIMULATED_STALE_RE.search(str(body))
        if match:
            days = int(match.group(1))
            best = days if best is None else max(best, days)
    return best


def score_issue(issue: dict) -> TriageFinding:
    fields = issue["fields"]
    key = issue["key"]
    summary = fields.get("summary", "")
    finding = TriageFinding(key=key, summary=summary)

    # -- info completeness --------------------------------------------
    desc_text = extract_description_text(fields.get("description"))
    if word_count(summary) <= VAGUE_TITLE_MAX_WORDS and word_count(desc_text) == 0:
        finding.reasons.append(
            f"Vague title (\u2264{VAGUE_TITLE_MAX_WORDS} words) with no description at all"
        )
        finding.category = "needs_info"
    elif word_count(desc_text) < MIN_DESCRIPTION_WORDS:
        finding.reasons.append(
            f"Description is only {word_count(desc_text)} words "
            f"(threshold: {MIN_DESCRIPTION_WORDS})"
        )
        finding.category = "needs_info"

    # -- staleness -----------------------------------------------------
    sim_days = simulated_stale_days(issue)
    real_days = days_since(fields["updated"])
    stale_days = max(sim_days or 0, real_days)
    finding.stale_days = stale_days

    if stale_days >= STALE_URGENT_DAYS:
        finding.reasons.append(
            f"No activity in {stale_days}+ days \u2014 needs a decision (close/refresh/deprioritize)"
        )
        finding.category = "stale" if finding.category == "ok" else finding.category
    elif stale_days >= STALE_DAYS:
        finding.reasons.append(f"Stale: no activity in {stale_days} days")
        finding.category = "stale" if finding.category == "ok" else finding.category
    elif stale_days >= STALE_WATCH_DAYS:
        finding.reasons.append(f"Watch: {stale_days} days since last activity")

    return finding


def find_duplicates(issues: list[dict]) -> list[tuple[str, str, float]]:
    pairs = []
    for i in range(len(issues)):
        for j in range(i + 1, len(issues)):
            a, b = issues[i], issues[j]
            sim = SequenceMatcher(
                None,
                a["fields"]["summary"].lower(),
                b["fields"]["summary"].lower(),
            ).ratio()
            if sim >= DUPLICATE_SIMILARITY_THRESHOLD:
                pairs.append((a["key"], b["key"], round(sim, 2)))
    return pairs


def render_report(
    findings: list[TriageFinding], duplicates: list[tuple[str, str, float]]
) -> str:
    needs_info = [f for f in findings if f.category == "needs_info"]
    stale = [f for f in findings if f.category == "stale"]
    ok = [f for f in findings if f.category == "ok"]

    lines = ["# Backlog Triage Report", ""]

    lines.append(f"## Needs info ({len(needs_info)})")
    for f in needs_info:
        lines.append(f"- **{f.key}** {f.summary} \u2014 {'; '.join(f.reasons)}")
    if not needs_info:
        lines.append("- none")
    lines.append("")

    lines.append(f"## Possible duplicates ({len(duplicates)})")
    for a, b, sim in duplicates:
        lines.append(f"- **{a}** \u2194 **{b}** (title similarity: {sim})")
    if not duplicates:
        lines.append("- none")
    lines.append("")

    lines.append(f"## Stale ({len(stale)})")
    for f in sorted(stale, key=lambda x: -(x.stale_days or 0)):
        lines.append(f"- **{f.key}** {f.summary} \u2014 {'; '.join(f.reasons)}")
    if not stale:
        lines.append("- none")
    lines.append("")

    lines.append(f"## Looks fine ({len(ok)})")
    lines.append(f"- {len(ok)} issues, no action needed")

    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--site", default=os.environ.get("JIRA_SITE_URL"))
    ap.add_argument("--email", default=os.environ.get("JIRA_EMAIL"))
    ap.add_argument("--token", default=os.environ.get("JIRA_API_TOKEN"))
    ap.add_argument("--jql", required=True)
    ap.add_argument("--apply", default="false")
    ap.add_argument(
        "--category",
        default="all",
        choices=["all", "needs_info", "stale"],
        help="Restrict --apply to one category of finding.",
    )
    args = ap.parse_args()

    if not (args.site and args.email and args.token):
        print(
            "Missing Jira credentials. Set JIRA_SITE_URL, JIRA_EMAIL, "
            "JIRA_API_TOKEN or pass --site/--email/--token.",
            file=sys.stderr,
        )
        sys.exit(1)

    apply_changes = args.apply.lower() == "true"

    jira = JiraClient(site_url=args.site, email=args.email, api_token=args.token)
    issues = jira.search_issues(args.jql)

    findings = [score_issue(i) for i in issues]
    duplicates = find_duplicates(issues)

    print(render_report(findings, duplicates))

    if apply_changes:
        applied = 0
        for f in findings:
            if args.category != "all" and f.category != args.category:
                continue
            if f.category == "ok":
                continue
            jira.add_labels(f.key, ["needs-triage"])
            jira.add_comment(
                f.key,
                "[backlog-triage] Flagged: " + "; ".join(f.reasons),
            )
            applied += 1
        print(f"\n---\nApplied labels/comments to {applied} issue(s).", file=sys.stderr)


if __name__ == "__main__":
    main()
