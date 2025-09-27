from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

from ..utils.i18n import Localizer
from ...config import SUPPORTED_LOCALES


def create_button(localizer: Localizer, code: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=localizer(f"buttons.{code}"),
                    callback_data=code,
                )
            ]
        ]
    )


def select_reason(localizer: Localizer) -> InlineKeyboardMarkup:
    reason_map = localizer("reason")
    inline_keyboard = [
        [
            InlineKeyboardButton(
                text=val,
                callback_data=key,
            )
        ]
        for key, val in reason_map.items()  # type: ignore
    ]
    inline_keyboard.append(
        [InlineKeyboardButton(text=localizer("buttons.back"), callback_data="back")]
    )
    return InlineKeyboardMarkup(inline_keyboard=inline_keyboard)


def select_language(localizer: Localizer) -> InlineKeyboardMarkup:
    inline_keyboard = []
    for locale in SUPPORTED_LOCALES:
        language_code = locale.lower()
        inline_keyboard.append(
            InlineKeyboardButton(
                text=localizer(f"buttons.lang.{language_code}"),
                callback_data=f"selected_lang:{language_code}",
            )
        )

    return InlineKeyboardMarkup(inline_keyboard=[inline_keyboard])
