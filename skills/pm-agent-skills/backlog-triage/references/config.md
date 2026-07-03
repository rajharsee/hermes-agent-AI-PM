# Setup

## 1. Jira API token

Generate one at: `https://id.atlassian.com/manage-profile/security/api-tokens`

Scope it to the account that has access to your target site
(e.g. `altbeing.atlassian.net`).

## 2. Environment variables

Add to `~/.hermes/.env` (per Hermes's existing secret-management
convention — never commit these):

```
JIRA_SITE_URL=https://altbeing.atlassian.net
JIRA_EMAIL=rajrkblr@gmail.com
JIRA_API_TOKEN=<token>
```

## 3. Install dependencies

```bash
pip install requests
```

(That's the only external dependency — `jira-connector/client.py`
deliberately avoids pulling in a full Jira SDK.)

## 4. Directory layout expected

```
your-hermes-fork/
├── jira-connector/
│   ├── __init__.py
│   └── client.py
└── skills/                      # or wherever Hermes loads skills from
    └── backlog-triage/
        ├── SKILL.md
        ├── scripts/
        │   └── triage.py
        └── references/
            ├── scoring.md
            └── config.md
```

`triage.py` locates `jira-connector` via a relative path two levels
up from itself (`backlog-triage/scripts/../../jira-connector`) —
adjust the `sys.path.insert` line in `triage.py` if your fork's
layout differs.

## 5. First run — always dry-run first

```bash
python skills/backlog-triage/scripts/triage.py \
  --jql "project = KAN AND statusCategory != Done" \
  --apply=false
```

Read the report. Only re-run with `--apply=true` once you trust the
output on your specific backlog — thresholds in `scoring.md` are
starting points, not settled values.
