from pyapiq import AsyncClientAPI, AsyncAPINamespace, async_endpoint
from pyapiq.types import HTTPMethod

from .models import (
    AddReportPayload,
    BanResponse,
    UpdateBansPayload,
)
from ..config import (
    MYTONSTORAGE_REPORTS_KEY,
    MYTONSTORAGE_BANS_KEY,
)


class BansNamespace(AsyncAPINamespace):
    namespace = "bans"
    headers = {"Authorization": MYTONSTORAGE_BANS_KEY}

    @async_endpoint(HTTPMethod.PUT, path="/", return_as=bool, headers=headers)
    async def update(self, bans: UpdateBansPayload) -> bool:
        pass

    @async_endpoint(
        HTTPMethod.GET, path="/{bag_id}", return_as=BanResponse, headers=headers
    )
    async def get_by_id(self, bag_id: str) -> BanResponse:
        pass


class ReportsNamespace(AsyncAPINamespace):
    namespace = "reports"
    headers = {"Authorization": MYTONSTORAGE_REPORTS_KEY}

    @async_endpoint(HTTPMethod.POST, path="/", return_as=bool, headers=headers)
    async def add(self, report: AddReportPayload) -> bool:
        pass


class MytonstorageClient(AsyncClientAPI):
    base_url = "https://mytonstorage.org/api"
    version = "v1"
    max_retries = 5
    rps = 10

    @property
    def bans(self) -> BansNamespace:
        return BansNamespace(self)

    @property
    def reports(self) -> ReportsNamespace:
        return ReportsNamespace(self)
