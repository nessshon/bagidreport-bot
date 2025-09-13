from __future__ import annotations

import asyncio
import logging
import random
import typing as t
from datetime import datetime

from aiogram import Bot
from aiogram.client.default import Default
from aiogram.exceptions import (
    TelegramRetryAfter,
    TelegramNetworkError,
    TelegramServerError,
    TelegramConflictError,
    TelegramBadRequest,
)
from aiogram.types import (
    ForumTopic,
    ReplyMarkupUnion,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    ResultChatMemberUnion,
)
from aiogram.utils import markdown

from .i18n import Localizer
from ...config import GROUP_ID, TIMEZONE
from ...context import Context
from ...database import UnitOfWork
from ...database.enums import ComplaintStatus
from ...database.models import UserTopicModel, ComplaintModel, VoteModel, UserModel

logger = logging.getLogger(__name__)


class TopicManager:
    MAX_ATTEMPTS: int = 3
    BASE_DELAY: float = 1.0

    def __init__(self, ctx: Context, uow: UnitOfWork, user_model: UserModel) -> None:
        self.uow = uow
        self.bot: Bot = ctx.bot
        self.user_model = user_model

        self.group_id: int = GROUP_ID
        self.topic_id: t.Optional[int] = None

    async def _sleep_with_backoff(
        self, attempt: int, min_delay: float | None = None
    ) -> None:
        exp = self.BASE_DELAY * (2 ** (attempt - 1))
        jitter = random.random() / 3
        delay = exp + jitter
        if min_delay is not None:
            delay = max(min_delay, delay)
        logger.warning("Retrying in %.2fs (attempt %d)", delay, attempt + 1)
        await asyncio.sleep(delay)

    async def _create_forum_topic(self, name: str) -> ForumTopic:
        return await self.bot.create_forum_topic(chat_id=self.group_id, name=name)

    async def _try_create_topic_once(self) -> int:
        existing = await self.uow.user_topic.get(user_id=self.user_model.user_id)
        if existing and existing.message_thread_id:
            return t.cast(int, existing.message_thread_id)

        name = (
            f"@{self.user_model.username}"
            if self.user_model.username
            else self.user_model.full_name
        ) or str(self.user_model.user_id)

        topic = await self._create_forum_topic(name=name)
        user_topic = await self.uow.user_topic.upsert(
            UserTopicModel(
                user_id=self.user_model.user_id,
                message_thread_id=topic.message_thread_id,
                created_at=datetime.now(TIMEZONE),
            )
        )
        return user_topic.message_thread_id

    async def create_topic(self) -> UserTopicModel:
        thread_id = await self._create_topic_with_retries()
        model = await self.uow.user_topic.get(user_id=self.user_model.user_id)
        if model is None:
            model = await self.uow.user_topic.upsert(
                UserTopicModel(
                    user_id=self.user_model.user_id,
                    message_thread_id=thread_id,
                    created_at=datetime.now(TIMEZONE),
                )
            )
        return model

    async def _create_topic_with_retries(self) -> int:
        last_err: t.Optional[BaseException] = None

        for attempt in range(1, self.MAX_ATTEMPTS + 1):
            try:
                thread_id = await self._try_create_topic_once()
                return thread_id

            except TelegramRetryAfter as e:
                logger.warning(
                    "TelegramRetryAfter: wait %.2fs (attempt %d/%d)",
                    e.retry_after,
                    attempt,
                    self.MAX_ATTEMPTS,
                )
                last_err = e
                if attempt < self.MAX_ATTEMPTS:
                    await self._sleep_with_backoff(
                        attempt, min_delay=float(e.retry_after)
                    )
                    continue
                break

            except (
                TelegramNetworkError,
                TelegramServerError,
                TelegramConflictError,
            ) as e:
                logger.warning(
                    "%s on creating topic (attempt %d/%d): %s",
                    e.__class__.__name__,
                    attempt,
                    self.MAX_ATTEMPTS,
                    e,
                )
                last_err = e
                if attempt < self.MAX_ATTEMPTS:
                    await self._sleep_with_backoff(attempt)
                    continue
                break

            except Exception as e:
                logger.exception(
                    "Unexpected error on creating topic (attempt %d/%d)",
                    attempt,
                    self.MAX_ATTEMPTS,
                )
                last_err = e
                if attempt < self.MAX_ATTEMPTS:
                    await self._sleep_with_backoff(attempt)
                    continue
                break

        assert last_err is not None
        raise last_err

    async def ensure_topic_id(self) -> None:
        existing = await self.uow.user_topic.get(user_id=self.user_model.user_id)
        if existing and existing.message_thread_id:
            self.topic_id = existing.message_thread_id
            return

        thread_id = await self._create_topic_with_retries()
        self.topic_id = thread_id

    async def send_message(
        self,
        text: str,
        parse_mode: t.Optional[t.Union[str, Default]] = Default("parse_mode"),
        disable_notification: t.Optional[bool] = None,
        reply_markup: t.Optional[ReplyMarkupUnion] = None,
        disable_web_page_preview: t.Optional[t.Union[bool, Default]] = Default(
            "link_preview_is_disabled"
        ),
        reply_to_message_id: t.Optional[int] = None,
    ) -> int:
        await self.ensure_topic_id()

        def _is_thread_missing(err: Exception) -> bool:
            s = str(err).lower()
            return "message thread not found" in s or "topic not found" in s

        for attempt in (1, 2):
            try:
                msg = await self.bot.send_message(
                    chat_id=self.group_id,
                    text=text,
                    reply_markup=reply_markup,
                    parse_mode=parse_mode,
                    disable_notification=disable_notification,
                    disable_web_page_preview=disable_web_page_preview,
                    reply_to_message_id=reply_to_message_id,
                    message_thread_id=self.topic_id,
                )
                return msg.message_id

            except TelegramRetryAfter as e:
                await asyncio.sleep(float(e.retry_after))
                msg = await self.bot.send_message(
                    chat_id=self.group_id,
                    text=text,
                    reply_markup=reply_markup,
                    parse_mode=parse_mode,
                    disable_notification=disable_notification,
                    disable_web_page_preview=disable_web_page_preview,
                    reply_to_message_id=reply_to_message_id,
                    message_thread_id=self.topic_id,
                )
                return msg.message_id

            except TelegramBadRequest as e:
                if _is_thread_missing(e) and attempt == 1:
                    await self.uow.user_topic.delete(user_id=self.user_model.user_id)
                    await self.ensure_topic_id()
                    continue
                raise

        raise RuntimeError("Failed to send message to topic after recreation")


class ComplaintManager:

    def __init__(
        self,
        ctx: Context,
        uow: UnitOfWork,
        complaint: ComplaintModel,
    ) -> None:
        self.ctx = ctx
        self.uow = uow
        self.bot: Bot = ctx.bot
        self.complaint = complaint
        self.localizer = Localizer(self.ctx.i18n.locales_data.get("group"))

        self.votes: t.List[VoteModel] = []
        self.admins: t.List[ResultChatMemberUnion] = []

    async def ensure_votes(self) -> None:
        self.votes = await self.uow.get_complaint_votes(self.complaint.id)

    async def ensure_admins(self) -> None:
        self.admins = await self.bot.get_chat_administrators(chat_id=GROUP_ID)

    @property
    def admins_ids(self) -> t.List[int]:
        return [a.user.id for a in self.admins]

    @property
    def approved_votes(self) -> t.List[VoteModel]:
        return [v for v in self.votes if v.decision == 1]

    @property
    def rejected_votes(self) -> t.List[VoteModel]:
        return [v for v in self.votes if v.decision == 0]

    @property
    def ready_for_admin(self) -> bool:
        return (
            self.complaint.status == ComplaintStatus.PENDING
            and len(self.approved_votes) >= 2
        )

    async def _create_reply_markup(self) -> InlineKeyboardMarkup:
        return InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text=self.localizer("buttons.reject"), callback_data="reject"
                    ),
                    InlineKeyboardButton(
                        text=self.localizer("buttons.approve"), callback_data="approve"
                    ),
                ],
            ]
        )

    async def _create_text(self) -> str:
        parts: t.List[str] = [
            self.localizer(
                "messages.complaint_alert",
                complaint_id=self.complaint.id,
                bag_id=self.complaint.bag_id.upper(),
                problem=markdown.hitalic(self.complaint.problem),
            )
        ]

        if self.approved_votes:
            part = self.localizer(
                "messages.complaint_approved",
                approved=self._format_votes(self.approved_votes),
            )
            parts.append(part)
        if self.rejected_votes:
            part = self.localizer(
                "messages.complaint_rejected",
                rejected=self._format_votes(self.rejected_votes),
            )
            parts.append(part)

        if self.complaint.status == ComplaintStatus.PENDING:
            part = self.localizer("messages.complaint_status_pending")
            parts.append(part)
        if self.complaint.status == ComplaintStatus.APPROVED:
            part = self.localizer(
                "messages.complaint_status_approved",
                resolved_by=await self._format_resolved_by(self.complaint.resolved_by),
                resolved_at=self._format_resolved_at(self.complaint.resolved_at),
            )
            parts.append(part)
        if self.complaint.status == ComplaintStatus.REJECTED:
            part = self.localizer(
                "messages.complaint_status_rejected",
                resolved_by=await self._format_resolved_by(self.complaint.resolved_by),
                resolved_at=self._format_resolved_at(self.complaint.resolved_at),
            )
            parts.append(part)
        return "\n".join(parts).rstrip()

    async def send_complaint(self) -> int:
        message = await self.bot.send_message(
            chat_id=GROUP_ID,
            text=await self._create_text(),
            reply_markup=await self._create_reply_markup(),
            message_thread_id=self.complaint.message_thread_id,
        )
        return message.message_id

    async def update_complaint(self) -> None:
        try:
            if self.complaint.status == ComplaintStatus.PENDING:
                reply_markup = await self._create_reply_markup()
            else:
                reply_markup = None
            await self.bot.edit_message_text(
                chat_id=GROUP_ID,
                text=await self._create_text(),
                message_id=self.complaint.message_id,
                reply_markup=reply_markup,
            )
        except TelegramBadRequest as e:
            if "message is not modified" not in e.message:
                raise

    async def ping_admins(self) -> None:
        admins = ", ".join(
            [
                admin.user.mention_html()
                for admin in self.admins
                if not admin.user.is_bot
            ]
        )
        text = self.localizer(
            "messages.complaint_waiting",
            admins=admins,
        )
        await self.bot.send_message(
            chat_id=GROUP_ID,
            text=text,
            message_thread_id=self.complaint.message_thread_id,
            reply_to_message_id=self.complaint.message_id,
        )

    def _format_status(self, status: int) -> str:
        if status == ComplaintStatus.APPROVED:
            key = "approved"
        elif status == ComplaintStatus.REJECTED:
            key = "rejected"
        else:
            key = "pending"
        return self.localizer(f"complaint_status.{key}")

    @staticmethod
    def _format_votes(votes: t.List[VoteModel]) -> str:
        if not votes:
            return ""
        return ", ".join([v.moderator.mention for v in votes])

    @staticmethod
    def _format_resolved_at(dt: datetime) -> str:
        if not dt:
            return "—"
        return dt.strftime("%Y-%m-%d %H:%M")

    async def _format_resolved_by(self, resolve_by: int) -> str:
        resolved_by = await self.uow.user.get(user_id=resolve_by)
        return resolved_by.mention
