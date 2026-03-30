import logging
import typing as t

from aiogram import Bot
from aiogram.exceptions import TelegramRetryAfter
from aiogram.types import (
    BotCommandScopeAllPrivateChats,
    BotCommandScopeAllGroupChats,
    BotCommandScopeChat,
    BotCommand,
)

from .utils.i18n import Localizer
from ..config import (
    SUPPORTED_LOCALES,
    DEFAULT_LOCALE,
    ADMIN_IDS_SET,
)
from ..context import Context

logger = logging.getLogger(__name__)


def _build_commands(commands_section: dict) -> t.List[BotCommand]:
    commands: t.List[BotCommand] = []
    for name, entry in commands_section.items():
        if not isinstance(entry, dict):
            continue
        description = entry.get("description")
        if not description:
            continue
        commands.append(BotCommand(command=name, description=description))
    return commands


async def setup(ctx: Context) -> None:
    bot: Bot = ctx.bot
    admin_loc = Localizer(ctx.i18n.locales_data.get("admin"))
    admin_commands = admin_loc.locale_data.get("commands", {})

    try:
        group_scope = BotCommandScopeAllGroupChats()
        group_commands = _build_commands(admin_commands.get("group", {}))
        await bot.set_my_commands(group_commands, scope=group_scope)

        private_scope = BotCommandScopeAllPrivateChats()
        for locale in SUPPORTED_LOCALES:
            locale_data = ctx.i18n.locales_data.get(locale)
            localizer = Localizer(locale_data)
            commands = _build_commands(localizer.locale_data.get("commands", {}))

            if not commands:
                continue
            if locale == DEFAULT_LOCALE:
                await bot.set_my_commands(commands=commands, scope=private_scope)
            else:
                await bot.set_my_commands(
                    commands=commands,
                    scope=private_scope,
                    language_code=locale,
                )

        admin_extra = _build_commands(admin_commands.get("private", {}))
        for admin_id in ADMIN_IDS_SET:
            for locale in SUPPORTED_LOCALES:
                locale_data = ctx.i18n.locales_data.get(locale)
                base_cmds = _build_commands(
                    Localizer(locale_data).locale_data.get("commands", {})
                )
                base_cmds.extend(admin_extra)
                try:
                    scope = BotCommandScopeChat(chat_id=admin_id)
                    if locale == DEFAULT_LOCALE:
                        await bot.set_my_commands(commands=base_cmds, scope=scope)
                    else:
                        await bot.set_my_commands(
                            commands=base_cmds, scope=scope, language_code=locale
                        )
                except Exception as e:
                    logger.warning(
                        "Failed to set admin commands for %d: %s", admin_id, e
                    )
        logger.info("Commands registered")

    except TelegramRetryAfter as e:
        logger.error(f"Failed to setup commands: \n{e.message}")


async def delete(ctx: Context) -> None:
    bot: Bot = ctx.bot

    try:
        private_scope = BotCommandScopeAllPrivateChats()
        await bot.delete_my_commands(scope=private_scope)
        for locale in SUPPORTED_LOCALES:
            if locale == DEFAULT_LOCALE:
                continue
            await bot.delete_my_commands(scope=private_scope, language_code=locale)

        group_scope = BotCommandScopeAllGroupChats()
        await bot.delete_my_commands(scope=group_scope)

        for admin_id in ADMIN_IDS_SET:
            try:
                scope = BotCommandScopeChat(chat_id=admin_id)
                await bot.delete_my_commands(scope=scope)
                for locale in SUPPORTED_LOCALES:
                    if locale != DEFAULT_LOCALE:
                        await bot.delete_my_commands(scope=scope, language_code=locale)
            except Exception:
                pass

        logger.info("Commands deleted")

    except TelegramRetryAfter as e:
        logger.error(f"Failed to delete commands: \n{e.message}")
