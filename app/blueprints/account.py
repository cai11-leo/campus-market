from flask import Blueprint, flash, g, redirect, render_template, request
from werkzeug.security import check_password_hash, generate_password_hash

from .. import db
from ..i18n import t
from ..queries import fetch_favorites, fetch_history, fetch_items
from ..security import login_required, validate_password

bp = Blueprint("account", __name__)

VALID_STATUSES = ("on_sale", "sold", "unavailable")


@bp.get("/my/items")
@login_required
def my_items():
    status = request.args.get("status", "")
    if status not in VALID_STATUSES:
        status = ""
    page = request.args.get("page", 1, type=int) or 1
    result = fetch_items(
        "seller",
        seller_id=g.user["id"],
        status=status or None,
        page=page,
    )
    return render_template("my_items.html", result=result, status=status)


@bp.get("/my/favorites")
@login_required
def favorites():
    entries = []
    for row in fetch_favorites(g.user["id"]):
        if row["is_removed"] or row["status"] == "unavailable":
            state = "invalid"
        elif row["status"] == "sold":
            state = "sold"
        else:
            state = "available"
        entries.append({"item": row, "state": state})
    return render_template("favorites.html", favorites=entries)


@bp.get("/my/history")
@login_required
def history():
    return render_template("history.html", items=fetch_history(g.user["id"]))


@bp.route("/profile", methods=("GET", "POST"))
@login_required
def profile():
    errors = {}
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        contact_wechat = request.form.get("contact_wechat", "").strip()
        contact_phone = request.form.get("contact_phone", "").strip()
        current_password = request.form.get("current_password", "")
        new_password = request.form.get("new_password", "")
        confirm_password = request.form.get("confirm_password", "")

        if not 2 <= len(username) <= 30:
            errors["username"] = "auth.error.username"
        if not contact_wechat and not contact_phone:
            errors["contact"] = "auth.error.contact_required"

        changing_password = bool(
            current_password or new_password or confirm_password
        )
        if changing_password:
            if not current_password or not check_password_hash(
                g.user["password_hash"], current_password
            ):
                errors["current_password"] = "account.error.current_password"
            elif new_password != confirm_password:
                errors["new_password"] = "auth.error.password_mismatch"
            else:
                password_error = validate_password(new_password)
                if password_error:
                    errors["new_password"] = password_error

        if not errors:
            db.execute(
                "UPDATE users SET username = ?, contact_wechat = ?, "
                "contact_phone = ? WHERE id = ?",
                (
                    username,
                    contact_wechat or None,
                    contact_phone or None,
                    g.user["id"],
                ),
            )
            if changing_password:
                db.execute(
                    "UPDATE users SET password_hash = ? WHERE id = ?",
                    (generate_password_hash(new_password), g.user["id"]),
                )
            flash(t("flash.success.updated"), "success")
            return redirect("/profile")

    stats = {
        "listings": db.query_one(
            "SELECT COUNT(*) AS n FROM items WHERE seller_id = ? "
            "AND NOT (is_removed = 1 AND removed_by = 'seller')",
            (g.user["id"],),
        )["n"],
        "favorites": db.query_one(
            "SELECT COUNT(*) AS n FROM favorites WHERE user_id = ?",
            (g.user["id"],),
        )["n"],
        "sold": db.query_one(
            "SELECT COUNT(*) AS n FROM items WHERE seller_id = ? "
            "AND is_removed = 0 AND status = 'sold'",
            (g.user["id"],),
        )["n"],
    }
    return render_template("profile.html", errors=errors, stats=stats)
