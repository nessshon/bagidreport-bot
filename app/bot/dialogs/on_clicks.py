import logging

from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery
from aiogram_dialog import DialogManager, ShowMode

from .states import UsersMenu, BagsMenu
from ..utils.i18n import Localizer
from ..utils.message import save_last_message_id
from ..utils.states import UserState
from ...api import UpdateBanItem, UpdateBansPayload, api_retry
from ...context import get_context

logger = logging.getLogger(__name__)


async def close_admin(_, __, manager: DialogManager) -> None:
    await manager.done()


async def hide_admin(callback: CallbackQuery, __, manager: DialogManager) -> None:
    await manager.done()
    state: FSMContext = manager.middleware_data["state"]
    localizer: Localizer = manager.middleware_data["localizer"]
    text = localizer("messages.main")
    await callback.message.edit_text(text)
    await save_last_message_id(state, callback.message.message_id)
    await state.set_state(UserState.MAIN)


async def change_users_tab(_, __, manager: DialogManager, item_id: str) -> None:
    manager.dialog_data["users_tab"] = item_id
    manager.dialog_data["users_page"] = 0


async def change_users_page(_, __, manager: DialogManager, item_id: str) -> None:
    manager.dialog_data["users_page"] = int(item_id)


async def select_user(_, __, manager: DialogManager, item_id: str) -> None:
    manager.dialog_data["selected_user_id"] = item_id
    await manager.switch_to(UsersMenu.DETAIL)


async def toggle_user_ban(_, __, manager: DialogManager) -> None:
    uow = manager.middleware_data["uow"]
    user_id = int(manager.dialog_data.get("selected_user_id", 0))
    user = await uow.user.get(user_id=user_id)
    if user:
        user.is_banned = not user.is_banned
        await uow.user.upsert(user)


async def unban_bag(callback: CallbackQuery, __, manager: DialogManager) -> None:
    bag_id = manager.dialog_data.get("unban_bag_id", "")
    if not bag_id:
        return

    user_model = manager.middleware_data["user_model"]
    ctx = get_context()
    payload = UpdateBansPayload(
        [  # noqa
            UpdateBanItem(
                bag_id=bag_id,
                admin=user_model.sender,
                reason="",
                comment="",
                status=False,
            ),
        ]
    )
    try:
        await api_retry(lambda: ctx.mytonstorage.bans.update(bans=payload))
        manager.dialog_data["ban_found"] = False
    except Exception:
        logger.exception("Failed to unban bag via API")
        admin_loc = Localizer(ctx.i18n.locales_data["admin"])
        await callback.answer(admin_loc("errors.api_unavailable"), show_alert=True)


async def create_ban_reason(_, __, manager: DialogManager, item_id: str) -> None:
    manager.dialog_data["create_ban_reason"] = item_id
    await manager.switch_to(BagsMenu.BAN_COMMENT)


async def _finalize_create_ban(manager: DialogManager, comment: str) -> None:
    user_model = manager.middleware_data["user_model"]
    bag_id = manager.dialog_data.get("create_ban_bag_id", "")
    reason = manager.dialog_data.get("create_ban_reason", "other")
    if not bag_id:
        return

    ctx = get_context()
    payload = UpdateBansPayload(
        [  # noqa
            UpdateBanItem(
                bag_id=bag_id,
                admin=user_model.sender,
                reason=reason,
                comment=comment,
                status=True,
            ),
        ]
    )
    try:
        await api_retry(lambda: ctx.mytonstorage.bans.update(bans=payload))
    except Exception:
        logger.exception("Failed to create ban in API")
        manager.dialog_data["create_ban_error"] = "api_unavailable"
        manager.show_mode = ShowMode.DELETE_AND_SEND
        await manager.switch_to(BagsMenu.BAN)
        return

    manager.dialog_data["unban_bag_id"] = bag_id
    manager.dialog_data["ban_found"] = True
    manager.dialog_data["ban_reason"] = reason
    manager.dialog_data["ban_admin"] = user_model.sender
    manager.dialog_data["ban_comment"] = comment or "—"
    await manager.switch_to(BagsMenu.UNBAN_DETAIL)


async def skip_create_ban_comment(_, __, manager: DialogManager) -> None:
    await _finalize_create_ban(manager, comment="")
