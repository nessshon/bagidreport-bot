import logging

from aiogram import Dispatcher

from .db import DbSessionMiddleware
from .i18n import I18nMiddleware
from .throttling import ThrottlingMiddleware

logger = logging.getLogger(__name__)


def register(dp: Dispatcher) -> None:
    i18n_middleware = I18nMiddleware()
    db_middleware = DbSessionMiddleware()
    throttling_middleware = ThrottlingMiddleware()

    dp.update.middleware(db_middleware)
    dp.update.middleware(i18n_middleware)
    dp.message.middleware(throttling_middleware)
    dp.callback_query.middleware(throttling_middleware)

    logger.info("Middlewares registered")


__all__ = ["register"]
