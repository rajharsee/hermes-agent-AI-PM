# Case Study: Building a Self-Improving PM Agent on Hermes

**Problem statement:** Fork an open-source agent framework (Hermes or OpenClaw) and ship a working Product Manager AI Agent — not a demo, a genuinely functioning tool integrated with real PM systems of record.

---

## Why Hermes over OpenClaw

Both are legitimate open-source agent frameworks, but the decision came down to three factors specific to this use case:

- **Architectural fit.** Hermes's core differentiator is a closed learning loop — it creates and refines skills from experience rather than starting from the same baseline every task. A PM agent's whole value proposition is *getting smarter about your specific product and workflows over time*, which is exactly what Hermes's architecture is built around, not a bolt-on.
- **Stack alignment.** Hermes is Python-native, matching the rest of my existing tooling (FastAPI resume customizer, funded-companies agent), which meant I could reuse patterns instead of context-switching languages.
- **Stability and security posture.** OpenClaw's larger ecosystem came with a documented track record of rapid, sometimes-breaking releases and a non-trivial rate of malicious skills in its community marketplace. For a tool meant to hold real API credentials and touch real product data, I weighted stability and a clean security history over ecosystem size.

## What was built

Two connector/skill pairs, each following the same architecture: a thin, dependency-light API client (the "connector," reusable and dumb) plus an Agent Skill (`SKILL.md` + scripts + references, following the open `agentskills.io` standard) that encodes the actual PM judgment.

```
pm-agent-skills/
├── jira-connector/        Jira Cloud REST client (API-token auth)
├── backlog-triage/        Deterministic scoring skill: info gaps,
│                          duplicates, staleness — dry-run by default
├── notion-connector/      Notion API client (page creation, MD→blocks)
└── prd-generator/         LLM-drafted PRDs, published to Notion
```

A deliberate architectural split runs through both skills: **backlog-triage is deterministic** (a Python script owns the scoring logic — cheap, fast, 100% reproducible), while **prd-generator is generative** (the agent itself drafts the PRD; the script's only job is the mechanical Notion publish step). Conflating these — trying to have a script "write" a PRD, or having the LLM freelance a scoring rubric — would have made both pieces worse. Keeping that boundary explicit is a small decision, but it's the kind of thing that separates a working tool from a fragile one.

Both skills default to safe behavior: `backlog-triage` runs dry-run unless explicitly told to apply changes; `prd-generator` shows a draft and waits for confirmation before publishing anything.

---

## Debugging story #1: the Jira pagination migration

**Symptom:** `backlog-triage`, tested and passing against synthetic offline data, threw a `400 Invalid request payload` the moment it hit the real Jira sandbox.

**Diagnosis process, not just the fix:**
- First signal worth noting: it was a `400`, not a `401`. That ruled out credentials/auth immediately and pointed at the request shape itself — a small but useful discipline (read the status code before touching the payload).
- The error body Jira returned was generic ("Invalid request payload. Refer to the REST API documentation"), so I had to research rather than guess. Turned out Atlassian had migrated `/rest/api/3/search/jql` away from the classic `startAt`/`isLast` pagination model entirely, replacing it with `nextPageToken` — and the old parameters aren't just ignored, they trigger a validation error.
- Fixed the client to build pagination around `nextPageToken`, re-ran against the real 25-issue sandbox backlog, and got a correct, fully paginated result.

**Why this is a better interview story than "I forked Hermes":** it's a live API contract change, the kind of thing that breaks production integrations in the wild (there's an active Atlassian community thread of teams hitting the exact same migration issue). Diagnosing it required reading the error precisely, not pattern-matching to a familiar fix.

## Debugging story #2: the Notion database-vs-page ID mixup

**Symptom:** `prd-generator`'s publish step failed with `400: Provided database_id ... is a page, not a database. Use the pages API instead, or pass the ID of the database itself.`

**Diagnosis process:**
- The mistake was a genuinely common one: Notion's UI makes it easy to copy a *page's* URL when a database is embedded inline inside that page, rather than the database object's own ID. The error message was actually specific enough to name the exact problem — a good example of why you read the full error text before reacting.
- Rather than re-guess at a URL a second time, I built a small diagnostic method (`list_accessible_databases`) that asks the Notion API directly, via the integration's own token, which databases it can actually see. This turned an error-prone manual process (copy URL, parse ID, hope) into a reliable one (ask the source of truth).
- That diagnostic immediately surfaced the *real* root cause underneath the ID confusion: the target database hadn't been shared with the integration at all — a second, independent failure mode that would have kept the tool broken even with a correct ID.
- Fixed both: created a purpose-built "PRD Tracker" database, shared it explicitly with the integration, re-ran the diagnostic to get a verified-correct ID (not URL-guessed), and the publish succeeded.

**The generalizable lesson:** when the same class of problem (a bad ID from a UI) is likely to recur, it's worth building a small tool that removes the manual step entirely, rather than just fixing the one instance and moving on.

---

## Engineering practices this demonstrates

- **Staged validation over mocking.** Both skills were tested offline against synthetic data modeled on real records *before* touching live systems — and the offline test caught a real bug (duplicate-detection threshold too strict) before it ever reached production data.
- **Explicit architectural decisions, documented in place.** The choice to pin an older Notion API version, the deterministic-vs-generative split between the two skills, the dry-run-by-default safety posture — all documented as comments and `references/` files at the point of decision, not left implicit.
- **Read the error before reacting to it.** Both bugs were solved by taking the specific error text seriously (`400` vs `401`; "is a page, not a database") rather than guessing broadly at possible causes.
- **Turn a one-off fix into a reusable tool when the failure mode is likely to recur.** The `list_accessible_databases` diagnostic is the clearest example — it converts "hope the URL is right" into "ask the API what's actually true."

## Current state

- Hermes Agent forked and running locally (macOS, Python 3.11 via `uv`).
- `backlog-triage` live against a real 25-issue Jira sandbox backlog (AI Lingo Product / `KAN`), correctly flagging incomplete issues, duplicates, and staleness.
- `prd-generator` live end-to-end: drafted a PRD for an AI Lingo feature (friends leaderboard) inside a Hermes chat session and published it directly into a dedicated Notion database via the API.
- Progress committed to the fork's `main` branch.

## One-line summary for a resume/LinkedIn

> Forked Hermes Agent and built a working PM copilot integrating Jira and Notion — debugged a live Jira API pagination migration and a Notion permissions/ID resolution issue along the way, both fixed and verified against real data.
