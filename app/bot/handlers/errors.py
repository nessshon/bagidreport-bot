import logging

from aiogram import Router
from aiogram.types import ErrorEvent
from aiogram_dialog import DialogManager

logger = logging.getLogger(__name__)
router = Router()


async def on_unknown_intent(event: ErrorEvent, dialog_manager: DialogManager) -> None:
    logger.error("Restarting dialog: %s", event.exception)
    await dialog_manager.reset_stack()


async def on_unknown_state(event: ErrorEvent, dialog_manager: DialogManager) -> None:
    logger.error("Restarting dialog: %s", event.exception)
    await dialog_manager.reset_stack()


@router.error()
async def error_handler(event: ErrorEvent) -> bool:
    logger.exception(
        "Unhandled error in update %s: %s",
        event.update.update_id if event.update else "?",
        event.exception,
    )
    return True
