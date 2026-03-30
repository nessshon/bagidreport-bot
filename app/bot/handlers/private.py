import logging
import time
import typing as t
from contextlib import suppress

from aiogram import Router, F, flags
from aiogram.enums import ChatType, ContentType
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import (
    ChatMemberUpdated,
    Message,
    CallbackQuery,
    InaccessibleMessage,
)
from aiogram_dialog import DialogManager, StartMode

from ..dialogs.states import AdminMenu
from ..utils import keyboards
from ..utils.captcha import generate_captcha
from ..utils.i18n import Localizer
from ..utils.message import (
    delete_last_message_id,
    save_last_message_id,
    delete_message,
    validate_report_message,
)
from ..utils.report import ReportData, format_report_text, create_report_markup
from ..utils.states import UserState
from ...api import AddReportPayload, api_retry
from ...config import ADMIN_IDS_SET, CAPTCHA_TTL, GROUP_ID
from ...context import Context, get_context
from ...database import UnitOfWork
from ...database.models import UserModel

logger = logging.getLogger(__name__)
router = Router()

router.message.filter(F.chat.type.in_({ChatType.PRIVATE}))
router.callback_query.filter(F.message.chat.type.in_({ChatType.PRIVATE}))
router.my_chat_member.filter(F.chat.type.in_({ChatType.PRIVATE}))


def _safe_loc(loc: Localizer, key: str, fallback: str = "—") -> str:
    template = loc.get_nested(loc.locale_data, key)
    return template if template else fallback


async def _reset_to_main(
    call: CallbackQuery, state: FSMContext, localizer: Localizer
) -> None:
    chat_id = call.from_user.id
    with suppress(Exception):
        await call.bot.delete_message(
            chat_id=chat_id, message_id=call.message.message_id
        )
    msg = await call.bot.send_message(chat_id=chat_id, text=localizer("messages.main"))
    await save_last_message_id(state, msg.message_id)
    await state.set_state(UserState.MAIN)
    await call.answer()


async def main_window(
    message: Message,
    state: FSMContext,
    localizer: Localizer,
    error_code: t.Optional[str] = None,
) -> None:
    text = localizer("messages.main")
    if error_code is not None:
        text += "\n" + localizer(f"errors.{error_code}")
    msg = await message.answer(text)
    await delete_last_message_id(message.bot, state, message.chat.id)
    await save_last_message_id(state, msg.message_id)
    await state.set_state(UserState.MAIN)


async def select_language_window(
    message: Message,
    state: FSMContext,
    localizer: Localizer,
) -> None:
    msg = await message.answer(
        localizer("messages.select_language"),
        reply_markup=keyboards.select_language(localizer),
    )
    await delete_last_message_id(message.bot, state, message.chat.id)
    await save_last_message_id(state, msg.message_id)
    await state.set_state(UserState.MAIN)


async def select_reason(
    message: Message,
    state: FSMContext,
    localizer: Localizer,
) -> None:
    msg = await message.answer(
        localizer("messages.select_reason"),
        reply_markup=keyboards.select_reason(localizer),
    )
    await delete_last_message_id(message.bot, state, message.chat.id)
    await save_last_message_id(state, msg.message_id)
    await state.set_state(UserState.REASON)


async def input_captcha_window(
    message: Message,
    state: FSMContext,
    localizer: Localizer,
    error_code: t.Optional[str] = None,
) -> None:
    caption = localizer("messages.input_captcha")
    if error_code is not None:
        caption += "\n" + localizer(f"errors.{error_code}")
    image, captcha_solution = await generate_captcha()
    msg = await message.answer_photo(
        image, caption=caption, reply_markup=keyboards.create_button(localizer, "back")
    )
    await delete_last_message_id(message.bot, state, message.chat.id)
    await save_last_message_id(state, msg.message_id)
    await state.update_data(
        captcha_solution=captcha_solution,
        captcha_issued_at=int(time.time()),
    )
    await state.set_state(UserState.CAPTCHA)


async def _ensure_topic(bot, user_model: UserModel, uow: UnitOfWork) -> int:
    if user_model.message_thread_id:
        return user_model.message_thread_id

    topic = await bot.create_forum_topic(chat_id=GROUP_ID, name=user_model.topic_name)
    user_model.message_thread_id = topic.message_thread_id
    await uow.user.upsert(user_model)

    admin_loc = Localizer(get_context().i18n.locales_data["admin"])
    await bot.send_message(
        chat_id=GROUP_ID,
        text=admin_loc(
            "messages.command_info",
            user_id=user_model.user_id,
            username=user_model.mention,
            full_name=user_model.full_name,
            language_code=_safe_loc(
                admin_loc,
                f"common.lang.{user_model.language_code}",
                user_model.language_code or "—",
            ),
            state=_safe_loc(
                admin_loc, f"common.state.{user_model.state}", user_model.state or "—"
            ),
            is_banned=(
                admin_loc("common.yes")
                if user_model.is_banned
                else admin_loc("common.no")
            ),
            created_at=user_model.created_at.strftime("%Y-%m-%d %H:%M"),
        ),
        message_thread_id=topic.message_thread_id,
        disable_notification=True,
    )
    return topic.message_thread_id


async def _send_report_to_topic(
    bot,
    thread_id: int,
    user_model: UserModel,
    uow: UnitOfWork,
    bag_id: str,
    reason: str,
    reason_display: str,
    problem: str,
) -> None:
    data = ReportData(
        bag_id=bag_id,
        reason=reason,
        reason_display=reason_display,
        problem=problem,
        author_mention=user_model.mention,
    )
    text = format_report_text(data)
    markup = create_report_markup(reason_display)

    try:
        await bot.send_message(
            chat_id=GROUP_ID,
            text=text,
            reply_markup=markup,
            message_thread_id=thread_id,
        )
    except TelegramBadRequest as e:
        if "thread not found" not in str(e).lower():
            raise
        topic = await bot.create_forum_topic(
            chat_id=GROUP_ID, name=user_model.topic_name
        )
        user_model.message_thread_id = topic.message_thread_id
        await uow.user.upsert(user_model)
        await bot.send_message(
            chat_id=GROUP_ID,
            text=text,
            reply_markup=markup,
            message_thread_id=topic.message_thread_id,
        )


@router.message(Command("start"))
async def start_command(
    message: Message,
    state: FSMContext,
    user_model: UserModel,
    localizer: Localizer,
) -> None:
    if user_model.language_code is not None:
        await main_window(message, state, localizer)
        return
    await select_language_window(message, state, localizer)


@router.message(Command("lang"))
async def lang_command(
    message: Message,
    state: FSMContext,
    localizer: Localizer,
) -> None:
    msg = await message.answer(
        localizer("messages.select_language"),
        reply_markup=keyboards.select_language(localizer),
    )
    await delete_last_message_id(message.bot, state, message.chat.id)
    await save_last_message_id(state, msg.message_id)


@router.message(Command("help"))
async def help_command(
    message: Message,
    state: FSMContext,
    localizer: Localizer,
) -> None:
    msg = await message.answer(localizer("messages.help"))
    await delete_last_message_id(message.bot, state, message.chat.id)
    await save_last_message_id(state, msg.message_id)


@router.message(Command("admin"))
async def admin_command(
    _: Message,
    user_model: UserModel,
    dialog_manager: DialogManager,
) -> None:
    if user_model.user_id not in ADMIN_IDS_SET:
        return
    await dialog_manager.start(AdminMenu.MAIN, mode=StartMode.RESET_STACK)


@router.message(UserState.CAPTCHA)
@flags.rate_limit(2)
async def captcha_message_handler(
    message: Message,
    ctx: Context,
    user_model: UserModel,
    state: FSMContext,
    localizer: Localizer,
    uow: UnitOfWork,
) -> None:
    if message.content_type != ContentType.TEXT:
        await delete_message(message)
        return

    state_data = await state.get_data()
    solution = state_data.get("captcha_solution")
    issued_at = state_data.get("captcha_issued_at")
    user_answer = (message.text or "").strip()

    if issued_at is None or (int(time.time()) - float(issued_at)) > CAPTCHA_TTL:
        await input_captcha_window(message, state, localizer, "captcha_expired")
        await delete_message(message)
        return

    if user_answer != solution:
        await input_captcha_window(message, state, localizer, "captcha_wrong")
        await delete_message(message)
        return

    bag_id = state_data.get("bag_id")
    reason = state_data.get("reason")
    problem = state_data.get("problem")

    try:
        ban_resp = await api_retry(
            lambda: ctx.mytonstorage.bans.get_by_id(bag_id=bag_id)
        )
        if ban_resp and ban_resp.ban:
            await main_window(message, state, localizer, "bag_already_banned")
            await delete_message(message)
            return
    except Exception:
        logger.exception("Failed to check ban status via API")
        await main_window(message, state, localizer, "api_unavailable")
        await delete_message(message)
        return

    try:
        await api_retry(
            lambda: ctx.mytonstorage.reports.add(
                report=AddReportPayload(
                    bag_id=bag_id,
                    reason=reason,
                    sender=user_model.sender,
                    comment=problem,
                )
            )
        )
    except Exception:
        logger.exception("Failed to send report to API")
        await main_window(message, state, localizer, "api_unavailable")
        await delete_message(message)
        return

    try:
        thread_id = await _ensure_topic(ctx.bot, user_model, uow)
        reason_map: dict = localizer("reason")  # type: ignore
        await _send_report_to_topic(
            ctx.bot,
            thread_id,
            user_model,
            uow,
            bag_id,
            reason,
            reason_map.get(reason, reason),
            problem,
        )
        await delete_last_message_id(message.bot, state, message.chat.id)
        await message.answer(localizer("messages.report_sent", report_bag_id=bag_id))
        await main_window(message, state, localizer)
    except Exception:
        logger.exception("Failed to post report to topic")
        await main_window(message, state, localizer, "unknown")
        await delete_message(message)
        return

    await delete_message(message)


@router.message()
@flags.rate_limit(3)
async def message_handler(
    message: Message,
    ctx: Context,
    state: FSMContext,
    localizer: Localizer,
) -> None:
    if message.content_type != ContentType.TEXT:
        await main_window(message, state, localizer, "non_text")
        await delete_message(message)
        return

    report_data, error_code = validate_report_message(message.text)
    if error_code is not None:
        await main_window(message, state, localizer, error_code)
        await delete_message(message)
        return

    bag_id = report_data["bag_id"]
    try:
        ban_resp = await api_retry(
            lambda: ctx.mytonstorage.bans.get_by_id(bag_id=bag_id)
        )
        if ban_resp and ban_resp.ban:
            await main_window(message, state, localizer, "bag_already_banned")
            await delete_message(message)
            return
    except Exception:
        logger.exception("Failed to check ban via API")
        await main_window(message, state, localizer, "api_unavailable")
        await delete_message(message)
        return

    await state.update_data(**report_data)
    await select_reason(message, state, localizer)


@router.callback_query(UserState.REASON)
async def select_reason_callback_query_handler(
    call: CallbackQuery,
    state: FSMContext,
    localizer: Localizer,
) -> None:
    if isinstance(call.message, InaccessibleMessage):
        await _reset_to_main(call, state, localizer)
        return
    reason_map: dict = localizer("reason")  # type: ignore
    if call.data == "back":
        await main_window(call.message, state, localizer)
    elif call.data in reason_map:
        await state.update_data(reason=call.data)
        await input_captcha_window(call.message, state, localizer)
    await call.answer()


@router.callback_query(UserState.CAPTCHA)
async def captcha_callback_query_handler(
    call: CallbackQuery,
    state: FSMContext,
    localizer: Localizer,
) -> None:
    if isinstance(call.message, InaccessibleMessage):
        await _reset_to_main(call, state, localizer)
        return
    if call.data == "back":
        await select_reason(call.message, state, localizer)
    await call.answer()


@router.callback_query()
async def callback_query_handler(
    call: CallbackQuery,
    state: FSMContext,
    uow: UnitOfWork,
    localizer: Localizer,
    user_model: UserModel,
    ctx: Context,
) -> None:
    if isinstance(call.message, InaccessibleMessage):
        await call.answer(localizer("errors.message_expired"), show_alert=True)
        return

    if call.data.startswith("selected_lang"):
        language_code = call.data.split(":")[1]
        locale_data = ctx.i18n.locales_data.get(language_code)
        if locale_data is None:
            await call.answer()
            return
        first_time = user_model.language_code is None
        user_model.language_code = language_code
        localizer = Localizer(locale_data)
        await uow.user.upsert(user_model)
        if first_time:
            await _ensure_topic(ctx.bot, user_model, uow)
        await main_window(call.message, state, localizer)

    await call.answer()


@router.my_chat_member()
async def my_chat_member_handler(
    update: ChatMemberUpdated,
    uow: UnitOfWork,
    user_model: UserModel,
) -> None:
    user_model.state = update.new_chat_member.status
    await uow.user.upsert(user_model)
