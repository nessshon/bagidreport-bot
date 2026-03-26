from aiogram.filters import Filter
from aiogram.types import Message

from ..database.models import UserModel


class IsBannedFilter(Filter):

    async def __call__(self, message: Message, user_model: UserModel) -> bool:
        return not user_model.is_banned
