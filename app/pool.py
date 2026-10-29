from __future__ import annotations

import asyncio
import hashlib
import logging
import time
from collections import deque
from dataclasses import dataclass, field
from typing import Any

from telethon import TelegramClient, events
from telethon.network.connection.tcpmtproxy import ConnectionTcpMTProxyRandomizedIntermediate
from telethon.sessions import SQLiteSession

from app.config import Settings
from app.converters import callback_to_bot_api, message_to_bot_api
from app.files import FileRegistry

logger = logging.getLogger(__name__)


@dataclass
class BotRuntime:
    token: str
    token_key: str
    client: TelegramClient
    ready: bool = False
    username: str | None = None
    updates: deque[dict[str, Any]] = field(default_factory=deque)
    update_seq: int = 0
    lock: asyncio.Lock = field(default_factory=asyncio.Lock)
    files: FileRegistry | None = None


class BotPool:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._bots: dict[str, BotRuntime] = {}
        self._locks: dict[str, asyncio.Lock] = {}

    def _token_key(self, token: str) -> str:
        return hashlib.sha256(token.encode()).hexdigest()[:16]

    async def get(self, token: str) -> BotRuntime:
        if token not in self.settings.allowed_tokens:
            raise PermissionError("token not allowed")
        if token in self._bots and self._bots[token].ready:
            return self._bots[token]
        lock = self._locks.setdefault(token, asyncio.Lock())
        async with lock:
            if token in self._bots and self._bots[token].ready:
                return self._bots[token]
            return await self._start(token)

    async def _start(self, token: str) -> BotRuntime:
        settings = self.settings
        token_key = self._token_key(token)
        session_path = settings.data_dir / "sessions" / f"{token_key}.session"
        session_path.parent.mkdir(parents=True, exist_ok=True)
        files = FileRegistry(settings.data_dir / "files")
        proxy = (settings.mtproxy_host, settings.mtproxy_port, settings.mtproxy_secret)
        logger.info(
            "Starting Telethon bot token_key=%s via MTProxy %s:%s",
            token_key,
            settings.mtproxy_host,
            settings.mtproxy_port,
        )
        client = TelegramClient(
            SQLiteSession(str(session_path)),
            settings.api_id,
            settings.api_hash,
            connection=ConnectionTcpMTProxyRandomizedIntermediate,
            proxy=proxy,
            connection_retries=10,
            retry_delay=2,
            auto_reconnect=True,
        )
        await client.start(bot_token=token)
        me = await client.get_me()
        runtime = BotRuntime(
            token=token,
            token_key=token_key,
            client=client,
            ready=True,
            username=me.username or None,
            files=files,
        )
        self._bots[token] = runtime

        async def on_new_message(event: events.NewMessage.Event) -> None:
            if not event.message or event.out:
                return
            try:
                message = await message_to_bot_api(event, files)
                runtime.update_seq += 1
                runtime.updates.append(
                    {"update_id": runtime.update_seq, "message": message}
                )
                while len(runtime.updates) > 5000:
                    runtime.updates.popleft()
            except Exception:
                logger.exception("failed to enqueue message update")

        async def on_callback(event: events.CallbackQuery.Event) -> None:
            try:
                query = await callback_to_bot_api(event)
                runtime.update_seq += 1
                runtime.updates.append(
                    {"update_id": runtime.update_seq, "callback_query": query}
                )
                while len(runtime.updates) > 5000:
                    runtime.updates.popleft()
            except Exception:
                logger.exception("failed to enqueue callback update")

        client.add_event_handler(on_new_message, events.NewMessage(incoming=True))
        client.add_event_handler(on_callback, events.CallbackQuery())
        logger.info("Bot ready @%s id=%s token_key=%s", runtime.username, me.id, token_key)
        return runtime

    async def get_updates(
        self,
        token: str,
        *,
        offset: int | None = None,
        timeout: int = 0,
        allowed_updates: list[str] | None = None,
    ) -> list[dict[str, Any]]:
        runtime = await self.get(token)
        timeout = max(0, min(int(timeout or 0), 50))
        deadline = time.monotonic() + timeout
        allowed = set(allowed_updates or [])

        def match(upd: dict[str, Any]) -> bool:
            if not allowed:
                return True
            if "message" in upd and "message" in allowed:
                return True
            if "callback_query" in upd and "callback_query" in allowed:
                return True
            return False

        while True:
            # Clients may keep a huge offset from real Bot API; our ids start at 1.
            if offset is not None and offset > runtime.update_seq + 1:
                offset = None
            if offset is not None:
                while runtime.updates and runtime.updates[0]["update_id"] < offset:
                    runtime.updates.popleft()

            batch = [u for u in runtime.updates if match(u)][:100]
            if batch:
                return batch
            if time.monotonic() >= deadline:
                return []
            await asyncio.sleep(0.25)

    async def close(self) -> None:
        for runtime in list(self._bots.values()):
            try:
                await runtime.client.disconnect()
            except Exception:
                pass
        self._bots.clear()
