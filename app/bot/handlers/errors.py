import logging

from aiogram import Router
from aiogram.types import ErrorEvent

logger = logging.getLogger(__name__)
router = Router()


@router.error()
async def error_handler(event: ErrorEvent) -> bool:
    logger.exception(
        "Unhandled error in update %s: %s",
        event.update.update_id if event.update else "?",
        event.exception,
    )
    return True
