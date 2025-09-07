from __future__ import annotations

import asyncio
import logging
import typing as t

from aiogram.enums import ChatMemberStatus
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
)

from .models import (
    UserModel,
)
from .repository import BaseRepository as BRepo

logger = logging.getLogger(__name__)


class UnitOfWork:
    session: AsyncSession

    user: BRepo[UserModel]

    def __init__(self, session_factory: async_sessionmaker) -> None:
        self.session_factory = session_factory

    async def __aenter__(self) -> UnitOfWork:
        self.session = self.session_factory()
        self.user = BRepo(UserModel, self.session)

        return self

    async def __aexit__(
        self,
        exc_type: t.Optional[type[BaseException]],
        exc: t.Optional[BaseException],
        tb: t.Optional[t.Any],
    ) -> None:
        if exc_type:
            await self.rollback()
        else:
            await self.commit()
        await self.session.close()

        if exc:
            logger.error(f"Unit of work error: {exc}")
            raise exc.with_traceback(tb)

    async def commit(self) -> None:
        await self.session.commit()

    async def rollback(self) -> None:
        await self.session.rollback()

    async def get_stats_summary(self) -> dict[str, t.Any]:
        stmt_users_total = select(func.count()).select_from(UserModel)
        stmt_users_active = (
            select(func.count())
            .select_from(UserModel)
            .where(UserModel.state == ChatMemberStatus.MEMBER)
        )
        (
            users_total_res,
            users_active_res,
        ) = await asyncio.gather(
            self.session.execute(stmt_users_total),
            self.session.execute(stmt_users_active),
        )

        users_total = int(users_total_res.scalar() or 0)
        users_active = int(users_active_res.scalar() or 0)
        users_inactive = max(users_total - users_active, 0)

        return {
            "users_total": users_total,
            "users_active": users_active,
            "users_inactive": users_inactive,
        }
