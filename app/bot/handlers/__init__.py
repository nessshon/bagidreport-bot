import logging

from aiogram import Dispatcher
from aiogram.filters import ExceptionTypeFilter
from aiogram_dialog.api.exceptions import UnknownIntent, UnknownState

from . import errors
from . import group
from . import private

logger = logging.getLogger(__name__)


def register(dp: Dispatcher) -> None:
    dp.errors.register(
        errors.on_unknown_intent,
        ExceptionTypeFilter(UnknownIntent),
    )
    dp.errors.register(
        errors.on_unknown_state,
        ExceptionTypeFilter(UnknownState),
    )

    dp.include_router(group.router)
    dp.include_router(group.id_router)
    dp.include_router(private.router)
    dp.include_router(errors.router)

    logger.info("Handlers registered")


__all__ = ["register"]
