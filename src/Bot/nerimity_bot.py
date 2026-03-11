import asyncio
import json
from pathlib import Path
from urllib.parse import urlencode

import aiohttp
import config
import nerimity


API_BASE = "https://api.astroid.cc"
STATUS_URL = "https://status.astroid.cc/monitor/iamup/nerimity"
STATE_FILE = Path(getattr(config, "NERIMITY_BRIDGE_STATE_FILE", "nerimity_bridge_state.json"))


client = nerimity.Client(
    token=config.NERIMITY_TOKEN,
    prefix=config.COMMAND_PREFIX,
)


def _require(value: str, name: str) -> str:
    value = value.strip()
    if not value:
        raise RuntimeError(f"{name} is required.")
    return value


NERIMITY_ENDPOINT = _require(str(getattr(config, "NERIMITY_ENDPOINT", "")), "NERIMITY_ENDPOINT")
NERIMITY_ENDPOINT_TOKEN = _require(
    str(getattr(config, "NERIMITY_ENDPOINT_TOKEN", "")), "NERIMITY_ENDPOINT_TOKEN"
)


def load_state() -> dict:
    if not STATE_FILE.exists():
        return {"monitored_channels": [], "webhook_routes": {}}
    try:
        return json.loads(STATE_FILE.read_text())
    except Exception:
        return {"monitored_channels": [], "webhook_routes": {}}


def save_state(state: dict) -> None:
    STATE_FILE.write_text(json.dumps(state, indent=2, sort_keys=True))


def normalize_channel_id(channel_id: str) -> str:
    return str(channel_id).strip()


def add_monitored_channel(channel_id: str) -> bool:
    state = load_state()
    channel_id = normalize_channel_id(channel_id)
    channels = state.setdefault("monitored_channels", [])
    if channel_id in channels:
        return False
    channels.append(channel_id)
    save_state(state)
    return True


def remove_monitored_channel(channel_id: str) -> bool:
    state = load_state()
    channel_id = normalize_channel_id(channel_id)
    channels = state.setdefault("monitored_channels", [])
    if channel_id not in channels:
        return False
    channels.remove(channel_id)
    save_state(state)
    return True


def is_monitored_channel(channel_id: str) -> bool:
    state = load_state()
    return normalize_channel_id(channel_id) in state.setdefault("monitored_channels", [])


def list_monitored_channels() -> list[str]:
    state = load_state()
    return state.setdefault("monitored_channels", [])


def add_webhook_route(channel_id: str, webhook_url: str) -> bool:
    state = load_state()
    channel_id = normalize_channel_id(channel_id)
    webhook_url = webhook_url.strip()
    routes = state.setdefault("webhook_routes", {})
    current = routes.setdefault(channel_id, [])
    if webhook_url in current:
        return False
    current.append(webhook_url)
    save_state(state)
    return True


def remove_webhook_route(channel_id: str, webhook_url: str | None = None) -> bool:
    state = load_state()
    channel_id = normalize_channel_id(channel_id)
    routes = state.setdefault("webhook_routes", {})
    if channel_id not in routes:
        return False

    if webhook_url:
        webhook_url = webhook_url.strip()
        if webhook_url not in routes[channel_id]:
            return False
        routes[channel_id].remove(webhook_url)
        if not routes[channel_id]:
            routes.pop(channel_id, None)
    else:
        routes.pop(channel_id, None)

    save_state(state)
    return True


def get_webhook_routes(channel_id: str) -> list[str]:
    state = load_state()
    return state.setdefault("webhook_routes", {}).get(normalize_channel_id(channel_id), [])


async def send_to_astroid(message: nerimity.Message) -> None:
    params = {
        "message_author_id": str(message.author.id),
        "message_author_name": message.author.username,
        "message_author_avatar": f"https://cdn.nerimity.com/{message.author.avatar}",
        "message_content": message.content or "",
        "sender": "nerimity",
        "sender_channel": str(message.channel_id),
        "trigger": "true",
        "token": NERIMITY_ENDPOINT_TOKEN,
    }

    if message.attachments:
        attachments = [f"https://cdn.nerimity.com/{item.path}" for item in message.attachments]
        params["message_attachments"] = ",".join(attachments)

    update_url = f"{API_BASE}/update/{NERIMITY_ENDPOINT}?{urlencode(params)}"

    async with aiohttp.ClientSession() as session:
        async with session.post(update_url) as resp:
            if resp.status >= 300:
                detail = await resp.text()
                print(f"Failed to forward message ({resp.status}): {detail}")


async def send_to_webhooks(message: nerimity.Message) -> None:
    routes = get_webhook_routes(str(message.channel_id))
    if not routes:
        return

    content = message.content or ""
    if message.attachments:
        urls = [f"https://cdn.nerimity.com/{item.path}" for item in message.attachments]
        content = (content + "\n" if content else "") + "\n".join(urls)

    payload = {
        "username": f"{message.author.username} (Nerimity)",
        "avatar_url": f"https://cdn.nerimity.com/{message.author.avatar}",
        "content": content or "[empty message]",
    }

    async with aiohttp.ClientSession() as session:
        for webhook_url in routes:
            try:
                async with session.post(webhook_url, json=payload) as resp:
                    if resp.status >= 300:
                        detail = await resp.text()
                        print(f"Webhook forward failed ({resp.status}): {detail}")
            except Exception as exc:
                print(f"Webhook forward error: {exc}")


async def send_iamup() -> None:
    async with aiohttp.ClientSession() as session:
        async with session.post(STATUS_URL) as resp:
            if resp.status == 200:
                print("Sent up status.")
            else:
                print(f"Could not send up status. ({resp.status})")


async def iamup_loop() -> None:
    while True:
        asyncio.create_task(send_iamup())
        await asyncio.sleep(40)


@client.command(name="monitor-add")
async def monitor_add(ctx: nerimity.Context, channel_id: str = ""):
    channel_id = channel_id.strip() or str(ctx.channel.id)
    added = add_monitored_channel(channel_id)
    if added:
        await ctx.respond(f"✅ Monitoring enabled for channel `{channel_id}`")
    else:
        await ctx.respond(f"ℹ️ Channel `{channel_id}` is already monitored")


@client.command(name="monitor-remove")
async def monitor_remove(ctx: nerimity.Context, channel_id: str = ""):
    channel_id = channel_id.strip() or str(ctx.channel.id)
    removed = remove_monitored_channel(channel_id)
    if removed:
        await ctx.respond(f"✅ Monitoring disabled for channel `{channel_id}`")
    else:
        await ctx.respond(f"ℹ️ Channel `{channel_id}` was not monitored")


@client.command(name="monitor-list")
async def monitor_list(ctx: nerimity.Context):
    channels = list_monitored_channels()
    if not channels:
        await ctx.respond("No monitored channels configured.")
        return
    await ctx.respond("Monitored channels:\n" + "\n".join(f"- `{item}`" for item in channels))


@client.command(name="webhook-add")
async def webhook_add(ctx: nerimity.Context, webhook_url: str):
    if not webhook_url.startswith("http"):
        await ctx.respond("Provide a valid webhook URL.")
        return
    channel_id = str(ctx.channel.id)
    added = add_webhook_route(channel_id, webhook_url)
    if added:
        await ctx.respond(f"✅ Added webhook route for channel `{channel_id}`")
    else:
        await ctx.respond("ℹ️ Webhook route already exists for this channel")


@client.command(name="webhook-remove")
async def webhook_remove(ctx: nerimity.Context, webhook_url: str = ""):
    channel_id = str(ctx.channel.id)
    removed = remove_webhook_route(channel_id, webhook_url or None)
    if removed:
        await ctx.respond(f"✅ Removed webhook route(s) for channel `{channel_id}`")
    else:
        await ctx.respond("ℹ️ No matching webhook route found")


@client.command(name="webhook-list")
async def webhook_list(ctx: nerimity.Context):
    channel_id = str(ctx.channel.id)
    routes = get_webhook_routes(channel_id)
    if not routes:
        await ctx.respond("No webhook routes set for this channel.")
        return
    await ctx.respond("Webhook routes:\n" + "\n".join(f"- {url}" for url in routes))


@client.listen("on_message_create")
async def on_message_created(payload: dict) -> None:
    message = nerimity.Message.deserialize(payload["message"])

    if message.author.id == client.account.id:
        return

    if message.content.startswith("a!") or message.content.startswith("gc!"):
        return

    if not is_monitored_channel(str(message.channel_id)):
        return

    await send_to_astroid(message)
    await send_to_webhooks(message)


@client.listen("on_ready")
async def on_ready(_: dict) -> None:
    print(f"Logged in as {client.account.username}#{client.account.tag}")
    print(f"State file: {STATE_FILE.resolve()}")
    asyncio.create_task(iamup_loop())


client.run()
