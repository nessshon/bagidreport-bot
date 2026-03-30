import logging

from aiogram.types import Message
from aiogram_dialog import DialogManager, ShowMode
from aiogram_dialog.widgets.input import MessageInput

from .states import UsersMenu, BagsMenu
from ..utils.message import extract_bag_id
from ...api import api_retry
from ...context import get_context
from ...database import UnitOfWork

logger = logging.getLogger(__name__)


def _show_error(manager: DialogManager, key: str, field: str) -> None:
    manager.dialog_data[field] = key
    manager.show_mode = ShowMode.DELETE_AND_SEND


async def search_user(
    message: Message,
    _: MessageInput,
    manager: DialogManager,
) -> None:
    text = (message.text or "").strip()
    manager.dialog_data.pop("search_error", None)

    if not text.isdigit():
        _show_error(manager, "invalid_user_id", "search_error")
        return

    uow: UnitOfWork = manager.middleware_data["uow"]
    user = await uow.user.get(user_id=int(text))
    if not user:
        _show_error(manager, "user_not_found", "search_error")
        return

    manager.dialog_data["selected_user_id"] = text
    manager.show_mode = ShowMode.DELETE_AND_SEND
    await manager.switch_to(UsersMenu.DETAIL)


async def unban_bag_input(
    message: Message,
    _: MessageInput,
    manager: DialogManager,
) -> None:
    manager.dialog_data.pop("unban_error", None)
    bag_id = extract_bag_id((message.text or ""))

    if bag_id is None:
        _show_error(manager, "invalid_bag_id", "unban_error")
        return

    ctx = get_context()
    try:
        resp = await api_retry(lambda: ctx.mytonstorage.bans.get_by_id(bag_id=bag_id))
        if resp and resp.ban:
            manager.dialog_data["unban_bag_id"] = bag_id
            manager.dialog_data["ban_found"] = True
            manager.dialog_data["ban_reason"] = resp.ban.reason
            manager.dialog_data["ban_admin"] = resp.ban.admin
            manager.dialog_data["ban_comment"] = resp.ban.comment or "—"
        else:
            manager.dialog_data["unban_bag_id"] = bag_id
            manager.dialog_data["ban_found"] = False
            manager.dialog_data["ban_reason"] = "—"
            manager.dialog_data["ban_admin"] = "—"
            manager.dialog_data["ban_comment"] = "—"
    except Exception:
        logger.exception("Failed to check bag via API")
        _show_error(manager, "api_unavailable", "unban_error")
        return

    manager.show_mode = ShowMode.DELETE_AND_SEND
    await manager.switch_to(BagsMenu.UNBAN_DETAIL)


async def create_ban_input(
    message: Message,
    _: MessageInput,
    manager: DialogManager,
) -> None:
    manager.dialog_data.pop("create_ban_error", None)
    bag_id = extract_bag_id((message.text or ""))

    if bag_id is None:
        _show_error(manager, "invalid_bag_id", "create_ban_error")
        return

    ctx = get_context()
    try:
        resp = await api_retry(lambda: ctx.mytonstorage.bans.get_by_id(bag_id=bag_id))
        if resp and resp.ban:
            _show_error(manager, "bag_already_banned", "create_ban_error")
            return
    except Exception:
        logger.exception("Failed to check ban status via API")
        _show_error(manager, "api_unavailable", "create_ban_error")
        return

    manager.dialog_data["create_ban_bag_id"] = bag_id
    manager.show_mode = ShowMode.DELETE_AND_SEND
    await manager.switch_to(BagsMenu.BAN_REASON)


async def create_ban_comment(
    message: Message,
    _: MessageInput,
    manager: DialogManager,
) -> None:
    from .on_clicks import _finalize_create_ban

    text = (message.text or "").strip()
    if not text:
        return
    manager.show_mode = ShowMode.DELETE_AND_SEND
    await _finalize_create_ban(manager, comment=text)
