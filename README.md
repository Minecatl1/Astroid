# Astroid Bot Sources + Stoat API Bridge

This repository contains the upstream Astroid bot files from:
`https://github.com/astroid-app/v2/tree/main/src/Bot`

It also includes a Stoat bridge service that patches Stoat messages into the
**Astroid API** so Astroid handles downstream bridging to Discord/Nerimity.

## Included bot files

- `src/Bot/discord.py` (upstream)
- `src/Bot/nerimity_bot.py` (upstream)
- `src/Bot/stoat_bridge.py` (Stoat -> Astroid API bridge)
- `src/Bot/config.py` and `src/Bot/.config.py` (config template)

## Install

```bash
pip install -r requirements.txt
```

## Stoat bridge configuration (`src/Bot/config.py`)

- `STOAT_ENDPOINT_TOKEN`: Astroid endpoint token used for `/update/{endpoint}`
- `STOAT_DEFAULT_ENDPOINT`: fallback endpoint ID for Stoat messages
- `STOAT_API_BASE`: Astroid API base (default `https://api.astroid.cc`)
- `STOAT_BRIDGE_HOST`: bind host (default `0.0.0.0`)
- `STOAT_BRIDGE_PORT`: bind port (default `8080`)

## Run Stoat bridge

```bash
python src/Bot/stoat_bridge.py
```

## Stoat -> bridge payload format

POST JSON to `http://<host>:<port>/stoat/message`:

```json
{
  "author": "stoat-user",
  "content": "hello from stoat",
  "endpoint": "123456789",
  "author_id": "stoat-user-42",
  "author_avatar": "https://example.com/avatar.png",
  "sender_channel": "stoat-general",
  "attachments": ["https://example.com/file1.png"]
}
```

Notes:
- `endpoint` is optional; if omitted, `STOAT_DEFAULT_ENDPOINT` is used.
- Bridge forwards into Astroid API: `POST /update/{endpoint}` with `sender=stoat` and endpoint `token`.

## Run with Docker

Build and run with Docker Compose:

```bash
docker compose up --build -d
```

This starts the container with:
- `BOT_SCRIPT=stoat_bridge.py` (default)
- `./src/Bot/config.py` mounted to `/app/config.py`
- port `8080` exposed for the bridge API

### Run a different bot script

Override `BOT_SCRIPT` to run another file copied into the image:

```bash
docker run --rm \
  -e BOT_SCRIPT=discord.py \
  -v $(pwd)/src/Bot/config.py:/app/config.py:ro \
  astroid:latest
```

## Nerimity bot configuration (endpoint-token only)

`src/Bot/nerimity_bot.py` now forwards messages using only endpoint credentials:

- `NERIMITY_TOKEN`: Nerimity bot token
- `NERIMITY_ENDPOINT`: Astroid endpoint ID to update
- `NERIMITY_ENDPOINT_TOKEN`: token for that endpoint

Notes:
- The bot uses endpoint credentials only (`NERIMITY_ENDPOINT`, `NERIMITY_ENDPOINT_TOKEN`).
- Messages are forwarded only from monitored channels.
- Webhook routes can forward messages from a Nerimity channel to other platforms (for example Discord webhook URLs).

Commands (Nerimity):
- `a!monitor-add [channel_id]` — add channel to monitored list (defaults to current channel)
- `a!monitor-remove [channel_id]` — remove channel from monitored list
- `a!monitor-list` — list monitored channels
- `a!webhook-add <webhook_url>` — add webhook route for current channel
- `a!webhook-remove [webhook_url]` — remove one route or all routes for current channel
- `a!webhook-list` — list webhook routes for current channel

Additional config:
- `NERIMITY_BRIDGE_STATE_FILE`: local JSON file for monitored channels + webhook routes

