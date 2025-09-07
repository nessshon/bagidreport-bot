from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    Integer,
    DateTime,
    ForeignKey,
    UniqueConstraint,
    CheckConstraint,
    Index,
)
from sqlalchemy.orm import (
    Mapped,
    mapped_column,
    relationship,
)

from ._base import BaseModel


class VoteModel(BaseModel):
    __tablename__ = "votes"

    id: Mapped[int] = mapped_column(
        primary_key=True,
        autoincrement=True,
    )
    complaint_id: Mapped[int] = mapped_column(
        ForeignKey("complaints.id", ondelete="CASCADE"),
        index=True,
    )
    moderator_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"),
        index=True,
    )
    decision: Mapped[int] = mapped_column(Integer, nullable=False)

    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)

    complaint = relationship(
        "ComplaintModel",
        back_populates="votes",
    )
    moderator = relationship(
        "UserModel",
        foreign_keys=[moderator_id],
        back_populates="moderator_votes",
    )

    __table_args__ = (
        UniqueConstraint(
            "complaint_id", "moderator_id", name="ux_vote_once_per_moderator"
        ),
        CheckConstraint("decision IN (0,1)", name="ck_vote_decision_int"),
        Index("ix_votes_complaint_decision", "complaint_id", "decision"),
    )
