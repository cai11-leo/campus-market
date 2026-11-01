import re

from flask import (
    Blueprint,
    abort,
    current_app,
    flash,
    redirect,
    render_template,
    request,
    url_for,
)

from .. import db
from ..i18n import t
from ..queries import admin_stats, fetch_categories, fetch_item, fetch_items
from ..security import admin_required

bp = Blueprint("admin", __name__, url_prefix="/admin")

VALID_STATUSES = ("on_sale", "sold", "unavailable")
VALID_ICONS = {"book", "device", "lamp", "ball", "shirt", "pen", "box"}
MAX_SQLITE_INT = 2_147_483_647


def _valid_id(value: int) -> bool:
    return isinstance(value, int) and 1 <= value <= MAX_SQLITE_INT


def _items_redirect():
    return redirect(url_for("admin.items"))


def _reports_redirect():
    return redirect(url_for("admin.reports"))


def _category_values():
    return {
        "slug": request.form.get("slug", "").strip().lower(),
        "name_zh": request.form.get("name_zh", "").strip(),
        "name_en": request.form.get("name_en", "").strip(),
        "icon": request.form.get("icon", "box").strip(),
        "sort_order": request.form.get("sort_order", "0").strip(),
    }


def _validate_category(values, category_id=None):
    errors = {}
    if not re.fullmatch(r"[a-z0-9-]{2,30}", values["slug"]):
        errors["slug"] = "admin.error.slug"
    if not 1 <= len(values["name_zh"]) <= 30:
        errors["name_zh"] = "admin.error.name"
    if not 1 <= len(values["name_en"]) <= 30:
        errors["name_en"] = "admin.error.name"
    if values["icon"] not in VALID_ICONS:
        errors["icon"] = "admin.error.icon"
    try:
        sort_order = int(values["sort_order"])
    except ValueError:
        errors["sort_order"] = "admin.error.sort"
    else:
        if not 0 <= sort_order <= 9999:
            errors["sort_order"] = "admin.error.sort"

    if not errors:
        conflict = db.query_one(
            "SELECT id FROM categories WHERE slug = ? AND id != ?",
            (values["slug"], category_id or -1),
        )
        if conflict:
            errors["slug"] = "admin.error.slug_taken"
    return errors


def _flash_category_errors(errors):
    key = next(iter(errors.values()))
    flash(t(key), "error")


@bp.get("")
@admin_required
def dashboard():
    return render_template("admin/dashboard.html", stats=admin_stats())


@bp.get("/items")
@admin_required
def items():
    q = request.args.get("q", "").strip()
    category = request.args.get("category", "").strip()
    status = request.args.get("status", "")
    if status not in VALID_STATUSES:
        status = ""
    removed = request.args.get("removed", "")
    if removed not in ("none", "admin", "seller"):
        removed = ""
    page = request.args.get("page", 1, type=int) or 1

    result = fetch_items(
        "admin",
        q=q or None,
        category_slug=category or None,
        status=status or None,
        removed=removed or None,
        page=page,
        per_page=current_app.config["ADMIN_ITEMS_PER_PAGE"],
    )
    return render_template(
        "admin/items.html",
        result=result,
        filters={
            "q": q,
            "category": category,
            "status": status,
            "removed": removed,
        },
        categories=fetch_categories(active_only=False),
    )


@bp.post("/items/<int:item_id>/remove")
@admin_required
def remove_item(item_id: int):
    reason = request.form.get("reason", "").strip()
    if not 2 <= len(reason) <= 200:
        flash(t("admin.error.reason"), "error")
        return _items_redirect()

    item = fetch_item(item_id)
    if item is None:
        abort(404)
    if item["is_removed"]:
        flash(t("admin.error.already_removed"), "info")
        return _items_redirect()

    db.execute(
        "UPDATE items SET is_removed = 1, removed_by = 'admin', "
        "removed_reason = ?, removed_at = datetime('now', 'localtime'), "
        "updated_at = datetime('now', 'localtime') WHERE id = ?",
        (reason, item_id),
    )
    flash(t("admin.flash.removed"), "success")
    return _items_redirect()


@bp.post("/items/<int:item_id>/restore")
@admin_required
def restore_item(item_id: int):
    item = fetch_item(item_id)
    if item is None:
        abort(404)
    if not item["is_removed"] or item["removed_by"] != "admin":
        flash(t("admin.error.restore_only_admin"), "error")
        return _items_redirect()

    db.execute(
        "UPDATE items SET is_removed = 0, removed_by = NULL, "
        "removed_reason = NULL, removed_at = NULL, "
        "updated_at = datetime('now', 'localtime') WHERE id = ?",
        (item_id,),
    )
    flash(t("admin.flash.restored"), "success")
    return _items_redirect()


@bp.get("/categories")
@admin_required
def categories():
    rows = fetch_categories(active_only=False)
    counts = {
        row["category_id"]: row["n"]
        for row in db.query_all(
            "SELECT category_id, COUNT(*) AS n FROM items "
            "WHERE is_removed = 0 GROUP BY category_id"
        )
    }
    return render_template(
        "admin/categories.html", categories=rows, counts=counts
    )


@bp.post("/categories")
@admin_required
def create_category():
    values = _category_values()
    errors = _validate_category(values)
    if errors:
        _flash_category_errors(errors)
        return redirect(url_for("admin.categories"))

    db.execute(
        "INSERT INTO categories (slug, name_zh, name_en, icon, sort_order, is_active) "
        "VALUES (?, ?, ?, ?, ?, 1)",
        (
            values["slug"],
            values["name_zh"],
            values["name_en"],
            values["icon"],
            int(values["sort_order"]),
        ),
    )
    flash(t("admin.flash.category_created"), "success")
    return redirect(url_for("admin.categories"))


@bp.post("/categories/<int:category_id>/edit")
@admin_required
def edit_category(category_id: int):
    if not _valid_id(category_id):
        abort(404)
    category = db.query_one(
        "SELECT * FROM categories WHERE id = ?", (category_id,)
    )
    if category is None:
        abort(404)

    values = _category_values()
    errors = _validate_category(values, category_id=category_id)
    if errors:
        _flash_category_errors(errors)
        return redirect(url_for("admin.categories"))

    db.execute(
        "UPDATE categories SET slug = ?, name_zh = ?, name_en = ?, "
        "icon = ?, sort_order = ? WHERE id = ?",
        (
            values["slug"],
            values["name_zh"],
            values["name_en"],
            values["icon"],
            int(values["sort_order"]),
            category_id,
        ),
    )
    flash(t("admin.flash.category_updated"), "success")
    return redirect(url_for("admin.categories"))


@bp.post("/categories/<int:category_id>/toggle")
@admin_required
def toggle_category(category_id: int):
    if not _valid_id(category_id):
        abort(404)
    category = db.query_one(
        "SELECT * FROM categories WHERE id = ?", (category_id,)
    )
    if category is None:
        abort(404)

    db.execute(
        "UPDATE categories SET is_active = ? WHERE id = ?",
        (0 if category["is_active"] else 1, category_id),
    )
    flash(t("admin.flash.category_toggled"), "success")
    return redirect(url_for("admin.categories"))


@bp.get("/reports")
@admin_required
def reports():
    status = request.args.get("status", "pending")
    if status not in ("pending", "resolved", "dismissed"):
        status = ""

    sql = (
        "SELECT r.*, i.title AS item_title, u.username AS reporter_name "
        "FROM reports r "
        "JOIN items i ON i.id = r.item_id "
        "JOIN users u ON u.id = r.reporter_id"
    )
    args = []
    if status:
        sql += " WHERE r.status = ?"
        args.append(status)
    sql += " ORDER BY r.created_at DESC, r.id DESC"

    return render_template(
        "admin/reports.html",
        reports=db.query_all(sql, args),
        status=status,
    )


def _update_report(report_id: int, status: str):
    if not _valid_id(report_id):
        abort(404)
    report = db.query_one("SELECT * FROM reports WHERE id = ?", (report_id,))
    if report is None:
        abort(404)
    db.execute(
        "UPDATE reports SET status = ?, "
        "handled_at = datetime('now', 'localtime') WHERE id = ?",
        (status, report_id),
    )
    return report


@bp.post("/reports/<int:report_id>/resolve")
@admin_required
def resolve_report(report_id: int):
    _update_report(report_id, "resolved")
    flash(t("admin.flash.report_resolved"), "success")
    return _reports_redirect()


@bp.post("/reports/<int:report_id>/dismiss")
@admin_required
def dismiss_report(report_id: int):
    _update_report(report_id, "dismissed")
    flash(t("admin.flash.report_dismissed"), "info")
    return _reports_redirect()


@bp.post("/reports/<int:report_id>/remove-item")
@admin_required
def remove_reported_item(report_id: int):
    if not _valid_id(report_id):
        abort(404)
    report = db.query_one("SELECT * FROM reports WHERE id = ?", (report_id,))
    if report is None:
        abort(404)

    item = fetch_item(report["item_id"])
    if item is not None and not item["is_removed"]:
        reason = f"reported: {report['reason']}"[:200]
        db.execute(
            "UPDATE items SET is_removed = 1, removed_by = 'admin', "
            "removed_reason = ?, removed_at = datetime('now', 'localtime'), "
            "updated_at = datetime('now', 'localtime') WHERE id = ?",
            (reason, item["id"]),
        )
    db.execute(
        "UPDATE reports SET status = 'resolved', "
        "handled_at = datetime('now', 'localtime') WHERE id = ?",
        (report_id,),
    )
    flash(t("admin.flash.item_removed"), "success")
    return _reports_redirect()
