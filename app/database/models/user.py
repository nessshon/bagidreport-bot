from __future__ import annotations

import typing as t
from datetime import datetime

from aiogram.enums import ChatMemberStatus
from aiogram.utils.link import create_tg_link
from aiogram.utils.markdown import hlink
from sqlalchemy import BigInteger, String, Boolean, DateTime
from sqlalchemy.orm import Mapped, mapped_column

from ._base import BaseModel


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

    message_thread_id: Mapped[t.Optional[int]] = mapped_column(
        BigInteger, nullable=True
    )
    is_banned: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )

    @property
    def mention(self) -> str:
        if self.username is not None:
            return f"@{self.username}"
        link = create_tg_link("user", id=self.user_id)
        return hlink(title=self.full_name, url=link)

    @property
    def topic_name(self) -> str:
        return (f"@{self.username}" if self.username else self.full_name) or str(
            self.user_id
        )

    @property
    def sender(self) -> str:
        if self.username is not None:
            return f"{self.username}.t.me"
        return f"tg.{self.full_name}"
