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
