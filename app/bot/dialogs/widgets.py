import typing as t

from aiogram_dialog import DialogManager
from aiogram_dialog.widgets.common import WhenCondition
from aiogram_dialog.widgets.text import Text

from ..utils.i18n import Localizer
from ...context import get_context

ITEMS_PER_PAGE = 10


class AdminText(Text):

    def __init__(self, key: str, when: WhenCondition = None):
        super().__init__(when=when)
        self.key = key

    async def _render_text(
        self,
        data: dict[str, t.Any],
        manager: DialogManager,
    ) -> str:
        ctx = get_context()
        loc = Localizer(ctx.i18n.locales_data["admin"])
        key = self.key.format_map(data) if "{" in self.key else self.key
        return loc(key, **data)


class AdminError(Text):

    def __init__(self, error_field: str = "error_key"):
        super().__init__(when=None)
        self.error_field = error_field

    async def _render_text(
        self,
        data: dict[str, t.Any],
        manager: DialogManager,
    ) -> str:
        error_key = data.get(self.error_field, "")
        if not error_key:
            return ""
        ctx = get_context()
        loc = Localizer(ctx.i18n.locales_data["admin"])
        return loc(f"messages.panel.errors.{error_key}")


def build_pagination_buttons(
    current_page: int,
    total_pages: int,
) -> list[dict[str, str]]:
    if total_pages <= 1:
        return []

    page = current_page + 1
    buttons = {}

    if total_pages <= 5:
        for p in range(1, total_pages + 1):
            buttons[p] = str(p)
    elif page <= 3:
        for p in range(1, 4):
            buttons[p] = str(p)
        buttons[4] = f"4 ›"
        buttons[total_pages] = f"{total_pages} »"
    elif page > total_pages - 3:
        buttons[1] = "« 1"
        buttons[total_pages - 3] = f"‹ {total_pages - 3}"
        for p in range(total_pages - 2, total_pages + 1):
            buttons[p] = str(p)
    else:
        buttons[1] = "« 1"
        buttons[page - 1] = f"‹ {page - 1}"
        buttons[page + 1] = f"{page + 1} ›"
        buttons[total_pages] = f"{total_pages} »"
        buttons[page] = str(page)

    buttons[page] = f"· {page} ·"

    return [{"id": str(p - 1), "label": label} for p, label in sorted(buttons.items())]
