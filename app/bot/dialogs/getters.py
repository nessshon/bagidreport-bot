import typing as t

from aiogram_dialog import DialogManager

from .widgets import (
    ITEMS_PER_PAGE,
    build_pagination_buttons,
)
from ..utils.i18n import Localizer
from ...context import get_context
from ...database import UnitOfWork
from ...database.models import UserModel


def _loc() -> Localizer:
    return Localizer(get_context().i18n.locales_data["admin"])


def _safe_loc(loc: Localizer, key: str, fallback: str = "—") -> str:
    template = loc.get_nested(loc.locale_data, key)
    return template if template else fallback


def _format_datetime(dt) -> str:
    return dt.strftime("%Y-%m-%d %H:%M") if dt else "—"


def _code_table(rows: list[tuple[str, t.Any]], pad: int = 18) -> str:
    lines = [f"• {label:<{pad}}  {value}" for label, value in rows]
    return "<code>" + "\n".join(lines) + "</code>"


def _build_stats_table(loc: Localizer, stats: dict[str, t.Any]) -> str:
    btn = loc.get_nested(loc.locale_data, "buttons")
    tabs = loc.get_nested(loc.locale_data, "tabs")
    c = loc.get_nested(loc.locale_data, "common")
    rows = [
        (c["active"], stats["users_active"]),
        (c["inactive"], stats["users_inactive"]),
        (tabs["users"]["banned"], stats["users_banned"]),
    ]
    return f"<b>{btn['manage_users']}: {stats['users_total']}</b>\n" + _code_table(rows)


async def admin_menu(dialog_manager: DialogManager, **_) -> dict[str, t.Any]:
    uow: UnitOfWork = dialog_manager.middleware_data["uow"]
    loc = _loc()
    stats = await uow.get_stats_summary()
    return {"stats_table": _build_stats_table(loc, stats)}


async def users_list(dialog_manager: DialogManager, **_) -> dict[str, t.Any]:
    uow: UnitOfWork = dialog_manager.middleware_data["uow"]
    tab = dialog_manager.dialog_data.get("users_tab", "all")
    page = int(dialog_manager.dialog_data.get("users_page", 0))

    dialog_manager.current_context().widget_data["users_tab"] = tab

    users_total = await uow.user.count()
    users_active = await uow.user.count(state="member")
    users_banned = await uow.user.count(is_banned=True)

    filters = {}
    if tab == "banned":
        filters["is_banned"] = True

    total = await uow.user.count(**filters)
    total_pages = max(1, (total + ITEMS_PER_PAGE - 1) // ITEMS_PER_PAGE)
    page = min(page, total_pages - 1)

    users = await uow.user.list(
        offset=page * ITEMS_PER_PAGE,
        limit=ITEMS_PER_PAGE,
        order_by=UserModel.created_at.desc(),
        **filters,
    )

    loc = _loc()
    c = loc.get_nested(loc.locale_data, "common")
    tabs = loc.get_nested(loc.locale_data, "tabs")
    users_stats = _code_table(
        [
            (c["active"], users_active),
            (c["inactive"], users_total - users_active),
            (tabs["users"]["banned"], users_banned),
        ]
    )

    return {
        "users_total": users_total,
        "users_stats": users_stats,
        "users_tab": tab,
        "user_items": [
            {"id": str(u.user_id), "label": u.full_name or str(u.user_id)}
            for u in users
        ],
        "pagination_items": build_pagination_buttons(page, total_pages),
    }


async def user_detail(dialog_manager: DialogManager, **_) -> dict[str, t.Any]:
    uow: UnitOfWork = dialog_manager.middleware_data["uow"]
    loc = _loc()
    user_id = int(dialog_manager.dialog_data.get("selected_user_id", 0))

    user = await uow.user.get(user_id=user_id)
    if not user:
        return {}

    return {
        "user_id": user.user_id,
        "username": f"@{user.username}" if user.username else "—",
        "full_name": user.full_name or "—",
        "language_code": _safe_loc(
            loc, f"common.lang.{user.language_code}", user.language_code
        ),
        "state": _safe_loc(loc, f"common.state.{user.state}", user.state),
        "is_banned": user.is_banned,
        "is_banned_text": loc("common.yes") if user.is_banned else loc("common.no"),
        "created_at": _format_datetime(user.created_at),
    }


async def unban_bag_detail(dialog_manager: DialogManager, **_) -> dict[str, t.Any]:
    loc = _loc()
    ban_found = dialog_manager.dialog_data.get("ban_found", False)
    raw_reason = dialog_manager.dialog_data.get("ban_reason", "—")
    reason_text = loc.get_nested(loc.locale_data, f"reason.{raw_reason}")
    return {
        "bag_id": dialog_manager.dialog_data.get("unban_bag_id", ""),
        "ban_found": ban_found,
        "ban_found_text": loc("common.yes") if ban_found else loc("common.no"),
        "ban_reason": reason_text or raw_reason,
        "ban_admin": dialog_manager.dialog_data.get("ban_admin", "—"),
        "ban_comment": dialog_manager.dialog_data.get("ban_comment", "—"),
    }


async def search_user(dialog_manager: DialogManager, **_) -> dict[str, t.Any]:
    return {
        "error_key": dialog_manager.dialog_data.get("search_error", ""),
    }


async def unban_bag(dialog_manager: DialogManager, **_) -> dict[str, t.Any]:
    return {
        "error_key": dialog_manager.dialog_data.get("unban_error", ""),
    }


async def create_ban(dialog_manager: DialogManager, **_) -> dict[str, t.Any]:
    return {
        "error_key": dialog_manager.dialog_data.get("create_ban_error", ""),
    }
