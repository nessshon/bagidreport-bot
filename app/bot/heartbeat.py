import asyncio
import logging
import time
import typing as t

import aiohttp
from aiogram.methods import GetUpdates

from ..config import BOT_TOKEN

logger = logging.getLogger(__name__)

HEARTBEAT_INTERVAL = 60
STALE_AFTER = 120


class HeartbeatMiddleware:

    def __init__(self) -> None:
        self.last_ok: t.Optional[float] = None
        self.last_error: t.Optional[str] = None

    async def __call__(self, make_request, bot, method):
        if not isinstance(method, GetUpdates):
            return await make_request(bot, method)
        try:
            result = await make_request(bot, method)
        except Exception as e:
            self.last_error = f"{type(e).__name__}: {e}".replace(BOT_TOKEN, "***")[:200]
            raise
        self.last_ok = time.monotonic()
        self.last_error = None
        return result

    async def run(self, url: str, token: str) -> None:
        headers = {"Authorization": f"Bearer {token}"}
        timeout = aiohttp.ClientTimeout(total=10)
        async with aiohttp.ClientSession(headers=headers, timeout=timeout) as session:
            while True:
                await asyncio.sleep(HEARTBEAT_INTERVAL)
                if self.last_ok is not None and time.monotonic() - self.last_ok < STALE_AFTER:
                    params = {"success": "true"}
                else:
                    params = {
                        "success": "false",
                        "error": self.last_error or f"no successful getUpdates within {STALE_AFTER}s",
                    }
                try:
                    async with session.post(url, params=params) as resp:
                        if resp.status >= 400:
                            logger.warning("Gatus heartbeat rejected: HTTP %s", resp.status)
                except Exception as e:
                    logger.warning("Gatus heartbeat failed: %s", e)
