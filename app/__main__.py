import asyncio
import logging
from contextlib import suppress

from aiogram import Dispatcher, Bot
from aiogram.client.default import DefaultBotProperties
from aiogram.fsm.storage.base import DefaultKeyBuilder
from aiogram.fsm.storage.redis import RedisStorage
from aiogram_dialog import setup_dialogs
from redis.asyncio import Redis

from .api import MytonstorageClient
from .bot import commands, middlewares, handlers, dialogs
from .bot.heartbeat import HeartbeatMiddleware
from .bot.utils.i18n import I18N
from .config import BOT_TOKEN, REDIS_URL, GATUS_HEARTBEAT_URL, GATUS_HEARTBEAT_TOKEN
from .context import Context, set_context
from .database import Database
from .logging import setup_logging

setup_logging()
logger = logging.getLogger("app.main")


async def on_startup(ctx: Context) -> None:
    logger.info("App startup initiated...")

    await ctx.db.start()
    await ctx.mytonstorage.ensure_session()
    with suppress(Exception):
        await commands.setup(ctx)

    if GATUS_HEARTBEAT_URL and GATUS_HEARTBEAT_TOKEN:
        ctx.heartbeat_task = asyncio.create_task(
            ctx.heartbeat.run(GATUS_HEARTBEAT_URL, GATUS_HEARTBEAT_TOKEN)
        )
    elif GATUS_HEARTBEAT_URL:
        logger.warning("GATUS_HEARTBEAT_URL is set but GATUS_HEARTBEAT_TOKEN is empty; heartbeat disabled")

    logger.info("App startup complete")


async def on_shutdown(ctx: Context) -> None:
    logger.info("App shutdown initiated...")

    with suppress(Exception):
        await commands.delete(ctx)
    if getattr(ctx, "heartbeat_task", None):
        ctx.heartbeat_task.cancel()
    await ctx.bot.session.close()
    await ctx.redis.aclose()
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

    middlewares.register(ctx.dp)
    dialogs.register(ctx.dp)
    handlers.register(ctx.dp)
    setup_dialogs(ctx.dp)

    ctx.heartbeat = HeartbeatMiddleware()
    ctx.bot.session.middleware(ctx.heartbeat)

    ctx.mytonstorage = MytonstorageClient()
    ctx.i18n = I18N()

    ctx.dp.startup.register(on_startup)
    ctx.dp.shutdown.register(on_shutdown)
    set_context(ctx)

    allowed_updates = ctx.dp.resolve_used_update_types(skip_events={"aiogd_update"})
    await ctx.dp.start_polling(ctx.bot, allowed_updates=allowed_updates)


if __name__ == "__main__":
    asyncio.run(main())
