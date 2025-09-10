import logging

from aiogram import Dispatcher

from . import group
from . import private

logger = logging.getLogger(__name__)


def register(dp: Dispatcher) -> None:
    dp.include_router(group.router)
    dp.include_router(private.router)

    logger.info("Handlers registered")


__all__ = ["register"]
