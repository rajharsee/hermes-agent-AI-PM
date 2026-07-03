---
name: prd-generator
description: >-
  Drafts a Product Requirements Document from a rough idea or feature
  request, following a consistent template, and can publish the
  result as a new page in a Notion database. Use when the user asks
  to "write a PRD", "draft a PRD for X", "create a product
  requirements doc", "turn this idea into a PRD", or "spec out this
  feature".
license: MIT
metadata:
  author: raj
  version: "0.1"
compatibility: Requires Python 3.10+ and a Notion integration token
  with access to the target database, if publishing is requested.
allowed-tools: Bash Read
---

# PRD Generator

## When to use this skill

The user has a rough idea, a one-line feature request, or a longer
brain dump, and wants it turned into a structured PRD — either just
shown in chat, or published as a Notion page.

## Important: this skill is mostly YOU, not a script

Unlike `backlog-triage`, PRD writing is not something to hand off to
deterministic code. **You draft the PRD content yourself**, using the
template below. The only script involved (`scripts/publish_to_notion.py`)
does the mechanical work of pushing already-written content into
Notion — it does not write anything.

## Instructions

1. **Assess how specified the idea is.** If it's a single vague
   phrase with no context ("build a leaderboard"), ask ONE clarifying
   question covering the most important gap (usually: who is this
   for, and what problem does it solve). Don't ask more than one
   question — if there are several gaps, pick reasonable assumptions
   for the rest and state them explicitly in the "Open Questions"
   section of the PRD rather than blocking on them.

2. **Draft the PRD** using exactly this structure (see
   `references/template.md` for the full annotated version):

   ```markdown
   # <Feature Name>

   ## Problem
   <1-2 paragraphs: what user/business problem this addresses, and
   why it matters now>

   ## Goals
   - <specific, ideally measurable>

   ## Non-Goals
   - <explicitly out of scope, to prevent scope creep>

   ## User Stories
   - As a <user>, I want <capability>, so that <outcome>

   ## Success Metrics
   - <how you'll know this worked>

   ## Open Questions
   - <anything assumed rather than confirmed, flagged for the user>
   ```

3. **Show the drafted PRD in chat first.** Do not publish anything
   automatically. Ask the user to confirm or request edits.

4. **Only on explicit confirmation**, publish it:

   ```bash
   python scripts/publish_to_notion.py \
     --database-id "$PRD_DATABASE_ID" \
     --title "<Feature Name>" \
     --markdown-file /tmp/prd_draft.md
   ```

   Write the confirmed PRD content to a temp file first, then call
   the script with that file path — don't try to pass long markdown
   as a shell argument.

5. Report back the Notion page URL the script returns.

## What this skill does NOT do

- Does not decide priority, timeline, or assign an owner — those are
  PM judgment calls, not something to fabricate.
- Does not overwrite an existing PRD page — it only creates new pages.
  If the user wants to update an existing PRD, that's a separate,
  not-yet-built capability (flag it rather than improvising a write
  path that could clobber existing content).

## Examples

- User: "Write a PRD for a friends leaderboard in AI Lingo" → draft
  using the template (this is specific enough to draft without
  clarifying questions — infer target user and problem from existing
  project context), show it, ask to publish.
- User: "PRD for notifications" → too vague alone; ask one clarifying
  question (e.g. "what should trigger a notification, and for which
  user segment?") before drafting.
