---
name: backlog-triage
description: >-
  Reviews a Jira backlog and flags issues that need attention: missing
  descriptions/acceptance criteria, likely duplicates, and stale issues
  with no recent activity. Use when the user asks to "triage the
  backlog", "review the Jira backlog", "clean up the backlog", "find
  duplicate tickets", or "what needs attention in Jira".
license: MIT
metadata:
  author: raj
  version: "0.1"
compatibility: Requires Python 3.10+, a Jira Cloud site, and an API
  token with read/comment/label permissions on the target project.
allowed-tools: Bash Read
---

# Backlog Triage

## When to use this skill

The user wants a pass over a Jira backlog to find issues that are
under-specified, duplicated, or going stale — the kind of triage a PM
does manually before sprint planning, but doesn't have time to do
thoroughly every week.

## What this skill does NOT do

- It does not delete or close issues.
- It does not reassign issues or change sprints.
- By default it runs in **dry-run mode**: it reports what it *would*
  flag, but does not write anything to Jira, unless the user
  explicitly confirms they want comments/labels applied.

This default exists because the first few runs of any new triage
logic will be wrong in some way, and it's much cheaper to be wrong in
a report than wrong in 25 issues' comment threads.

## Instructions

1. Determine the JQL scope. If the user names a project (e.g. "triage
   KAN"), use `project = KEY AND statusCategory != Done`. If they
   don't specify, ask which project/board before running.

2. Run the triage script:

   ```bash
   python scripts/triage.py \
     --site "$JIRA_SITE_URL" \
     --email "$JIRA_EMAIL" \
     --jql "project = KAN AND statusCategory != Done" \
     --apply=false
   ```

   Required env/config (see `references/config.md` for setup):
   `JIRA_SITE_URL`, `JIRA_EMAIL`, `JIRA_API_TOKEN`.

3. The script prints a Markdown triage report to stdout, grouped into:
   - **Needs info** — no description, or description under ~15 words
   - **Possible duplicates** — pairs with high title/description
     similarity
   - **Stale** — no update/comment in 14+ days, bucketed by severity
   - **Looks fine** — everything else, shown only as a count

4. Present this report to the user. Do not silently apply any labels
   or comments — summarize the findings and ask which of the flagged
   issues (if any) they want acted on.

5. Only if the user confirms, re-run with `--apply=true`, which adds
   a `needs-triage` label and a short explanatory comment to each
   flagged issue (see `references/scoring.md` for exactly what
   triggers each label).

## Scoring logic (summary)

See `references/scoring.md` for the full rubric. In short:

- **Info completeness**: description length, presence of acceptance
  criteria markers ("Acceptance Criteria", checklist syntax), and
  whether the summary alone is under 4 words (a strong "vague title"
  signal).
- **Duplicate detection**: token-overlap similarity between issue
  summaries within the same project; anything above threshold is
  surfaced as a *possible* duplicate for human judgment, never
  auto-merged.
- **Staleness**: days since `updated` (or the most recent comment,
  whichever is later). Buckets: 7-14d "watch", 14-30d "stale",
  30d+ "needs a decision" (close, deprioritize, or refresh).

## Examples

- User: "Triage the KAN backlog" → run with `project = KAN AND
  statusCategory != Done`, dry-run, present report.
- User: "Apply labels to the stale ones" → re-run with
  `--apply=true --category=stale` only.
- User: "What's duplicated in the backlog?" → run full triage but
  present only the duplicates section.
