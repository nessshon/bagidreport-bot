import logging
from datetime import datetime

from aiogram import Router, F
from aiogram.enums import ChatType
from aiogram.filters import (
    Command,
    CommandObject,
)
from aiogram.types import (
    Message,
    CallbackQuery,
)
from aiogram.utils.markdown import hcode

from app.bot.utils.i18n import Localizer
from app.bot.utils.topic import ComplaintManager
from app.config import GROUP_ID, TIMEZONE
from app.context import Context
from app.database import UnitOfWork
from app.database.enums import VoteDecision, ComplaintStatus
from app.database.models import UserModel, VoteModel, ComplaintModel

logger = logging.getLogger(__name__)
router = Router()


@router.message(Command("id"))
async def group_id_command(message: Message) -> None:
    text = hcode(message.chat.id)
    await message.reply(text)


router.message.filter(
    *[
        F.chat.id == GROUP_ID,
        F.chat.type.in_({ChatType.GROUP, ChatType.SUPERGROUP}),
    ]
)
router.callback_query.filter(
    *[
        F.message.chat.id == GROUP_ID,
        F.message.chat.type.in_({ChatType.GROUP, ChatType.SUPERGROUP}),
    ]
)


@router.message(Command("info"))
async def info_command(
    message: Message,
    uow: UnitOfWork,
    localizer: Localizer,
) -> None:
    user_topic = await uow.user_topic.get(message_thread_id=message.message_thread_id)
    user = await uow.user.get(user_id=user_topic.user_id)
    if user_topic is None or user is None:
        return

    text = localizer(
        "messages.command_info",
        user_id=user.user_id,
        username=user.mention,
        full_name=user.full_name,
        language_code=user.language_code,
        state=localizer(f"common.state.{user.state}"),
        is_banned=localizer(f"common.banned._{user.is_banned}"),
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
    user_topic = await uow.user_topic.get(message_thread_id=message.message_thread_id)
    user = await uow.user.get(user_id=user_topic.user_id)
    if user_topic is None or user is None:
        return

    text = localizer(
        f"messages.command_{command.command}",
        user_mention=user.mention,
    )
    user.is_banned = True if command.command == "ban" else False
    await uow.user.upsert(user)
    await message.reply(text=text)


async def update_vote_status(
    uow: UnitOfWork,
    complaint: ComplaintModel,
    user_model: UserModel,
    decision: VoteDecision,
):
    existing = await uow.vote.get(
        complaint_id=complaint.id,
        moderator_id=user_model.user_id,
    )

    if existing:
        if existing.decision == decision:
            await uow.vote.delete(
                complaint_id=complaint.id,
                moderator_id=user_model.user_id,
            )
        else:
            await uow.vote.update(
                filters={
                    "complaint_id": complaint.id,
                    "moderator_id": user_model.user_id,
                },
                values={
                    "decision": decision,
                    "created_at": datetime.now(TIMEZONE),
                },
            )
    else:
        await uow.vote.create(
            VoteModel(
                complaint_id=complaint.id,
                moderator_id=user_model.user_id,
                decision=decision,
                created_at=datetime.now(TIMEZONE),
            )
        )

    await uow.session.flush()


@router.callback_query()
async def callback_query_handler(
    call: CallbackQuery,
    ctx: Context,
    user_model: UserModel,
    uow: UnitOfWork,
) -> None:
    message_id = call.message.message_id
    complaint = await uow.complaint.get(message_id=message_id)

    if complaint is None:
        await call.answer()
        return

    complaint_manager = ComplaintManager(ctx, uow, complaint)
    await complaint_manager.ensure_admins()

    if call.data in {"approve", "reject"}:
        if call.data == "approve":
            decision = VoteDecision.APPROVE
        else:
            decision = VoteDecision.REJECT

        if user_model.user_id not in complaint_manager.admins_ids:
            await update_vote_status(uow, complaint, user_model, decision)
            await complaint_manager.ensure_votes()
            if complaint_manager.ready_for_admin:
                await complaint_manager.ping_admins()

        else:
            await complaint_manager.ensure_votes()
            now = datetime.now(TIMEZONE)
            complaint.resolved_by = user_model.user_id
            complaint.resolved_at = now
            if decision == VoteDecision.APPROVE:
                complaint.status = ComplaintStatus.APPROVED
            else:
                complaint.status = ComplaintStatus.REJECTED
            complaint.updated_at = now
            await uow.complaint.upsert(complaint)
            complaint_manager.complaint = complaint

        await complaint_manager.update_complaint()
    await call.answer()
