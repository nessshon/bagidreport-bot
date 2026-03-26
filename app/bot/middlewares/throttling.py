import asyncio
import typing as t
from contextlib import suppress

from aiogram import BaseMiddleware
from aiogram.dispatcher.flags import get_flag
from aiogram.types import TelegramObject, User, CallbackQuery, Message, Chat
from cachetools import TTLCache

from ..utils.i18n import Localizer
from ...config import GROUP_ID

THROTTLING_DEFAULT_TTL: float = 0.5
THROTTLING_GROUP_TTL: float = 1.0


def normalize_ttl(ttl: float) -> int:
    if ttl < 0:
        ttl = 0.0
    return int(round(ttl * 1000))


def parse_rate_flag(value: t.Any, default_ttl: float) -> float:
    return float(value) if isinstance(value, (int, float)) else float(default_ttl)


def get_or_create_cache(
    registry: dict[int, TTLCache[t.Hashable, t.Any]],
    ttl: float,
    maxsize: int = 10_000,
) -> TTLCache[t.Hashable, t.Any]:
    bucket = normalize_ttl(ttl)
    cache = registry.get(bucket)
    if cache is None:
        cache = TTLCache(maxsize=maxsize, ttl=ttl)
        registry[bucket] = cache
    return cache


async def send_feedback(
    event: TelegramObject | CallbackQuery,
    localizer: t.Optional[Localizer],
    ttl: float,
    text_key: str,
    auto_delete_seconds: int = 3,
) -> None:
    ttl = int(ttl) if ttl.is_integer() else ttl
    text = localizer(text_key, ttl=ttl)

    if isinstance(event, CallbackQuery):
        with suppress(Exception):
            await event.answer(text, show_alert=True)

    if isinstance(event, Message):
        try:
            msg = await event.reply(text)
        except (Exception,):
            return

        async def _del():
            await asyncio.sleep(auto_delete_seconds)
            with suppress(Exception):
                await msg.delete()

        asyncio.create_task(_del())
        return


class ThrottlingMiddleware(BaseMiddleware):

    def __init__(self, default_ttl: float = THROTTLING_DEFAULT_TTL) -> None:
        self.default_ttl = float(default_ttl)
        self._caches: dict[int, TTLCache[int, None]] = {}

    async def __call__(
        self,
        handler: t.Callable[[TelegramObject, dict], t.Awaitable[t.Any]],
        event: TelegramObject,
        data: dict,
    ) -> t.Optional[t.Any]:
        user: t.Optional[User] = data.get("event_from_user")
        if user is not None:
            localizer: t.Optional[Localizer] = data.get("localizer")
            ttl = parse_rate_flag(get_flag(data, "rate_limit"), self.default_ttl)

            cache = get_or_create_cache(self._caches, ttl)
            if user.id in cache:
                await send_feedback(
                    ttl=ttl,
                    event=event,
                    localizer=localizer,
                    text_key="messages.throttled",
                )
                return None

            cache[user.id] = None

        return await handler(event, data)


class GroupThrottlingMiddleware(BaseMiddleware):

    def __init__(self, default_ttl: float = THROTTLING_GROUP_TTL) -> None:
        self.default_ttl = float(default_ttl)
        self._caches: dict[int, TTLCache[str, int]] = {}

    async def __call__(
        self,
        handler: t.Callable[[CallbackQuery, dict], t.Awaitable[t.Any]],
        event: CallbackQuery,
        data: dict,
    ) -> t.Optional[t.Any]:
        user: t.Optional[User] = data.get("event_from_user")
        chat: t.Optional[Chat] = data.get("event_chat")

        if user is not None and not user.is_bot and chat and chat.id == GROUP_ID:
            localizer: t.Optional[Localizer] = data.get("localizer")
            ttl = parse_rate_flag(get_flag(data, "rate_limit"), self.default_ttl)

            cache = get_or_create_cache(self._caches, ttl)
            msg_id = event.message.message_id if event.message else 0
            key = f"{chat.id}:{msg_id}:{normalize_ttl(ttl)}"

            owner_id = cache.get(key)
            if owner_id is not None and owner_id != user.id:
                await send_feedback(
                    ttl=ttl,
                    event=event,
                    localizer=localizer,
                    text_key="messages.throttled_message",
                )
                return None

            cache[key] = user.id

        return await handler(event, data)
