import logging
import typing as t

from aiogram import Bot
from aiogram.exceptions import TelegramRetryAfter
from aiogram.types import (
    BotCommandScopeAllPrivateChats,
    BotCommandScopeAllGroupChats,
    BotCommand,
)

from .utils.i18n import Localizer
from ..config import SUPPORTED_LOCALES, DEFAULT_LOCALE
from ..context import Context

logger = logging.getLogger(__name__)


def build_group_commands(ctx: Context) -> t.List[BotCommand]:
    localizer = Localizer(ctx.i18n.locales_data.get("group"))
    commands_section = localizer.locale_data.get("commands", {})
    commands: t.List[BotCommand] = []

    for name, entry in commands_section.items():
        if not isinstance(entry, dict):
            continue
        try:
            description = localizer(f"commands.{name}.description")
        except KeyError:
            continue
        if not description:
            continue
        commands.append(BotCommand(command=name, description=description))
    return commands


def build_private_commands(localizer: Localizer) -> t.List[BotCommand]:
    commands_section = localizer.locale_data.get("commands", {})
    commands: t.List[BotCommand] = []

    for name, entry in commands_section.items():
        if not isinstance(entry, dict):
            continue
        try:
            description = localizer(f"commands.{name}.description")
        except KeyError:
            continue
        if not description:
            continue
        commands.append(BotCommand(command=name, description=description))
    return commands


async def setup(ctx: Context) -> None:
    bot: Bot = ctx.bot

    try:
        group_scope = BotCommandScopeAllGroupChats()
        group_commands = build_group_commands(ctx)
        await bot.set_my_commands(group_commands, scope=group_scope)

        private_scope = BotCommandScopeAllPrivateChats()
        for locale in SUPPORTED_LOCALES:
            locale_data = ctx.i18n.locales_data.get(locale)
            localizer = Localizer(locale_data)
            commands = build_private_commands(localizer)

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
        logger.info("Commands deleted")

    except TelegramRetryAfter as e:
        logger.error(f"Failed to delete commands: \n{e.message}")
