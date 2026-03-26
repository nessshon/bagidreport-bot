import re
import typing as t
from contextlib import suppress

from aiogram import Bot
from aiogram.fsm.context import FSMContext
from aiogram.types import Message


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


def validate_complaint_message(
    message_text: str,
) -> t.Tuple[t.Optional[t.Dict[str, str]], t.Optional[str]]:
    lines = message_text.strip().splitlines()
    if len(lines) < 2:
        return None, "invalid_format"

    first_line = lines[0].strip()
    bag_id_re = re.compile(r"^[A-Fa-f0-9]{64}$")
    bag_id_match = bag_id_re.match(first_line)

    if not bag_id_match:
        return None, "bag_id_invalid"

    bag_id = first_line.lower()
    problem = "\n".join(lines[1:]).strip()

    if (
        not problem
        or len(problem.split()) < 3
        or (problem.startswith("<") and problem.endswith(">"))
    ):
        return None, "problem_required"

    if len(problem) > 2048:
        return None, "problem_too_long"

    return {"bag_id": bag_id, "problem": problem}, None
