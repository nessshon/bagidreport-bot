import re
import typing as t
from contextlib import suppress

from aiogram import Bot
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

_BAG_ID_HEX = re.compile(r"[A-Fa-f0-9]{64}")
_GATEWAY_URL = re.compile(
    r"https?://(?:www\.)?mytonstorage\.org/api/v\d+/gateway/([A-Fa-f0-9]{64})"
)


def extract_bag_id(text: str) -> t.Optional[str]:
    text = text.strip()
    url_match = _GATEWAY_URL.search(text)
    if url_match:
        return url_match.group(1).lower()
    hex_match = _BAG_ID_HEX.fullmatch(text)
    if hex_match:
        return text.lower()
    return None


async def delete_message(message: Message) -> None:
    with suppress(Exception):
        await message.delete()


async def delete_last_message_id(bot: Bot, state: FSMContext, chat_id: int) -> None:
    state_data = await state.get_data()
    last_message_id = state_data.get("last_message_id")
    if last_message_id is not None:
        with suppress(Exception):
            await bot.delete_message(chat_id=chat_id, message_id=last_message_id)


async def save_last_message_id(state: FSMContext, message_id: int) -> None:
    await state.update_data(last_message_id=message_id)


def validate_report_message(
    message_text: str,
) -> t.Tuple[t.Optional[t.Dict[str, str]], t.Optional[str]]:
    lines = message_text.strip().splitlines()
    if len(lines) < 2:
        return None, "invalid_format"

    first_line = lines[0].strip()
    bag_id = extract_bag_id(first_line)

    if bag_id is None:
        return None, "bag_id_invalid"

    problem = "\n".join(lines[1:]).strip()

    if (
        not problem
        or len(problem.split()) < 3
        or (problem.startswith("<") and problem.endswith(">"))
    ):
        return None, "problem_required"

    if len(problem) > 1024:
        return None, "problem_too_long"

    return {"bag_id": bag_id, "problem": problem}, None
