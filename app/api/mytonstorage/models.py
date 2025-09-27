import typing as t

from pydantic import BaseModel


class Report(BaseModel):
    bag_id: str
    reason: str
    sender: str
    comment: str
    created_at: int


class Reports(BaseModel):
    reports: t.List[Report]


class AddReportPayload(BaseModel):
    bag_id: str
    reason: str
    sender: str
    comment: str
