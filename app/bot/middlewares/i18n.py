from __future__ import annotations

import typing as t
from collections.abc import Awaitable, Callable

from aiogram.dispatcher.middlewares.base import BaseMiddleware
from aiogram.enums import ChatType
from aiogram.types import TelegramObject, User, Chat

from ..utils.i18n import Localizer
from ...config import (
    DEFAULT_LOCALE,
    SUPPORTED_LOCALES,
)
from ...context import Context
from ...database.models import UserModel


class I18nMiddleware(BaseMiddleware):

    async def __call__(
        self,
        handler: Callable[
            [TelegramObject, t.Dict[str, t.Any]],
            Awaitable[t.Any],
        ],
        event: TelegramObject,
        data: t.Dict[str, t.Any],
    ) -> t.Any:
        user: t.Optional[User] = data.get("event_from_user")
        chat: t.Optional[Chat] = data.get("event_chat")
        ctx: Context = data.get("ctx")

        if user is not None and not user.is_bot:
            if chat.type == ChatType.PRIVATE:
                user_model: UserModel = data.get("user_model")
                language_code = self._get_user_language_code(user, user_model)
            elif chat.type in {ChatType.GROUP, ChatType.SUPERGROUP}:
                language_code = "group"
            else:
                return await handler(event, data)

            locale_data = ctx.i18n.locales_data.get(language_code)
            if locale_data is None:
                raise ValueError(
                    f"Localization for language '{language_code}' "
                    f"not found in locales_data."
                )

            data["localizer"] = Localizer(locale_data)

        return await handler(event, data)

    @staticmethod
    def _get_user_language_code(user: User, user_model: UserModel) -> str:
        if user_model.language_code in SUPPORTED_LOCALES:
            language_code = user_model.language_code
        elif user.language_code in SUPPORTED_LOCALES:
            language_code = user.language_code
        else:
            language_code = DEFAULT_LOCALE
        return language_code
