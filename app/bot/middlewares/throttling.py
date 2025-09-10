import typing as t

from aiogram import BaseMiddleware
from aiogram.dispatcher.flags import get_flag
from aiogram.types import TelegramObject, User
from cachetools import TTLCache

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
            rate_flag = get_flag(data, "rate_limit")
            ttl = self._parse_rate_flag(rate_flag, self.default_ttl)
            cache = self._get_cache(ttl)
            if user.id in cache:
                return None
            cache[user.id] = None

        return await handler(event, data)
