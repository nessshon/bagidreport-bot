from __future__ import annotations

import typing as t
from pathlib import Path
from zoneinfo import ZoneInfo

from environs import Env

ENV = Env()
ENV.read_env()

BASE_DIR = Path(__file__).resolve().parent
TIMEZONE = ZoneInfo(ENV.str("TIMEZONE", "UTC"))

LOCALES_DIR: Path = BASE_DIR.parent / "locales"
DEFAULT_LOCALE: str = ENV.str("DEFAULT_LOCALE", "en")
SUPPORTED_LOCALES: t.List[str] = ENV.list("SUPPORTED_LOCALES", default=[DEFAULT_LOCALE])

DEV_ID: int = ENV.int("DEV_ID")
GROUP_ID: int = ENV.int("GROUP_ID")
ADMIN_IDS: list = ENV.list("ADMIN_IDS", subcast=int, default=[])

DB_URL = ENV.str("DB_URL")
REDIS_URL = ENV.str("REDIS_URL")

BOT_TOKEN: str = ENV.str("BOT_TOKEN")

CAPTCHA_TTL: int = 2 * 60

MYTONSTORAGE_REPORTS_KEY: str = ENV.str("MYTONSTORAGE_REPORTS_KEY")
MYTONSTORAGE_BANS_KEY: str = ENV.str("MYTONSTORAGE_BANS_KEY")
ADMIN_IDS_SET: set = set(ADMIN_IDS) | {DEV_ID}
