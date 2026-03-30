from aiogram.fsm.state import StatesGroup, State


class AdminMenu(StatesGroup):
    MAIN = State()


class UsersMenu(StatesGroup):
    LIST = State()
    SEARCH = State()
    DETAIL = State()


class BagsMenu(StatesGroup):
    UNBAN = State()
    UNBAN_DETAIL = State()
    BAN = State()
    BAN_REASON = State()
    BAN_COMMENT = State()
