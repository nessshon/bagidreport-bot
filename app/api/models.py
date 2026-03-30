import typing as t

from pydantic import BaseModel, RootModel


class AddReportPayload(BaseModel):
    bag_id: str
    reason: str
    sender: str
    comment: str


class Ban(BaseModel):
    bag_id: str
    admin: str
    reason: str
    comment: str


class BanResponse(BaseModel):
    ban: t.Optional[Ban] = None


class UpdateBanItem(BaseModel):
    bag_id: str
    admin: str
    reason: str
    comment: str
    status: bool


class UpdateBansPayload(RootModel[t.List[UpdateBanItem]]):
    pass
