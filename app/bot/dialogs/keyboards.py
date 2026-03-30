from aiogram import F
from aiogram.enums import ButtonStyle
from aiogram_dialog.widgets import kbd
from aiogram_dialog.widgets.style import Style
from aiogram_dialog.widgets.text import Const, Format

from . import on_clicks, states
from .consts import USERS_TABS, REASON_KEYS
from .widgets import AdminText

admin_menu = kbd.Group(
    kbd.Start(
        AdminText("buttons.manage_users"),
        id="to_users",
        state=states.UsersMenu.LIST,
        style=Style(style=ButtonStyle.PRIMARY),
    ),
    kbd.Row(
        kbd.Start(
            AdminText("buttons.unban_bag_menu"),
            id="to_unban_bag",
            state=states.BagsMenu.UNBAN,
            style=Style(style=ButtonStyle.SUCCESS),
        ),
        kbd.Start(
            AdminText("buttons.create_ban"),
            id="to_create_ban",
            state=states.BagsMenu.BAN,
            style=Style(style=ButtonStyle.DANGER),
        ),
    ),
    kbd.Button(
        AdminText("buttons.close"),
        id="hide_admin",
        on_click=on_clicks.hide_admin,
    ),
)

users_list_menu = kbd.Group(
    kbd.Group(
        kbd.Radio(
            checked_text=Const("• ") + AdminText("tabs.users.{item}"),
            unchecked_text=AdminText("tabs.users.{item}"),
            id="users_tab",
            item_id_getter=lambda x: x,
            items=USERS_TABS,
            on_click=on_clicks.change_users_tab,
            checked_style=Style(style=ButtonStyle.PRIMARY),
        ),
        width=2,
    ),
    kbd.Column(
        kbd.Select(
            Format("{item[label]}"),
            id="select_user",
            item_id_getter=lambda item: item["id"],
            items="user_items",
            on_click=on_clicks.select_user,
        ),
    ),
    kbd.Group(
        kbd.Select(
            Format("{item[label]}"),
            id="users_page",
            item_id_getter=lambda item: item["id"],
            items="pagination_items",
            on_click=on_clicks.change_users_page,
        ),
        width=5,
    ),
    kbd.Row(
        kbd.Button(
            AdminText("buttons.back"), id="users_back", on_click=on_clicks.close_admin
        ),
        kbd.SwitchTo(
            AdminText("buttons.search"),
            id="users_search",
            state=states.UsersMenu.SEARCH,
        ),
    ),
)

user_detail_menu = kbd.Column(
    kbd.CopyText(
        AdminText("buttons.copy_user_id"),
        copy_text=Format("{user_id}"),
    ),
    kbd.Button(
        AdminText("buttons.ban"),
        id="ban_user",
        on_click=on_clicks.toggle_user_ban,
        when=~F["is_banned"],
        style=Style(style=ButtonStyle.DANGER),
    ),
    kbd.Button(
        AdminText("buttons.unban"),
        id="unban_user",
        on_click=on_clicks.toggle_user_ban,
        when=F["is_banned"],
        style=Style(style=ButtonStyle.SUCCESS),
    ),
    kbd.SwitchTo(
        AdminText("buttons.back"), id="user_back_to_list", state=states.UsersMenu.LIST
    ),
)

unban_bag_detail_menu = kbd.Column(
    kbd.CopyText(
        AdminText("buttons.copy_bag_id"),
        copy_text=Format("{bag_id}"),
    ),
    kbd.Url(
        AdminText("buttons.open_mytonstorage"),
        url=Format("https://mytonstorage.org/api/v1/gateway/{bag_id}"),
        id="open_bag",
    ),
    kbd.Button(
        AdminText("buttons.unban_bag"),
        id="unban_bag",
        on_click=on_clicks.unban_bag,
        when=F["ban_found"].is_(True),
        style=Style(style=ButtonStyle.SUCCESS),
    ),
    kbd.SwitchTo(
        AdminText("buttons.back"), id="unban_back", state=states.BagsMenu.UNBAN
    ),
)

create_ban_reason_menu = kbd.Column(
    kbd.Select(
        AdminText("reason.{item}"),
        id="select_create_ban_reason",
        item_id_getter=lambda x: x,
        items=REASON_KEYS,
        on_click=on_clicks.create_ban_reason,
    ),
    kbd.SwitchTo(
        AdminText("buttons.back"), id="create_ban_back", state=states.BagsMenu.BAN
    ),
)
