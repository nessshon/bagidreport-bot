from aiogram.fsm.state import StatesGroup, State


class UserState(StatesGroup):
    MAIN = State()
    CAPTCHA = State()
