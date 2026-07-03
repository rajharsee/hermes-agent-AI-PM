# Setup

## 1. Create a Notion integration

Go to `https://www.notion.so/my-integrations` → New integration.
Name it something like "PM Agent". Copy the generated token
(starts with `secret_` or `ntn_`).

## 2. Share your target database with the integration

This is the single most common failure mode — Notion integrations see
**nothing** by default, even with a valid token. In Notion, open the
database you want PRDs to land in → `•••` menu → **Connections** →
add your integration by name.

## 3. Get the database ID

Open the database as a full page in Notion, copy the URL. The ID is
the 32-character string right before the `?v=` query parameter:

```
https://www.notion.so/yourworkspace/1234567890abcdef1234567890abcdef?v=...
                                     ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
                                     this is the database_id
```

## 4. Environment variables

Add to `~/.hermes/.env`:

```
NOTION_API_KEY=secret_xxx
PRD_DATABASE_ID=1234567890abcdef1234567890abcdef
```

## 5. Confirm the database has a title property

The script writes the PRD title into whichever property you pass as
`--title-property` (default: `Name`). Check your database's title
column name — if it's not literally called "Name", pass
`--title-property "Your Column Name"` or update the default in
`SKILL.md`'s example command.

## 6. Known limitation — pinned API version

`notion-connector/client.py` pins `Notion-Version: 2022-06-28`
deliberately, using the older `database_id`-based page creation flow.
Notion's newer API versions (2025-09-03+) restructured databases into
"data sources" and expect `data_source_id` instead. If Notion
eventually removes support for the pinned version, `create_page_in_database`
is the one place to update — see the comment at the top of `client.py`.
