from __future__ import annotations

import logging
import typing as t

logger = logging.getLogger(__name__)


class _SafeDict(dict):

    def __missing__(self, key: str) -> str:
        return "{" + key + "}"


class Localizer:

    def __init__(
        self,
        locale_data: t.Dict[str, t.Any],
    ) -> None:
        self.locale_data = locale_data

    @classmethod
    def get_nested(
        cls,
        data: t.Dict[str, t.Any],
        dotted_key: str,
        default: t.Optional[t.Any] = None,
    ) -> t.Any:
        keys = dotted_key.split(".")
        current: t.Any = data
        for key in keys:
            if isinstance(current, dict) and key in current:
                current = current[key]
            else:
                return default
        return current

    def _get_locale(self, key: str, default: t.Optional[str] = None) -> t.Optional[str]:
        if key in self.locale_data:
            return self.locale_data[key]

        result = self.get_nested(self.locale_data, key, default)
        if result is default:
            logger.info(f"Localization key not found: 'key={key}'")
        return result

    @staticmethod
    def _format(template_str: str, **kwargs: t.Any) -> str:
        try:
            return template_str.format_map(_SafeDict(kwargs))
        except (Exception,):
            return template_str

    def __call__(
        self,
        key: t.Optional[str] = None,
        *,
        default: t.Optional[str] = None,
        **kwargs: t.Any,
    ) -> str:
        if key is not None:
            template_str = self._get_locale(key)
            if template_str is None:
                logger.warning(f"Missing localization key: 'key={key}'")
                raise KeyError(f"Localization key '{key}' not found in locale data.")
        elif default is not None:
            template_str = default
        else:
            raise ValueError("Either 'key' or 'default' must be provided to Localizer.")

        return self._format(template_str, **kwargs)
