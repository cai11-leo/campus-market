import os
import re
import secrets

from flask import (
    Blueprint,
    flash,
    redirect,
    render_template,
    request,
    session,
    url_for,
)
from werkzeug.security import check_password_hash, generate_password_hash

from .. import db
from ..i18n import t
from ..security import safe_next_url, validate_password

bp = Blueprint("auth", __name__)


def _reset_session(user_id: int) -> None:
    lang = session.get("lang", "zh")
    session.clear()
    session["lang"] = lang
    session["user_id"] = user_id
    session["csrf_token"] = secrets.token_hex(16)


@bp.route("/register", methods=("GET", "POST"))
def register():
    errors = {}
    if request.method == "POST":
        student_id = request.form.get("student_id", "").strip()
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        confirm_password = request.form.get("confirm_password", "")
        contact_wechat = request.form.get("contact_wechat", "").strip()
        contact_phone = request.form.get("contact_phone", "").strip()

        if not re.fullmatch(r"[A-Za-z0-9]{4,20}", student_id):
            errors["student_id"] = "auth.error.invalid_student_id"
        if not 2 <= len(username) <= 30:
            errors["username"] = "auth.error.username"
        if password != confirm_password:
            errors["confirm_password"] = "auth.error.password_mismatch"
        password_error = validate_password(password)
        if password_error:
            errors["password"] = password_error
        if not contact_wechat and not contact_phone:
            errors["contact"] = "auth.error.contact_required"
        if not errors and db.query_one(
            "SELECT id FROM users WHERE student_id = ?", (student_id,)
        ):
            errors["student_id"] = "auth.error.student_id_taken"

        if not errors:
            user_id = db.execute(
                "INSERT INTO users "
                "(student_id, username, password_hash, contact_wechat, "
                "contact_phone, role, created_at) "
                "VALUES (?, ?, ?, ?, ?, 'student', datetime('now', 'localtime'))",
                (
                    student_id,
                    username,
                    generate_password_hash(password),
                    contact_wechat or None,
                    contact_phone or None,
                ),
            )
            _reset_session(user_id)
            flash(t("auth.flash.welcome", name=username), "success")
            return redirect(url_for("main.index"))

    return render_template("register.html", errors=errors)


@bp.route("/login", methods=("GET", "POST"))
def login():
    error = None
    next_target = safe_next_url(
        request.form.get("next") or request.args.get("next")
    )
    if request.method == "POST":
        student_id = request.form.get("student_id", "").strip()
        password = request.form.get("password", "")
        user = db.query_one(
            "SELECT * FROM users WHERE student_id = ? AND is_active = 1",
            (student_id,),
        )
        share_admin_hash = os.environ.get("CAMPUS_SHARE_ADMIN_HASH")
        valid = False
        if user is not None:
            try:
                if student_id == "admin" and share_admin_hash:
                    valid = check_password_hash(share_admin_hash, password)
                else:
                    valid = check_password_hash(user["password_hash"], password)
            except (TypeError, ValueError):
                valid = False
        if not valid:
            error = "auth.error.invalid_credentials"
        else:
            _reset_session(user["id"])
            return redirect(next_target or url_for("main.index"))

    return render_template("login.html", error=error, next=next_target or "")


@bp.post("/logout")
def logout():
    lang = session.get("lang", "zh")
    session.clear()
    session["lang"] = lang
    session["csrf_token"] = secrets.token_hex(16)
    flash(t("auth.flash.logged_out"), "info")
    return redirect(url_for("main.index"))
