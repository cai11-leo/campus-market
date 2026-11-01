import hmac
import re
import secrets
from functools import wraps
from urllib.parse import unquote, urlsplit

from flask import abort, flash, g, redirect, request, session, url_for

from . import db
from .i18n import t


def get_current_user():
    user_id = session.get("user_id")
    if not user_id:
        return None
    user = db.query_one(
        "SELECT * FROM users WHERE id = ? AND is_active = 1", (user_id,)
    )
    if user is None:
        session.pop("user_id", None)
    return user


def csrf_token() -> str:
    return session.get("csrf_token", "")


def safe_next_url(target: str | None) -> str | None:
    """Return a safe same-site redirect target, or None.

    Rejects absolute URLs, protocol-relative URLs, backslashes, control
    characters, and percent-encoded variants of those (including a decoded
    leading ``//``), which would otherwise turn into an open redirect.
    """
    if not target:
        return None

    def has_control(value: str) -> bool:
        return any(ord(char) < 0x20 or ord(char) == 0x7F for char in value)

    if has_control(target) or "\\" in target:
        return None
    if re.search(r"%(?:0[0-9a-f]|7f)", target, re.IGNORECASE):
        return None

    decoded = unquote(target)
    if has_control(decoded) or "\\" in decoded:
        return None
    if decoded.startswith("//"):
        return None

    parts = urlsplit(decoded)
    if parts.scheme or parts.netloc:
        return None
    if not parts.path.startswith("/") or parts.path.startswith("//"):
        return None
    return target


def validate_password(password: str) -> str | None:
    if (
        len(password) < 8
        or not re.search(r"[A-Za-z]", password)
        or not re.search(r"\d", password)
    ):
        return "auth.error.password_weak"
    return None


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if getattr(g, "user", None) is None:
            flash(t("flash.login_required"), "info")
            return redirect(url_for("auth.login", next=request.full_path))
        return view(*args, **kwargs)

    return wrapped


def admin_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        user = getattr(g, "user", None)
        if user is None:
            flash(t("flash.login_required"), "info")
            return redirect(url_for("auth.login", next=request.full_path))
        if user["role"] != "admin":
            abort(403)
        return view(*args, **kwargs)

    return wrapped


def init_app(app) -> None:
    @app.before_request
    def load_user():
        if request.endpoint == "static":
            g.user = None
        else:
            g.user = get_current_user()
        if "csrf_token" not in session:
            session["csrf_token"] = secrets.token_hex(16)

    @app.before_request
    def verify_csrf():
        if request.method != "POST":
            return None
        expected = session.get("csrf_token", "")
        submitted = request.form.get("csrf_token", "")
        if (
            not expected
            or not submitted
            or not hmac.compare_digest(expected, submitted)
        ):
            abort(400)
        return None
