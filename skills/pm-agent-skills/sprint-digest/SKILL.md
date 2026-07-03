---
name: sprint-digest
description: >-
  Generates a summary of recent Jira activity (resolved, new, and
  in-progress issues) plus recently published PRDs, and posts it as a
  formatted digest to Slack. Use when the user asks to "post the
  sprint digest", "send a weekly summary to Slack", "generate a
  status update", or when running as a scheduled cron job for an
  unattended recurring digest.
license: MIT
metadata:
  author: raj
  version: "0.1"
compatibility: Requires Python 3.10+, a Slack bot token with
  chat:write scope, and (for full functionality) Jira and Notion
  credentials as already configured for backlog-triage and
  prd-generator.
allowed-tools: Bash Read
---

# Sprint Digest

## When to use this skill

The user wants a recurring or on-demand summary of what's happened
recently across Jira (and optionally Notion PRDs), delivered to
Slack. This is the skill most suited to running unattended via
`hermes cron` — see `references/cron-setup.md`.

## Architecture note: fully stateless by design

Hermes cron jobs run in a fresh session every time, with no memory of
previous runs. This skill's script is written to match that
constraint exactly: every run takes an explicit lookback window
(`--days`) and re-derives everything it needs from Jira/Notion
directly — it does not depend on the agent remembering anything from
a prior conversation. This is what makes it safe to schedule
unattended.

## Instructions

1. Determine scope: which Jira project (JQL), how many days to look
   back (default 7), which Slack channel, and optionally which Notion
   PRD database to check for recent additions. If the user doesn't
   specify, use whatever defaults are in `~/.hermes/.env`
   (`DIGEST_JQL`, `DIGEST_SLACK_CHANNEL`) rather than asking — this
   skill is meant to run unattended, so it should have sensible
   defaults rather than always requiring interactive input.

2. Run the digest script:

   ```bash
   python scripts/generate_digest.py \
     --jql "$DIGEST_JQL" \
     --days 7 \
     --slack-channel "$DIGEST_SLACK_CHANNEL" \
     --notion-database-id "$PRD_DATABASE_ID" \
     --apply=false
   ```

3. **In an interactive session**, show the digest content first
   (dry-run), let the user confirm, then re-run with `--apply=true`
   to actually post to Slack — same pattern as `backlog-triage` and
   `prd-generator`.

4. **In a cron session** (no human to confirm), it's appropriate to
   run directly with `--apply=true` — that's the whole point of
   scheduling it. Set this up deliberately (see
   `references/cron-setup.md`), don't default to it in interactive use.

## What the digest includes

- Issues resolved in the lookback window (count + list)
- Issues newly created in the lookback window (count + list)
- Issues still in progress, unchanged (flagged if suspiciously stale —
  reuses the same staleness logic philosophy as `backlog-triage`,
  though not the same code, since this only needs a simple check, not
  full scoring)
- Recently published PRDs from the Notion PRD database, if
  `--notion-database-id` is provided (optional — the script degrades
  gracefully and omits this section if not given)

## What this skill does NOT do

- Does not editorialize or add commentary beyond the factual summary
  — no "great progress this week!" filler. A digest that always
  sounds positive stops being useful signal.
- Does not post if there's nothing to report — an empty digest is
  worse than no message; the script should say so explicitly rather
  than post noise.
