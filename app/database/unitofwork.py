from __future__ import annotations

import logging
import typing as t

from aiogram.enums import ChatMemberStatus
from sqlalchemy import select, func, case
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from sqlalchemy.orm import joinedload

from .models import UserModel, UserTopicModel, ComplaintModel, VoteModel
from .repository import BaseRepository as BRepo

logger = logging.getLogger(__name__)


class UnitOfWork:
    session: AsyncSession

    user: BRepo[UserModel]
    user_topic: BRepo[UserTopicModel]
    complaint: BRepo[ComplaintModel]
    vote: BRepo[VoteModel]

    def __init__(self, session_factory: async_sessionmaker) -> None:
        self.session_factory = session_factory

    async def __aenter__(self) -> UnitOfWork:
        self.session = self.session_factory()

        self.user = BRepo(UserModel, self.session)
        self.user_topic = BRepo(UserTopicModel, self.session)
        self.complaint = BRepo(ComplaintModel, self.session)
        self.vote = BRepo(VoteModel, self.session)

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
                    (UserModel.state == ChatMemberStatus.MEMBER, 1),
                )
            ).label("active"),
        ).select_from(UserModel)

        result = await self.session.execute(stmt)
        row = result.one()

        users_total = int(row.total or 0)
        users_active = int(row.active or 0)

        return {
            "users_total": users_total,
            "users_active": users_active,
            "users_inactive": max(users_total - users_active, 0),
        }

    async def create_complaint(self, complaint: ComplaintModel, max_retries: int = 3) -> ComplaintModel:
        from .models.complaint import generate_public_id

        for attempt in range(max_retries):
            nested = await self.session.begin_nested()
            try:
                self.session.add(complaint)
                await nested.commit()
                return complaint
            except IntegrityError:
                await nested.rollback()
                if attempt < max_retries - 1:
                    await self.session.expire_all()
                    complaint.public_id = generate_public_id()
                    continue
                raise

    async def get_complaint_by_message_id(
        self,
        message_id: int,
    ) -> t.Optional[ComplaintModel]:
        stmt = (
            select(ComplaintModel)
            .options(
                joinedload(ComplaintModel.user),
                joinedload(ComplaintModel.votes).joinedload(VoteModel.moderator),
            )
            .where(ComplaintModel.message_id == message_id)
        )
        res = await self.session.execute(stmt)
        return res.scalar_one_or_none()

    async def get_complaint_votes(self, complaint_id: int) -> t.List[VoteModel]:
        stmt = (
            select(VoteModel)
            .options(joinedload(VoteModel.moderator))
            .where(VoteModel.complaint_id == complaint_id)
        )
        res = await self.session.execute(stmt)
        return list(res.scalars().all())
