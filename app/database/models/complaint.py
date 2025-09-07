from __future__ import annotations

import typing as t
from datetime import datetime

from sqlalchemy import (
    Integer,
    String,
    Text,
    DateTime,
    ForeignKey,
    CheckConstraint,
    Index,
    BigInteger,
)
from sqlalchemy.orm import (
    Mapped,
    mapped_column,
    relationship,
)

from ._base import BaseModel
from ..enums import ComplaintStatus

if t.TYPE_CHECKING:
    from .user import UserModel
    from .vote import VoteModel


class ComplaintModel(BaseModel):
    __tablename__ = "complaints"

    id: Mapped[int] = mapped_column(
        primary_key=True,
        autoincrement=True,
    )
    status: Mapped[int] = mapped_column(
        Integer,
        default=ComplaintStatus.PENDING,
        index=True,
    )

    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"),
        index=True,
        nullable=False,
    )

    message_thread_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    message_id: Mapped[int] = mapped_column(BigInteger, nullable=False)

    bag_id: Mapped[str] = mapped_column(String(128), index=True)
    problem: Mapped[str] = mapped_column(Text, nullable=False)

    approved_by: Mapped[t.Optional[int]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    approved_at: Mapped[t.Optional[datetime]] = mapped_column(DateTime)

    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    updated_at: Mapped[t.Optional[datetime]] = mapped_column(DateTime)

    user: Mapped["UserModel"] = relationship(
        "UserModel",
        foreign_keys=[user_id],
        back_populates="complaints",
    )

    votes: Mapped[t.List["VoteModel"]] = relationship(
        back_populates="complaint",
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        CheckConstraint("status IN (0,1,2)", name="ck_complaint_status_int"),
        Index("ix_complaints_status_created", "status", "created_at"),
    )

    @property
    def moderators_approved(self) -> t.List["VoteModel"]:
        return [v for v in self.votes if v.decision == 1]

    @property
    def moderators_rejected(self) -> t.List["VoteModel"]:
        return [v for v in self.votes if v.decision == 0]

    @property
    def ready_for_admin(self) -> bool:
        return len({v.moderator_id for v in self.votes if v.decision == 1}) >= 2
