from __future__ import annotations

from enum import Enum


class ComplaintStatus(int, Enum):
    PENDING = 0
    APPROVED = 1
    REJECTED = 2


class VoteDecision(int, Enum):
    APPROVE = 1
    REJECT = 0
