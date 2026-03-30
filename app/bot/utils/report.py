from __future__ import annotations

import re
import typing as t
from dataclasses import dataclass, field

from aiogram.enums import ButtonStyle
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

GATEWAY_URL = "https://mytonstorage.org/api/v1/gateway/{bag_id}"

_BAG_ID_RE = re.compile(r"[a-f0-9]{64}")


def _admin_loc():
    from .i18n import Localizer
    from ...context import get_context

    return Localizer(get_context().i18n.locales_data["admin"])


@dataclass
class ReportData:
    bag_id: str
    reason: str
    reason_display: str
    problem: str
    author_mention: str
    approve_mentions: list[str] = field(default_factory=list)
    reject_mentions: list[str] = field(default_factory=list)
    status: str = "pending"
    resolved_by: str = ""
    resolved_at: str = ""


def format_report_text(data: ReportData) -> str:
    loc = _admin_loc()
    link = GATEWAY_URL.format(bag_id=data.bag_id)
    parts: list[str] = [
        loc("report.title"),
        "",
        f'{loc("report.label_bag_id")}\n<a href="{link}">{data.bag_id}</a>',
        f'{loc("report.label_reason")} {data.reason_display}',
        f'{loc("report.label_problem")}\n<blockquote>{data.problem}</blockquote>',
        "",
        f'{loc("report.label_author")} {data.author_mention}',
    ]

    if data.approve_mentions:
        parts.append(
            f'\n{loc("report.label_approve")} {", ".join(data.approve_mentions)}'
        )
    if data.reject_mentions:
        parts.append(f'{loc("report.label_reject")} {", ".join(data.reject_mentions)}')

    parts.append("")

    if data.status == "approved":
        parts.append(
            f'{loc("report.status_approved")} {data.resolved_by}\n<code>{data.resolved_at}</code>'
        )
    elif data.status == "rejected":
        parts.append(
            f'{loc("report.status_rejected")} {data.resolved_by}\n<code>{data.resolved_at}</code>'
        )
    else:
        parts.append(loc("report.status_pending"))

    return "\n".join(parts)


def _extract_after(text: str, label: str) -> t.Optional[str]:
    for line in text.split("\n"):
        stripped = line.strip()
        if stripped.startswith(label):
            return stripped[len(label) :].strip()
    return None


def _extract_blockquote(text: str) -> str:
    match = re.search(r"<blockquote>([\s\S]*?)</blockquote>", text)
    return match.group(1).strip() if match else ""


def parse_report_text(html_text: str) -> t.Optional[ReportData]:
    loc = _admin_loc()
    bag_match = _BAG_ID_RE.search(html_text)
    if not bag_match:
        return None

    reason_display = _extract_after(html_text, loc("report.label_reason"))
    problem = _extract_blockquote(html_text)
    author = _extract_after(html_text, loc("report.label_author"))

    if not reason_display or not author:
        return None

    data = ReportData(
        bag_id=bag_match.group(0),
        reason="",
        reason_display=reason_display,
        problem=problem,
        author_mention=author,
    )

    approve_raw = _extract_after(html_text, loc("report.label_approve"))
    if approve_raw:
        data.approve_mentions = [m.strip() for m in approve_raw.split(",")]

    reject_raw = _extract_after(html_text, loc("report.label_reject"))
    if reject_raw:
        data.reject_mentions = [m.strip() for m in reject_raw.split(",")]

    approved_raw = _extract_after(html_text, loc("report.status_approved"))
    rejected_raw = _extract_after(html_text, loc("report.status_rejected"))
    if approved_raw:
        data.status = "approved"
        data.resolved_by, data.resolved_at = _split_resolved(approved_raw)
    elif rejected_raw:
        data.status = "rejected"
        data.resolved_by, data.resolved_at = _split_resolved(rejected_raw)

    return data


def _split_resolved(raw: str) -> tuple[str, str]:
    match = re.search(r"<code>(.+?)</code>", raw)
    if match:
        before = raw[: match.start()].strip()
        return before, match.group(1)
    return raw.strip(), ""


def reverse_reason_key(reason_map: dict, display: str) -> str:
    for key, val in reason_map.items():
        if val == display:
            return key
    return display


def create_report_markup(reason_display: str) -> InlineKeyboardMarkup:
    loc = _admin_loc()
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=loc("report.btn_reason", reason=reason_display),
                    callback_data="change_reason",
                    style=ButtonStyle.PRIMARY,
                ),
            ],
            [
                InlineKeyboardButton(
                    text=loc("report.btn_approve"),
                    callback_data="approve",
                    style=ButtonStyle.SUCCESS,
                ),
                InlineKeyboardButton(
                    text=loc("report.btn_reject"),
                    callback_data="reject",
                    style=ButtonStyle.DANGER,
                ),
            ],
        ]
    )


def toggle_vote(mentions: list[str], mention: str) -> list[str]:
    if mention in mentions:
        return [m for m in mentions if m != mention]
    return mentions + [mention]
