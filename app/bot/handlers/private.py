import logging
import time
import typing as t
from datetime import datetime

from aiogram import Router, F, flags
from aiogram.enums import ChatType, ContentType
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import (
    ChatMemberUpdated,
    Message,
    CallbackQuery,
)

from ..filters import IsBannedFilter
from ..utils import keyboards
from ..utils.captcha import generate_captcha
from ..utils.i18n import Localizer
from ..utils.message import (
    delete_last_message_id,
    save_last_message_id,
    delete_message,
    validate_complaint_message,
)
from ..utils.states import UserState
from ..utils.topic import TopicManager, ComplaintManager
from ...config import CAPTCHA_TTL, TIMEZONE
from ...context import Context
from ...database import UnitOfWork
from ...database.models import UserModel, ComplaintModel

logger = logging.getLogger(__name__)
router = Router()

filters = [F.chat.type.in_({ChatType.PRIVATE}), IsBannedFilter()]
router.message.filter(*filters)
router.my_chat_member.filter(*filters)


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
    text = localizer("messages.select_language")
    reply_markup = keyboards.select_language(localizer)
    msg = await message.answer(text, reply_markup=reply_markup)
    await delete_last_message_id(message.bot, state, message.chat.id)
    await save_last_message_id(state, msg.message_id)
    await state.set_state(UserState.MAIN)


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
    reply_markup = keyboards.create_button(localizer, "cancel")
    msg = await message.answer_photo(image, caption, reply_markup=reply_markup)
    await delete_last_message_id(message.bot, state, message.chat.id)
    await save_last_message_id(state, msg.message_id)

    await state.update_data(
        captcha_solution=captcha_solution,
        captcha_issued_at=int(time.time()),
    )
    await state.set_state(UserState.CAPTCHA)


async def complaint_sent_window(
    message: Message,
    state: FSMContext,
    localizer: Localizer,
    error: bool = False,
) -> None:
    state_data = await state.get_data()
    text = (
        localizer(
            "messages.complaint_sent",
            complaint_id=state_data.get("complaint_id"),
            complaint_bag_id=state_data.get("complaint_bag_id"),
        )
        if not error
        else localizer("errors.unknown")
    )
    reply_markup = keyboards.create_button(localizer, "to_main")
    msg = await message.answer(text, reply_markup=reply_markup)
    await delete_last_message_id(message.bot, state, message.chat.id)
    await save_last_message_id(state, msg.message_id)
    await state.set_state(UserState.MAIN)


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
    text = localizer("messages.select_language")
    reply_markup = keyboards.select_language(localizer)
    msg = await message.answer(text, reply_markup=reply_markup)
    await delete_last_message_id(message.bot, state, message.chat.id)
    await save_last_message_id(state, msg.message_id)


@router.message(Command("help"))
async def help_command(
    message: Message,
    state: FSMContext,
    localizer: Localizer,
) -> None:
    text = localizer("messages.help")
    msg = await message.answer(text)
    await delete_last_message_id(message.bot, state, message.chat.id)
    await save_last_message_id(state, msg.message_id)


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
    now_ts = int(time.time())
    user_answer = (message.text or "").strip()

    if issued_at is None or (now_ts - float(issued_at)) > CAPTCHA_TTL:
        await input_captcha_window(message, state, localizer, "captcha_expired")
        await delete_message(message)
        return

    if user_answer == solution:
        try:
            topic_manager = TopicManager(ctx, uow, user_model)
            await topic_manager.ensure_topic_id()

            complaint = ComplaintModel(
                user_id=user_model.user_id,
                message_thread_id=topic_manager.topic_id,
                bag_id=state_data.get("bag_id"),
                problem=state_data.get("problem"),
                created_at=datetime.now(TIMEZONE),
            )
            uow.session.add(complaint)
            await uow.session.flush()

            complaint_manager = ComplaintManager(ctx, uow, complaint)
            message_id = await complaint_manager.send_complaint()
            complaint.message_id = message_id
            await uow.complaint.upsert(complaint)

            await state.update_data(
                complaint_id=complaint.id,
                complaint_bag_id=complaint.bag_id,
            )
            await complaint_sent_window(message, state, localizer)
        except Exception as e:
            logger.exception(
                "Failed to post complaint to topic (user_id=%s, chat_id=%s): %s",
                user_model.user_id,
                message.chat.id,
                e,
            )
            await complaint_sent_window(message, state, localizer, True)
    else:
        await input_captcha_window(message, state, localizer, "captcha_wrong")

    await delete_message(message)


@router.message()
@flags.rate_limit(3)
async def message_handler(
    message: Message,
    state: FSMContext,
    localizer: Localizer,
) -> None:
    if message.content_type == ContentType.TEXT:
        complaint_data, error_code = validate_complaint_message(message.text)
        if error_code is None:
            await state.update_data(**complaint_data)
            await input_captcha_window(message, state, localizer)
            return
        else:
            await main_window(message, state, localizer, error_code)
    else:
        await main_window(message, state, localizer, "non_text")

    await delete_message(message)


@router.callback_query()
async def callback_query_handler(
    call: CallbackQuery,
    state: FSMContext,
    uow: UnitOfWork,
    localizer: Localizer,
    user_model: UserModel,
    ctx: Context,
) -> None:
    if call.data.startswith("selected_lang"):
        language_code = call.data.split(":")[1]
        user_model.language_code = language_code

        locale_data = ctx.i18n.locales_data.get(language_code)
        localizer = Localizer(locale_data)

        await uow.user.upsert(user_model)
        await main_window(call.message, state, localizer)

    elif call.data in {"to_main", "cancel"}:
        await main_window(call.message, state, localizer)

    await call.answer()


@router.my_chat_member()
async def my_chat_memeber_handler(
    update: ChatMemberUpdated,
    uow: UnitOfWork,
    user_model: UserModel,
) -> None:
    user_model.state = update.new_chat_member.status
    await uow.user.upsert(user_model)
