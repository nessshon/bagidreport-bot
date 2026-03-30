from __future__ import annotations

import logging
import typing as t

from aiogram.enums import ChatMemberStatus
from sqlalchemy import select, func, case
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from .models import UserModel
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
            logger.error(f"Unit of work error: {exc}")
        else:
            await self.commit()
        await self.session.close()

    async def commit(self) -> None:
        await self.session.commit()

    async def rollback(self) -> None:
        await self.session.rollback()

    async def get_stats_summary(self) -> dict[str, t.Any]:
        stmt = select(
            func.count().label("total"),
            func.count(
                case(
                    (UserModel.state == ChatMemberStatus.MEMBER.value, 1),
                )
            ).label("active"),
            func.count(
                case(
                    (UserModel.is_banned == True, 1),
                )
            ).label("banned"),
        ).select_from(UserModel)
        result = await self.session.execute(stmt)
        row = result.one()
        return {
            "users_total": int(row.total or 0),
            "users_active": int(row.active or 0),
            "users_inactive": max(int(row.total or 0) - int(row.active or 0), 0),
            "users_banned": int(row.banned or 0),
        }
