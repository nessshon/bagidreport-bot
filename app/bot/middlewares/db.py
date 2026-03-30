import typing as t
from datetime import datetime

from aiogram import BaseMiddleware
from aiogram.enums import ChatType
from aiogram.types import TelegramObject, User, Chat, Update

from ...config import TIMEZONE, ADMIN_IDS_SET
from ...context import Context
from ...database.models import UserModel
from ...database.unitofwork import UnitOfWork


class DbSessionMiddleware(BaseMiddleware):

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
        chat: t.Optional[Chat] = data.get("event_chat")
        ctx: t.Optional[Context] = data.get("ctx")
        uow = UnitOfWork(ctx.db.session_factory)

        async with uow:
            user_model: t.Optional[UserModel] = None
            if user and not user.is_bot:
                existing = await uow.user.get(user_id=user.id)
                if existing is None:
                    user_model = UserModel(
                        user_id=user.id,
                        full_name=user.full_name,
                        username=user.username,
                        created_at=datetime.now(TIMEZONE),
                    )
                    user_model = await uow.user.create(user_model)
                else:
                    existing.full_name = user.full_name
                    existing.username = user.username
                    user_model = existing
                    await uow.session.flush()

                if (
                    user_model
                    and user_model.is_banned
                    and user_model.user_id not in ADMIN_IDS_SET
                    and chat
                    and chat.type == ChatType.PRIVATE
                    and not self._is_my_chat_member(data)
                ):
                    return None

            data["user_model"] = user_model
            data["uow"] = uow
            return await handler(event, data)

    @staticmethod
    def _is_my_chat_member(data: t.Dict[str, t.Any]) -> bool:
        update: t.Optional[Update] = data.get("event_update")
        return update is not None and update.my_chat_member is not None
