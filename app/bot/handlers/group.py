import logging
from datetime import datetime

from aiogram import Router, F
from aiogram.enums import ChatType
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import Command, CommandObject
from aiogram.types import Message, CallbackQuery, InaccessibleMessage
from aiogram.utils.markdown import hcode
from pyapiq.exceptions import APIClientResponseError

from ..utils import keyboards
from ..utils.i18n import Localizer
from ..utils.report import (
    ReportData,
    parse_report_text,
    format_report_text,
    create_report_markup,
    reverse_reason_key,
    toggle_vote,
)
from ...api import UpdateBanItem, UpdateBansPayload, api_retry
from ...config import GROUP_ID, TIMEZONE
from ...context import Context
from ...database import UnitOfWork
from ...database.models import UserModel

logger = logging.getLogger(__name__)
router = Router()
id_router = Router()
id_router.message.filter(F.chat.type.in_({ChatType.GROUP, ChatType.SUPERGROUP}))

router.message.filter(
    F.chat.id == GROUP_ID,
    F.chat.type.in_({ChatType.GROUP, ChatType.SUPERGROUP}),
)
router.callback_query.filter(
    F.message.chat.id == GROUP_ID,
    F.message.chat.type.in_({ChatType.GROUP, ChatType.SUPERGROUP}),
)


def _safe_loc(loc: Localizer, key: str, fallback: str = "—") -> str:
    template = loc.get_nested(loc.locale_data, key)  # type: ignore
    return template if template else fallback


async def _edit_report(
    bot,
    message_id: int,
    data: ReportData,
    with_buttons: bool = True,
) -> None:
    text = format_report_text(data)
    markup = create_report_markup(data.reason_display) if with_buttons else None
    try:
        await bot.edit_message_text(
            chat_id=GROUP_ID,
            message_id=message_id,
            text=text,
            reply_markup=markup,
        )
    except TelegramBadRequest as e:
        if "message is not modified" not in e.message:
            raise


async def _ban_via_api(ctx: Context, data: ReportData, admin: UserModel) -> None:
    payload = UpdateBansPayload(
        [  # noqa
            UpdateBanItem(
                bag_id=data.bag_id,
                admin=admin.sender,
                reason=data.reason or data.reason_display,
                comment=data.problem or "",
                status=True,
            ),
        ]
    )
    await api_retry(lambda: ctx.mytonstorage.bans.update(bans=payload))


@id_router.message(Command("id"))
async def group_id_command(message: Message) -> None:
    await message.reply(hcode(message.chat.id))


@router.message(Command("info"))
async def info_command(
    message: Message,
    uow: UnitOfWork,
    localizer: Localizer,
) -> None:
    user = await uow.user.get(message_thread_id=message.message_thread_id)
    if user is None:
        return

    text = localizer(
        "messages.command_info",
        user_id=user.user_id,
        username=user.mention,
        full_name=user.full_name,
        language_code=_safe_loc(
            localizer, f"common.lang.{user.language_code}", user.language_code or "—"
        ),
        state=_safe_loc(localizer, f"common.state.{user.state}", user.state),
        is_banned=localizer("common.yes") if user.is_banned else localizer("common.no"),
        created_at=user.created_at.strftime("%Y-%m-%d %H:%M"),
    )
    await message.reply(text=text)


@router.message(Command("ban", "unban"))
async def ban_unban_command(
    message: Message,
    command: CommandObject,
    uow: UnitOfWork,
    localizer: Localizer,
) -> None:
    user = await uow.user.get(message_thread_id=message.message_thread_id)
    if user is None:
        return

    user.is_banned = command.command == "ban"
    await uow.user.upsert(user)
    text = localizer(f"messages.command_{command.command}", user_mention=user.mention)
    await message.reply(text=text)


@router.callback_query()
async def callback_query_handler(
    call: CallbackQuery,
    ctx: Context,
    localizer: Localizer,
    user_model: UserModel,
) -> None:
    if isinstance(call.message, InaccessibleMessage):
        await call.answer()
        return

    html_text = call.message.text and call.message.html_text
    if not html_text:
        await call.answer()
        return

    report = parse_report_text(html_text)
    if report is None or report.status != "pending":
        await call.answer()
        return

    reason_map: dict = localizer("reason")  # type: ignore
    report.reason = reverse_reason_key(reason_map, report.reason_display)
    msg_id = call.message.message_id

    if call.data == "change_reason":
        try:
            await ctx.bot.edit_message_reply_markup(
                chat_id=GROUP_ID,
                message_id=msg_id,
                reply_markup=keyboards.select_reason(localizer),
            )
        except TelegramBadRequest:
            pass

    elif call.data in reason_map:
        report.reason = call.data
        report.reason_display = reason_map[call.data]
        await _edit_report(ctx.bot, msg_id, report)

    elif call.data == "back":
        await _edit_report(ctx.bot, msg_id, report)

    elif call.data in {"approve", "reject"}:
        admins = await ctx.bot.get_chat_administrators(chat_id=GROUP_ID)
        admin_ids = {a.user.id for a in admins if not a.user.is_bot}
        mention = user_model.mention

        if user_model.user_id in admin_ids:
            await _handle_admin_decision(
                call, ctx, localizer, report, user_model, mention, msg_id
            )
        else:
            await _handle_moderator_vote(
                call, ctx, localizer, report, admins, mention, msg_id
            )

    await call.answer()


async def _handle_moderator_vote(
    call: CallbackQuery,
    ctx: Context,
    localizer: Localizer,
    report: ReportData,
    admins,
    mention: str,
    msg_id: int,
) -> None:
    if call.data == "approve":
        report.approve_mentions = toggle_vote(report.approve_mentions, mention)
        report.reject_mentions = [m for m in report.reject_mentions if m != mention]
    else:
        report.reject_mentions = toggle_vote(report.reject_mentions, mention)
        report.approve_mentions = [m for m in report.approve_mentions if m != mention]

    await _edit_report(ctx.bot, msg_id, report)

    if len(report.approve_mentions) >= 2:
        admin_mentions = ", ".join(
            a.user.mention_html() for a in admins if not a.user.is_bot
        )
        await ctx.bot.send_message(
            chat_id=GROUP_ID,
            text=localizer("messages.report_waiting", admins=admin_mentions),
            message_thread_id=call.message.message_thread_id,
            reply_to_message_id=msg_id,
        )


async def _handle_admin_decision(
    call: CallbackQuery,
    ctx: Context,
    localizer: Localizer,
    report: ReportData,
    user_model: UserModel,
    mention: str,
    msg_id: int,
) -> None:
    resolved_at = datetime.now(TIMEZONE).strftime("%Y-%m-%d %H:%M")
    report.resolved_by = mention
    report.resolved_at = resolved_at

    if call.data == "approve":
        report.status = "approved"
        try:
            await _ban_via_api(ctx, report, user_model)
        except APIClientResponseError as e:
            logger.exception("Failed to send ban to API")
            await call.answer(
                localizer("errors.api", status_code=e.status_code, message=e.message),
                show_alert=True,
            )
            return
        except Exception as e:
            logger.exception("Failed to send ban to API")
            await call.answer(localizer("errors.unknown", error=e), show_alert=True)
            return
    else:
        report.status = "rejected"

    await _edit_report(ctx.bot, msg_id, report, with_buttons=False)
