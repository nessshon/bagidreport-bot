import asyncio
import typing as t
from contextlib import suppress

from aiogram import BaseMiddleware
from aiogram.dispatcher.flags import get_flag
from aiogram.types import TelegramObject, User, CallbackQuery, Message
from cachetools import TTLCache

from app.bot.utils.i18n import Localizer

THROTTLING_DEFAULT_TTL: float = 0.5


class ThrottlingMiddleware(BaseMiddleware):

    def __init__(
        self,
        default_ttl: float = THROTTLING_DEFAULT_TTL,
    ) -> None:
        self.default_ttl = float(default_ttl)
        self._caches: dict[int, TTLCache[int, None]] = {}

    @staticmethod
    def _normalize_ttl(ttl: float) -> int:
        if ttl < 0:
            ttl = 0.0
        return int(round(ttl * 1000))

    def _get_cache(self, ttl: float) -> TTLCache[int, None]:
        key = self._normalize_ttl(ttl)
        cache = self._caches.get(key)
        if cache is None:
            cache = TTLCache(maxsize=10_000, ttl=ttl)
            self._caches[key] = cache
        return cache

    @staticmethod
    def _parse_rate_flag(value: t.Any, default_ttl: float) -> float:
        if isinstance(value, (int, float)):
            return float(value)
        return default_ttl

    @staticmethod
    async def _send_feedback(
        event: TelegramObject,
        localizer: Localizer,
        ttl: float,
    ) -> None:
        if ttl.is_integer():
            ttl = int(ttl)
        text = localizer("messages.throttled", ttl=ttl)

        if isinstance(event, Message):
            try:
                msg = await event.reply(text)
            except (Exception,):
                return

            async def _del():
                await asyncio.sleep(3)
                with suppress(Exception):
                    await msg.delete()

            asyncio.create_task(_del())
            return

        if isinstance(event, CallbackQuery):
            with suppress(Exception):
                await event.answer(text, show_alert=True)

    async def __call__(
        self,
        handler: t.Callable[
            [TelegramObject, t.Dict[str, t.Any]],
            t.Awaitable[t.Any],
        ],
        event: TelegramObject,
        data: t.Dict[str, t.Any],
    ) -> t.Optional[t.Any]:
        user: t.Optional[User] = data.get("event_from_user")
        if user is not None:
            localizer = data.get("localizer")

            rate_flag = get_flag(data, "rate_limit")
            ttl = self._parse_rate_flag(rate_flag, self.default_ttl)
            cache = self._get_cache(ttl)
            if user.id in cache:
                await self._send_feedback(event, localizer, ttl)
                return None
            cache[user.id] = None

        return await handler(event, data)
