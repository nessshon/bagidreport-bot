import logging

from aiogram import Dispatcher, Router
from aiogram_dialog import Dialog

from . import windows

logger = logging.getLogger(__name__)


def register(dp: Dispatcher) -> None:
    dialog_router = Router()
    dialog_router.include_routers(
        Dialog(
            windows.admin_main,
        ),
        Dialog(
            windows.users_list_window,
            windows.users_search_window,
            windows.user_detail_window,
        ),
        Dialog(
            windows.unban_bag_window,
            windows.unban_bag_detail_window,
            windows.ban_create_window,
            windows.ban_create_reason_window,
            windows.ban_create_comment_window,
        ),
    )
    dp.include_router(dialog_router)

    logger.info("Dialogs registered")


__all__ = ["register"]
