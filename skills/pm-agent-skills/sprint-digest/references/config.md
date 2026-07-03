# Setup

## 1. Create a Slack app + bot token

1. Go to `https://api.slack.com/apps` → **Create New App** → From scratch
2. Name it (e.g. "PM Agent"), pick your workspace
3. Left sidebar → **OAuth & Permissions**
4. Under **Scopes → Bot Token Scopes**, add:
   - `chat:write` (required — lets the bot post messages)
   - `chat:write.public` (recommended — lets it post to public channels
     without needing to be manually invited first)
5. Scroll up, click **Install to Workspace**, authorize
6. Copy the **Bot User OAuth Token** (starts with `xoxb-`)

## 2. Get the channel ID

Slack deprecated posting by channel *name* — you need the channel
*ID*. Easiest way: open the channel in Slack, click the channel name
at the top → scroll to the bottom of the panel that opens → copy the
Channel ID (starts with `C`).

## 3. If posting to a private channel

`chat:write.public` only covers public channels. For a private
channel, invite the bot explicitly from within Slack:
```
/invite @YourBotName
```

## 4. Environment variables

Add to `~/.hermes/.env`:

```
SLACK_BOT_TOKEN=xoxb-your-token-here
DIGEST_SLACK_CHANNEL=C0123456789
DIGEST_JQL=project = KAN
```

## 5. Known gotcha this connector already handles

Slack's `chat.postMessage` returns **HTTP 200 even on failure** — the
real success/failure signal is the `"ok"` field in the JSON body.
`slack-connector/client.py` checks this explicitly and raises
`SlackClientError` with Slack's actual error code (e.g.
`not_in_channel`, `channel_not_found`, `invalid_auth`) rather than
treating a 200 as success. If you ever extend this connector, keep
that check — it's easy to accidentally lose if refactored.
