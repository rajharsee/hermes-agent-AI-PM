# Scoring Rubric

This is the detailed version of the logic implemented in
`scripts/triage.py`. Read this when tuning thresholds or explaining
*why* an issue was flagged a particular way.

## 1. Info completeness → `needs_info`

An issue is flagged `needs_info` if either:

- Its title (summary) is 4 words or fewer **and** it has no
  description at all, or
- Its description is fewer than 15 words total.

Rationale: a short title alone isn't a problem ("Fix login bug" is
fine if the description has repro steps). It's the *combination* of a
short title and no elaboration that signals someone filed a
placeholder and moved on.

**Explicitly not checked (v0.1):** presence of a formal "Acceptance
Criteria" section. Many good tickets don't use that exact heading.
Future version: look for either an AC heading or a markdown checklist
(`- [ ]`) as a stronger-quality signal, without penalizing issues that
just have solid prose instead.

## 2. Duplicate detection → surfaced, never auto-merged

Uses `difflib.SequenceMatcher` on lowercased issue summaries within
the same JQL result set. Threshold: 0.72 similarity ratio.

This is intentionally crude — it's a **recall-favoring** first pass
(catch anything plausible) rather than a precision-favoring one. It
will produce some false positives (e.g. "Fix login bug" vs. "Fix
signup bug" might trip it). That's fine: the skill never auto-merges;
it only ever presents pairs for a human to judge.

**Known gap:** this only compares summaries. A future version should
also factor in description similarity and issue type (a Story and a
Bug with similar titles are less likely to be true duplicates than
two Stories).

## 3. Staleness → `stale`

Computed as `max(days since 'updated' field, days since last comment)`.

Buckets:
- **0–6 days**: fine, not mentioned in report
- **7–13 days ("watch")**: noted in the issue's reason list but does
  not change its overall category unless it's also `needs_info`
- **14–29 days ("stale")**: flagged as `stale`
- **30+ days ("needs a decision")**: flagged as `stale`, worded more
  urgently — these are candidates for the PM to actively close,
  deprioritize, or refresh rather than let sit indefinitely

**Sandbox-only mechanism:** during development, real Jira issues are
all freshly created (so `updated` is always "today"). The script also
looks for a comment matching `Simulated last-touched: N days ago` and
takes the max of that and the real timestamp. This lets staleness
logic be tested immediately in a new sandbox. **Remove or ignore this
check once real backlog age exists** — it's a testing scaffold, not
production logic.
