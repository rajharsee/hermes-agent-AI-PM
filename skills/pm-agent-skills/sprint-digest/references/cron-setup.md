# Wiring this to Hermes cron

This is the skill designed to run unattended. Two things matter for
that to actually work reliably, based on how Hermes cron behaves:

## 1. The gateway daemon must be running

Cron jobs don't fire unless Hermes's gateway is up and ticking (every
60 seconds). Start it (and keep it running — consider `pm2` or a
systemd unit if you want this to survive terminal closes/reboots):

```bash
hermes gateway
```

## 2. Cron sessions are stateless — the prompt must be self-contained

Every cron run starts a brand-new agent session with zero memory of
previous runs or interactive conversations. The job's prompt has to
say everything the agent needs, as if talking to a stranger. This
skill's script already handles that correctly (explicit `--days`
lookback, no reliance on "since last time"), so the cron prompt itself
can stay simple:

```bash
hermes cron add \
  --name "weekly-sprint-digest" \
  --schedule "0 9 * * 1" \
  --prompt "Run the sprint-digest skill. Use a 7-day lookback and post to Slack." \
  --skill sprint-digest
```

That schedule (`0 9 * * 1`) fires every Monday at 9am. Adjust to your
actual cadence.

## 3. Verify before trusting it

Don't just check that the job appears in `hermes cron list` — that
only proves it's *scheduled*, not that it *works*. Trigger it manually
once and confirm the message actually lands in Slack:

```bash
hermes cron run weekly-sprint-digest
```

Then check `hermes cron list` again for status, and look at the actual
Slack channel — a green scheduler state is not proof of a working
job, the delivered message is.

## 4. If it fails silently for a while

Check logs:
```bash
hermes cron logs weekly-sprint-digest --last 5
```

Consider adding failure notification so you find out immediately
rather than noticing a week of silence:
```bash
hermes cron edit weekly-sprint-digest --on-failure-notify slack
```
