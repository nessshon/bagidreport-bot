from __future__ import annotations

import typing as t
from datetime import datetime

from aiogram.enums import ChatMemberStatus
from sqlalchemy import (
    BigInteger,
    String,
    Boolean,
    DateTime,
    ForeignKey,
    UniqueConstraint,
)
from sqlalchemy.orm import (
    Mapped,
    mapped_column,
    relationship,
)

from ._base import BaseModel

if t.TYPE_CHECKING:
    from .vote import VoteModel
    from .complaint import ComplaintModel


class UserModel(BaseModel):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(
        primary_key=True,
        autoincrement=True,
    )
    state: Mapped[str] = mapped_column(
        String(64),
        default=ChatMemberStatus.MEMBER.value,
    )
    user_id: Mapped[int] = mapped_column(
        BigInteger,
        unique=True,
        nullable=False,
        index=True,
    )

    username: Mapped[t.Optional[str]] = mapped_column(String)
    full_name: Mapped[t.Optional[str]] = mapped_column(String)
    language_code: Mapped[t.Optional[str]] = mapped_column(String(8))

    is_banned: Mapped[bool] = mapped_column(Boolean, default=False)
    banned_at: Mapped[t.Optional[datetime]] = mapped_column(DateTime)
    banned_by: Mapped[t.Optional[int]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )

    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)

    topic: Mapped["UserTopicModel"] = relationship(
        "UserTopicModel",
        back_populates="user",
        uselist=False,
        cascade="all, delete-orphan",
    )
    complaints: Mapped[t.List["ComplaintModel"]] = relationship(
        back_populates="user",
        foreign_keys="ComplaintModel.user_id",
    )
    moderator_votes: Mapped[t.List["VoteModel"]] = relationship(
        "VoteModel",
        back_populates="moderator",
        foreign_keys="VoteModel.moderator_id",
        viewonly=True,
    )
    approved_complaints: Mapped[t.List["ComplaintModel"]] = relationship(
        "ComplaintModel",
        foreign_keys="ComplaintModel.approved_by",
        viewonly=True,
    )


class UserTopicModel(BaseModel):
    __tablename__ = "users.topics"

    id: Mapped[int] = mapped_column(
        primary_key=True,
        autoincrement=True,
    )
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        unique=True,
        index=True,
    )
    message_thread_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)

    user: Mapped[UserModel] = relationship(back_populates="topic")

    __table_args__ = (UniqueConstraint("user_id", name="ux_topics_user"),)
