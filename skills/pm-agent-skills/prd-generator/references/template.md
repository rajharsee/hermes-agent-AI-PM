# PRD Template — Annotated

This is the structure `SKILL.md` instructs the agent to follow. Kept
as a separate reference file per skill best practice (progressive
disclosure) rather than bloating the main SKILL.md body.

```markdown
# <Feature Name>

## Problem
<1-2 paragraphs>
```
State the problem, not the solution. If this section already
describes a leaderboard/button/screen, it's not a problem statement —
rewrite it as "users currently can't X, which causes Y."

```markdown
## Goals
- <specific, ideally measurable>
```
Avoid vague goals like "improve engagement." Prefer "increase D7
retention among users who complete lesson 1" — specific enough that
someone could later say "we hit this" or "we didn't."

```markdown
## Non-Goals
- <explicitly out of scope>
```
This section exists to prevent scope creep and to give engineering a
clear boundary. If nothing is out of scope, that's usually a sign the
feature itself is under-scoped — say so rather than leaving this
section empty.

```markdown
## User Stories
- As a <user>, I want <capability>, so that <outcome>
```
Keep these to the 2-4 stories that actually matter for v1. A PRD with
15 user stories is usually a roadmap wearing a PRD's clothes.

```markdown
## Success Metrics
- <how you'll know this worked>
```
Prefer metrics that are already instrumented or clearly instrumentable.
A success metric nobody can actually measure isn't one.

```markdown
## Open Questions
- <anything assumed rather than confirmed>
```
This is not a junk drawer. Every assumption the agent made while
drafting (because the user's original request was underspecified)
belongs here explicitly, so the human reviewing the PRD can see
exactly what was inferred vs. stated.
