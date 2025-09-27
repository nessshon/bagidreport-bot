from pyapiq import AsyncClientAPI, AsyncAPINamespace, async_endpoint
from pyapiq.types import HTTPMethod

from .models import Reports, AddReportPayload
from ...config import MYTONSTORAGE_REPORTS_KEY


class BansNamespace(AsyncAPINamespace):
    namespace = "bans"


class ReportsNamespace(AsyncAPINamespace):
    namespace = "reports"
    headers = {"Authorization": MYTONSTORAGE_REPORTS_KEY}

    @async_endpoint(HTTPMethod.POST, path="/", return_as=bool, headers=headers)
    async def add(self, report: AddReportPayload) -> bool:
        pass

    @async_endpoint(HTTPMethod.GET, path="/", return_as=Reports, headers=headers)
    async def get_all(self, limit: int = 100, offset: int = 0) -> Reports:
        pass

    @async_endpoint(
        HTTPMethod.GET, path="/{bag_id}", return_as=Reports, headers=headers
    )
    async def get_by_id(self, bag_id: str) -> Reports:
        pass


class MytonstorageClient(AsyncClientAPI):
    base_url = "https://mytonstorage.org/api"
    version = "v1"
    rps = 10

    @property
    def bans(self) -> BansNamespace:
        return BansNamespace(self)

    @property
    def reports(self) -> ReportsNamespace:
        return ReportsNamespace(self)
