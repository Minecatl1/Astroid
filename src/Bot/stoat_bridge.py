"""Stoat -> Astroid API bridge service.

Run this process and send POST requests from Stoat to `/stoat/message`.
The payload is forwarded into Astroid API (`/update/{endpoint}`), where Astroid
handles downstream platform fanout (Discord, Nerimity, etc.).
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlencode

import aiohttp
from aiohttp import web

import config


@dataclass(frozen=True)
class BridgeConfig:
    endpoint_token: str
    default_endpoint: str
    bridge_host: str = "0.0.0.0"
    bridge_port: int = 8080
    api_base_url: str = "https://api.astroid.cc"

    @classmethod
    def from_config(cls) -> "BridgeConfig":
        endpoint_token = str(getattr(config, "STOAT_ENDPOINT_TOKEN", "")).strip()
        default_endpoint = str(getattr(config, "STOAT_DEFAULT_ENDPOINT", "")).strip()

        if not endpoint_token:
            raise RuntimeError("STOAT_ENDPOINT_TOKEN is required.")
        if not default_endpoint:
            raise RuntimeError("STOAT_DEFAULT_ENDPOINT is required.")

        host = str(getattr(config, "STOAT_BRIDGE_HOST", "0.0.0.0")).strip() or "0.0.0.0"
        port_raw = str(getattr(config, "STOAT_BRIDGE_PORT", "8080")).strip() or "8080"
        if not port_raw.isdigit():
            raise RuntimeError("STOAT_BRIDGE_PORT must be numeric.")

        api_base_url = (
            str(getattr(config, "STOAT_API_BASE", "https://api.astroid.cc")).strip()
            or "https://api.astroid.cc"
        ).rstrip("/")

        return cls(
            endpoint_token=endpoint_token,
            default_endpoint=default_endpoint,
            bridge_host=host,
            bridge_port=int(port_raw),
            api_base_url=api_base_url,
        )


async def send_to_astroid_api(
    session: aiohttp.ClientSession,
    bridge_config: BridgeConfig,
    *,
    endpoint: str,
    author: str,
    content: str,
    author_id: str,
    author_avatar: str,
    sender_channel: str,
    attachments: str,
) -> dict[str, Any]:
    params = {
        "message_content": content,
        "message_author_name": author,
        "message_author_avatar": author_avatar,
        "message_author_id": author_id,
        "trigger": "true",
        "sender": "stoat",
        "token": bridge_config.endpoint_token,
        "sender_channel": sender_channel,
    }
    if attachments:
        params["message_attachments"] = attachments

    update_url = f"{bridge_config.api_base_url}/update/{endpoint}?{urlencode(params)}"

    async with session.post(update_url) as response:
        text = await response.text()
        if response.status >= 300:
            raise RuntimeError(f"Astroid API error {response.status}: {text}")
        try:
            return await response.json()
        except Exception:
            return {"ok": True, "raw": text}


async def handle_stoat_message(request: web.Request) -> web.Response:
    app = request.app
    bridge_config: BridgeConfig = app["bridge_config"]
    session: aiohttp.ClientSession = app["http_session"]

    try:
        body: dict[str, Any] = await request.json()
    except Exception:
        return web.json_response({"ok": False, "error": "Invalid JSON body."}, status=400)

    author = str(body.get("author", "Stoat User")).strip() or "Stoat User"
    content = str(body.get("content", "")).strip()
    if not content:
        return web.json_response({"ok": False, "error": "`content` is required."}, status=400)

    endpoint = str(body.get("endpoint", bridge_config.default_endpoint)).strip()
    if not endpoint:
        return web.json_response(
            {"ok": False, "error": "`endpoint` missing and no STOAT_DEFAULT_ENDPOINT configured."},
            status=400,
        )

    author_id = str(body.get("author_id", f"stoat:{author.lower().replace(' ', '_')}"))
    author_avatar = str(body.get("author_avatar", "https://api.astroid.cc/assets/Astroid%20PFP%20not%20found.png"))
    sender_channel = str(body.get("sender_channel", "stoat"))

    attachments_raw = body.get("attachments", [])
    attachments = ""
    if isinstance(attachments_raw, list):
        attachments = ",".join(str(item) for item in attachments_raw if str(item).strip())
    elif isinstance(attachments_raw, str):
        attachments = attachments_raw.strip()

    try:
        api_response = await send_to_astroid_api(
            session,
            bridge_config,
            endpoint=endpoint,
            author=author,
            content=content,
            author_id=author_id,
            author_avatar=author_avatar,
            sender_channel=sender_channel,
            attachments=attachments,
        )
    except Exception as exc:
        logging.exception("Stoat -> Astroid update failed")
        return web.json_response({"ok": False, "error": str(exc)}, status=502)

    return web.json_response({"ok": True, "endpoint": endpoint, "astroid": api_response})


async def health(_: web.Request) -> web.Response:
    return web.json_response({"ok": True})


async def run() -> None:
    logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(message)s")
    bridge_config = BridgeConfig.from_config()

    app = web.Application()
    app["bridge_config"] = bridge_config
    app["http_session"] = aiohttp.ClientSession()

    async def on_cleanup(app_: web.Application) -> None:
        await app_["http_session"].close()

    app.on_cleanup.append(on_cleanup)
    app.router.add_get("/health", health)
    app.router.add_post("/stoat/message", handle_stoat_message)

    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, bridge_config.bridge_host, bridge_config.bridge_port)
    await site.start()

    logging.info(
        "Stoat bridge listening on http://%s:%s and forwarding to %s",
        bridge_config.bridge_host,
        bridge_config.bridge_port,
        bridge_config.api_base_url,
    )

    while True:
        await asyncio.sleep(3600)


if __name__ == "__main__":
    asyncio.run(run())
