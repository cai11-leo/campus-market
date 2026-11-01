from datetime import datetime

from flask import request, url_for

from .i18n import get_locale, t


def _row_get(row, key, default=""):
    try:
        value = row[key]
    except (KeyError, IndexError, TypeError):
        return default
    return default if value is None else value


def money(value) -> str:
    if value is None:
        return "—"
    return f"¥{float(value):,.2f}"


def dt(value: str) -> str:
    if not value:
        return "—"
    try:
        parsed = datetime.strptime(value, "%Y-%m-%d %H:%M:%S")
    except (TypeError, ValueError):
        return str(value)
    if get_locale() == "en":
        return f"{parsed.day} {parsed.strftime('%b %Y')}"
    return f"{parsed.year}年{parsed.month}月{parsed.day}日"


def category_name(row) -> str:
    if get_locale() == "en":
        return _row_get(
            row, "name_en", _row_get(row, "category_name_en", "")
        )
    return _row_get(
        row, "name_zh", _row_get(row, "category_name_zh", "")
    )


def status_label(status: str) -> str:
    if not status:
        return "—"
    return t(f"status.{status}")


def condition_label(condition) -> str:
    if not condition:
        return "—"
    return t(f"condition.{condition}")


def url_with_page(page: int) -> str:
    args = request.args.to_dict(flat=True)
    args["page"] = page
    return url_for(request.endpoint, **(request.view_args or {}), **args)
