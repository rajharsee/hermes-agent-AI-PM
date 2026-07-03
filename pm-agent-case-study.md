# Case Study: Building a Self-Improving PM Agent on Hermes

**Problem statement:** Fork an open-source agent framework (Hermes or OpenClaw) and ship a working Product Manager AI Agent — not a demo, a genuinely functioning tool integrated with real PM systems of record.

---

## Why Hermes over OpenClaw

Both are legitimate open-source agent frameworks, but the decision came down to three factors specific to this use case:

- **Architectural fit.** Hermes's core differentiator is a closed learning loop — it creates and refines skills from experience rather than starting from the same baseline every task. A PM agent's whole value proposition is *getting smarter about your specific product and workflows over time*, which is exactly what Hermes's architecture is built around, not a bolt-on.
- **Stack alignment.** Hermes is Python-native, matching the rest of my existing tooling (FastAPI resume customizer, funded-companies agent), which meant I could reuse patterns instead of context-switching languages.
- **Stability and security posture.** OpenClaw's larger ecosystem came with a documented track record of rapid, sometimes-breaking releases and a non-trivial rate of malicious skills in its community marketplace. For a tool meant to hold real API credentials and touch real product data, I weighted stability and a clean security history over ecosystem size.

## What was built

Three connector/skill pairs, each following the same architecture: a thin, dependency-light API client (the "connector," reusable and dumb) plus an Agent Skill (`SKILL.md` + scripts + references, following the open `agentskills.io` standard) that encodes the actual PM judgment.

```
pm-agent-skills/
├── jira-connector/        Jira Cloud REST client (API-token auth)
├── backlog-triage/        Deterministic scoring skill: info gaps,
│                          duplicates, staleness — dry-run by default
├── notion-connector/      Notion API client (page creation, MD→blocks,
│                          database queries)
├── prd-generator/         LLM-drafted PRDs, published to Notion
├── slack-connector/       Slack Web API client (chat.postMessage)
└── sprint-digest/         Pulls Jira + Notion activity, posts a
                           formatted digest to Slack — designed to run
                           unattended via Hermes cron
```

A deliberate architectural split runs through the skills: **backlog-triage and sprint-digest are deterministic** (a Python script owns the logic — cheap, fast, 100% reproducible, and safe to run unattended on a schedule), while **prd-generator is generative** (the agent itself drafts the PRD; the script's only job is the mechanical Notion publish step). Conflating these — trying to have a script "write" a PRD, or having the LLM freelance a scoring rubric — would have made both pieces worse. Keeping that boundary explicit is a small decision, but it's the kind of thing that separates a working tool from a fragile one.

All three skills default to safe behavior: `backlog-triage` and `sprint-digest` run dry-run unless explicitly told to apply changes; `prd-generator` shows a draft and waits for confirmation before publishing anything.

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

## Debugging story #3: the silently mangled JQL string

**Symptom:** `sprint-digest` failed with `400: Expecting a field name but got 'AND'. You must surround 'AND' in quotation marks to use it as a field name.` — a JQL syntax error, but the JQL string being sent (`project = KAN AND ...`) looked completely normal.

**Diagnosis process:**
- The actual bug was two steps upstream of where the error surfaced. `~/.hermes/.env` had `DIGEST_JQL=project = KAN` — unquoted, with spaces in the value.
- `source`ing a `.env` file runs it as literal bash, not a simple key=value parser. Bash read `DIGEST_JQL=project`, stopped there, and then tried to execute `= KAN` as a separate command — hence a `command not found: =` error that appeared *before* the real failure and looked unrelated to it.
- Net effect: `$DIGEST_JQL` was set to just `project`, not the full query. By the time that truncated value reached Jira with `AND ...` clauses appended in the script, the JQL was structurally invalid — but the error Jira returned pointed at the *symptom* (malformed JQL), not the *cause* (an unquoted shell variable three layers upstream).
- Fixed by quoting the value (`DIGEST_JQL="project = KAN"`), confirmed with a clean reload, and audited the rest of `.env` for the same pattern.

**Why this one matters as much as the API bugs:** it's not a code bug at all — the Python and the API calls were correct the whole time. It's a configuration/environment bug, which are arguably more common in real deployments than API contract changes, and much easier to misdiagnose because the error you see is often several steps removed from the actual cause. The habit that mattered here: noticing an *earlier*, seemingly unrelated shell error (`command not found: =`) instead of only looking at the final traceback.

## A bug that never reached production: the shared-filename import collision

Worth including because it shows the testing discipline, not just the fixes. While building `sprint-digest` (which needed all three connectors — Jira, Notion, Slack — in one script), a naive `sys.path` import of three files that all happened to be named `client.py` silently collided: Python cached the first-imported `client` module under that name, and the second and third imports silently reused the wrong module instead of failing loudly. Caught this in offline testing before it ever reached a real run, and fixed it with explicit `importlib` module loading instead of relying on `sys.path` order. The lesson: the same offline-testing habit that caught the duplicate-detection threshold issue in `backlog-triage` caught a second, more subtle bug here — worth keeping as a standing practice, not a one-off.

---

## Engineering practices this demonstrates

- **Staged validation over mocking.** Every skill was tested offline against synthetic data modeled on real records *before* touching live systems — and offline testing caught two real bugs (a duplicate-detection threshold too strict, and a module import collision) before either reached production data or a real run.
- **Explicit architectural decisions, documented in place.** The choice to pin an older Notion API version, the deterministic-vs-generative split between skills, the dry-run-by-default safety posture — all documented as comments and `references/` files at the point of decision, not left implicit.
- **Read the error before reacting to it — including errors that look unrelated.** All three live-system bugs were solved by taking the specific error text seriously rather than guessing broadly. The `.env` bug specifically required noticing an *earlier*, seemingly irrelevant shell error instead of only looking at the final traceback several layers downstream.
- **Turn a one-off fix into a reusable tool when the failure mode is likely to recur.** The `list_accessible_databases` diagnostic is the clearest example — it converts "hope the URL is right" into "ask the API what's actually true."
- **Configuration bugs are real bugs, not embarrassing footnotes.** The `.env` quoting issue wasn't a code defect, but it broke a real run just as thoroughly as an API contract change would have — worth treating environment setup with the same rigor as application logic, not as an afterthought.

## Current state

- Hermes Agent forked and running locally (macOS, Python 3.11 via `uv`).
- `backlog-triage` live against a real 25-issue Jira sandbox backlog (AI Lingo Product / `KAN`), correctly flagging incomplete issues, duplicates, and staleness.
- `prd-generator` live end-to-end: drafted a PRD for an AI Lingo feature (friends leaderboard) inside a Hermes chat session and published it directly into a dedicated Notion database via the API.
- `sprint-digest` live end-to-end: pulls recent Jira activity and recently published Notion PRDs, formats a digest, and posts it to a real Slack channel via a bot token — the piece designed to eventually run unattended on a schedule via Hermes cron.
- Progress committed to the fork's `main` branch.

## One-line summary for a resume/LinkedIn

> Forked Hermes Agent and built a working PM copilot integrating Jira, Notion, and Slack — debugged a live Jira API pagination migration, a Notion permissions/ID resolution issue, and a shell config bug along the way, each diagnosed from real symptoms and verified against real data.
