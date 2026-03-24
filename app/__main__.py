import logging
from contextlib import suppress

from aiogram import Dispatcher, Bot
from aiogram.client.default import DefaultBotProperties
from aiogram.exceptions import TelegramRetryAfter
from aiogram.fsm.storage.base import DefaultKeyBuilder
from aiogram.fsm.storage.redis import RedisStorage
from redis.asyncio import Redis

from .api.mytonstorage import MytonstorageClient
from .bot import commands, middlewares, handlers, Broadcaster
from .bot.utils.i18n import I18N
from .config import BOT_TOKEN, REDIS_URL
from .context import Context, set_context
from .database import Database
from .logging import setup_logging

setup_logging()
logger = logging.getLogger("app.main")


async def on_startup(ctx: Context) -> None:
    logger.info("App startup initiated...")

    await ctx.db.start()
    await ctx.mytonstorage.ensure_session()

    middlewares.register(ctx.dp)
    handlers.register(ctx.dp)

    with suppress(TelegramRetryAfter):
        await commands.setup(ctx)

    logger.info("App startup complete")


async def on_shutdown(ctx: Context) -> None:
    logger.info("App shutdown initiated...")

    with suppress(TelegramRetryAfter):
        await commands.delete(ctx)
    await ctx.bot.session.close()
    await ctx.db.shutdown()
    await ctx.mytonstorage.close()

    logger.info("App shutdown complete")


async def main() -> None:
    logger.info("Preparing app...")

    ctx = Context()

    ctx.db = Database()
    ctx.redis = Redis.from_url(url=REDIS_URL)

    properties = DefaultBotProperties(
        parse_mode="HTML",
        link_preview_is_disabled=True,
    )
    storage = RedisStorage(
        redis=ctx.redis,
        key_builder=DefaultKeyBuilder(with_destiny=True),
    )
    ctx.bot = Bot(BOT_TOKEN, default=properties)
    ctx.dp = Dispatcher(storage=storage, ctx=ctx)

    ctx.mytonstorage = MytonstorageClient()
    ctx.broadcaster = Broadcaster(ctx.bot)
    ctx.i18n = I18N()

    ctx.dp.startup.register(on_startup)
    ctx.dp.shutdown.register(on_shutdown)
    set_context(ctx)

    allowed_updates = ctx.dp.resolve_used_update_types()
    await ctx.dp.start_polling(ctx.bot, allowed_updates=allowed_updates)


if __name__ == "__main__":
    import asyncio

    asyncio.run(main())
