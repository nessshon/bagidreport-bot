from aiogram.enums import ContentType
from aiogram_dialog import Window
from aiogram_dialog.widgets import kbd
from aiogram_dialog.widgets.input import MessageInput

from . import getters, handlers, keyboards, on_clicks, states
from .widgets import AdminText, AdminError

admin_main = Window(
    AdminText("messages.panel.main"),
    keyboards.admin_menu,
    getter=getters.admin_menu,
    state=states.AdminMenu.MAIN,
)

users_list_window = Window(
    AdminText("messages.panel.users.title"),
    keyboards.users_list_menu,
    getter=getters.users_list,
    state=states.UsersMenu.LIST,
)

users_search_window = Window(
    AdminText("messages.panel.users.search"),
    AdminError(),
    MessageInput(func=handlers.search_user, content_types=[ContentType.TEXT]),
    kbd.SwitchTo(
        AdminText("buttons.back"), id="search_user_back", state=states.UsersMenu.LIST
    ),
    getter=getters.search_user,
    state=states.UsersMenu.SEARCH,
)

user_detail_window = Window(
    AdminText("messages.panel.users.detail"),
    keyboards.user_detail_menu,
    getter=getters.user_detail,
    state=states.UsersMenu.DETAIL,
)

unban_bag_window = Window(
    AdminText("messages.panel.unban_bag"),
    AdminError(),
    MessageInput(func=handlers.unban_bag_input, content_types=[ContentType.TEXT]),
    kbd.Button(
        AdminText("buttons.back"), id="unban_bag_back", on_click=on_clicks.close_admin
    ),
    getter=getters.unban_bag,
    state=states.BagsMenu.UNBAN,
)

unban_bag_detail_window = Window(
    AdminText("messages.panel.unban_bag_detail"),
    keyboards.unban_bag_detail_menu,
    getter=getters.unban_bag_detail,
    state=states.BagsMenu.UNBAN_DETAIL,
)

ban_create_window = Window(
    AdminText("messages.panel.create_ban"),
    AdminError(),
    MessageInput(func=handlers.create_ban_input, content_types=[ContentType.TEXT]),
    kbd.Button(
        AdminText("buttons.back"), id="create_ban_back", on_click=on_clicks.close_admin
    ),
    getter=getters.create_ban,
    state=states.BagsMenu.BAN,
)

ban_create_reason_window = Window(
    AdminText("messages.panel.create_ban_reason"),
    keyboards.create_ban_reason_menu,
    state=states.BagsMenu.BAN_REASON,
)

ban_create_comment_window = Window(
    AdminText("messages.panel.create_ban_comment"),
    MessageInput(func=handlers.create_ban_comment, content_types=[ContentType.TEXT]),
    kbd.Button(
        AdminText("buttons.skip"),
        id="skip_comment",
        on_click=on_clicks.skip_create_ban_comment,
    ),
    kbd.SwitchTo(
        AdminText("buttons.back"),
        id="comment_back",
        state=states.BagsMenu.BAN_REASON,
    ),
    state=states.BagsMenu.BAN_COMMENT,
)
