import math
import time

from flask import (
    Blueprint,
    abort,
    current_app,
    flash,
    g,
    redirect,
    render_template,
    request,
    session,
    url_for,
)

from .. import db
from ..i18n import t
from ..permissions import item_access_mode
from ..queries import (
    fetch_categories,
    fetch_category_by_slug,
    fetch_item,
    fetch_item_images,
    fetch_items,
)
from ..security import login_required, safe_next_url
from ..uploads import delete_image, save_image, validate_image

bp = Blueprint("items", __name__)

VALID_SORTS = ("latest", "price_asc", "price_desc", "views")
VALID_CONDITIONS = ("new", "like_new", "good", "fair")
VALID_STATUSES = ("on_sale", "sold", "unavailable")


def _parse_filters():
    q = request.args.get("q", "").strip()
    category = request.args.get("category", "").strip()
    status = request.args.get("status", "").strip()
    if status not in ("on_sale", "sold"):
        status = ""
    sort = request.args.get("sort", "latest")
    if sort not in VALID_SORTS:
        sort = "latest"
    page = request.args.get("page", 1, type=int) or 1
    return {
        "q": q,
        "category": category,
        "status": status,
        "sort": sort,
        "page": page,
    }


def _render_list(active_category=None):
    filters = _parse_filters()
    category_slug = active_category["slug"] if active_category else filters["category"]
    result = fetch_items(
        "public",
        q=filters["q"] or None,
        category_slug=category_slug or None,
        status=filters["status"] or None,
        sort=filters["sort"],
        page=filters["page"],
        per_page=current_app.config["ITEMS_PER_PAGE"],
    )
    return render_template(
        "items.html",
        result=result,
        filters=filters,
        categories=fetch_categories(),
        active_category=active_category,
    )


@bp.get("/items")
def list_items():
    return _render_list()


@bp.get("/category/<slug>")
def category(slug: str):
    active = fetch_category_by_slug(slug)
    if active is None:
        abort(404)
    return _render_list(active_category=active)


def _record_view(item_id: int) -> bool:
    now = time.time()
    viewed = {
        key: timestamp
        for key, timestamp in session.get("viewed", {}).items()
        if isinstance(timestamp, (int, float)) and now - timestamp <= 1800
    }
    key = str(item_id)
    last = viewed.get(key)
    if last and now - last <= 1800:
        return False
    db.execute(
        "UPDATE items SET view_count = view_count + 1 WHERE id = ?", (item_id,)
    )
    viewed[key] = now
    session["viewed"] = viewed
    session.modified = True
    return True


def _record_history(user_id: int, item_id: int) -> None:
    db.execute(
        "INSERT INTO browse_history (user_id, item_id, viewed_at) "
        "VALUES (?, ?, datetime('now', 'localtime')) "
        "ON CONFLICT(user_id, item_id) "
        "DO UPDATE SET viewed_at = excluded.viewed_at",
        (user_id, item_id),
    )


@bp.get("/item/<int:item_id>")
def detail(item_id: int):
    item = fetch_item(item_id)
    user = getattr(g, "user", None)
    mode = item_access_mode(item, user)
    if mode == "denied":
        abort(404)

    images = fetch_item_images(item_id)
    viewed = False
    if mode == "full" and (user is None or user["id"] != item["seller_id"]):
        viewed = _record_view(item_id)
        if viewed:
            item = fetch_item(item_id)

    if (
        mode == "full"
        and user is not None
        and user["id"] != item["seller_id"]
    ):
        _record_history(user["id"], item_id)

    contact_allowed = user is not None and (
        item["status"] == "on_sale"
        or user["id"] == item["seller_id"]
        or user["role"] == "admin"
    )
    is_favorited = False
    if user is not None:
        is_favorited = db.query_one(
            "SELECT 1 FROM favorites WHERE user_id = ? AND item_id = ?",
            (user["id"], item_id),
        ) is not None

    can_manage = (
        mode in ("full", "paused_owner")
        and user is not None
        and (user["id"] == item["seller_id"] or user["role"] == "admin")
    )

    return render_template(
        "item_detail.html",
        item=item,
        images=images,
        mode=mode,
        contact_allowed=contact_allowed,
        is_favorited=is_favorited,
        can_manage=can_manage,
        view_count=item["view_count"],
    )


def _default_values():
    return {
        "title": "",
        "category_id": "",
        "price": "",
        "original_price": "",
        "condition": "",
        "trade_location": "",
        "description": "",
    }


def _form_values():
    return {
        key: request.form.get(key, "").strip()
        for key in (
            "title",
            "category_id",
            "price",
            "original_price",
            "condition",
            "trade_location",
            "description",
        )
    }


def _values_from_item(item):
    original = item["original_price"]
    return {
        "title": item["title"],
        "category_id": str(item["category_id"]),
        "price": f"{item['price']:g}",
        "original_price": f"{original:g}" if original is not None else "",
        "condition": item["condition"] or "",
        "trade_location": item["trade_location"] or "",
        "description": item["description"],
    }


def _parse_price(raw):
    try:
        value = float(raw)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(value) or value < 0 or value > 99999:
        return None
    return value


def _validate_values(values, allowed_category_id=None):
    errors = {}
    if not 2 <= len(values["title"]) <= 60:
        errors["title"] = "items.error.title"
    if not 5 <= len(values["description"]) <= 2000:
        errors["description"] = "items.error.description"

    price = _parse_price(values["price"])
    if price is None:
        errors["price"] = "items.error.price"

    original = None
    if values["original_price"]:
        original = _parse_price(values["original_price"])
        if original is None:
            errors["original_price"] = "items.error.price"

    if values["condition"] and values["condition"] not in VALID_CONDITIONS:
        errors["condition"] = "items.error.condition"

    category_id = None
    try:
        category_id = int(values["category_id"])
    except (TypeError, ValueError):
        errors["category_id"] = "items.error.category"
    else:
        if not 1 <= category_id <= 2_147_483_647:
            errors["category_id"] = "items.error.category"
        elif category_id != allowed_category_id and db.query_one(
            "SELECT id FROM categories WHERE id = ? AND is_active = 1",
            (category_id,),
        ) is None:
            errors["category_id"] = "items.error.category"

    if len(values["trade_location"]) > 60:
        errors["trade_location"] = "items.error.location"

    return errors, price, original, category_id


def _uploaded_images():
    return [f for f in request.files.getlist("images") if f and f.filename]


def _image_error(files):
    max_images = current_app.config["MAX_IMAGES"]
    if not 1 <= len(files) <= max_images:
        return "items.error.images_count"
    for file_storage in files:
        if validate_image(file_storage) is not None:
            return "items.error.image_invalid"
    return None


@bp.route("/publish", methods=("GET", "POST"))
@login_required
def publish():
    values = _default_values()
    errors = {}

    if request.method == "POST":
        user = g.user
        if not user["contact_wechat"] and not user["contact_phone"]:
            flash(t("items.error.contact_required"), "error")
            return redirect("/profile")

        values = _form_values()
        errors, price, original, category_id = _validate_values(values)
        files = _uploaded_images()
        image_error = _image_error(files)
        if image_error:
            errors["images"] = image_error

        if not errors:
            saved = []
            try:
                for file_storage in files:
                    saved.append(save_image(file_storage))
                item_id = db.execute(
                    "INSERT INTO items "
                    "(seller_id, category_id, title, description, price, "
                    "original_price, condition, trade_location, status, "
                    "created_at, updated_at) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'on_sale', "
                    "datetime('now', 'localtime'), datetime('now', 'localtime'))",
                    (
                        user["id"],
                        category_id,
                        values["title"],
                        values["description"],
                        price,
                        original,
                        values["condition"] or None,
                        values["trade_location"] or None,
                    ),
                )
                for index, path in enumerate(saved):
                    db.execute(
                        "INSERT INTO item_images (item_id, filename, sort_order) "
                        "VALUES (?, ?, ?)",
                        (item_id, path, index),
                    )
            except Exception:
                for path in saved:
                    delete_image(path)
                raise

            flash(t("flash.success.published"), "success")
            return redirect(url_for("items.detail", item_id=item_id))

    return render_template(
        "publish.html",
        values=values,
        errors=errors,
        categories=fetch_categories(),
    )


@bp.route("/item/<int:item_id>/edit", methods=("GET", "POST"))
@login_required
def edit(item_id: int):
    item = fetch_item(item_id)
    if item is None:
        abort(404)
    user = g.user
    if user["id"] != item["seller_id"] and user["role"] != "admin":
        abort(403)
    if item["is_removed"]:
        abort(403)

    images = fetch_item_images(item_id)
    values = _values_from_item(item)
    errors = {}

    categories = fetch_categories()
    if not any(
        category["id"] == item["category_id"] for category in categories
    ):
        current_category = db.query_one(
            "SELECT * FROM categories WHERE id = ?", (item["category_id"],)
        )
        if current_category is not None:
            categories.append(current_category)

    if request.method == "POST":
        values = _form_values()
        errors, price, original, category_id = _validate_values(
            values, allowed_category_id=item["category_id"]
        )
        existing_ids = {image["id"] for image in images}
        remove_ids = [
            int(raw)
            for raw in request.form.getlist("remove_images")
            if raw.isdigit() and int(raw) in existing_ids
        ]
        new_files = _uploaded_images()
        max_images = current_app.config["MAX_IMAGES"]
        total = len(existing_ids) - len(remove_ids) + len(new_files)

        if not 1 <= total <= max_images:
            errors.setdefault("images", "items.error.images_count")
        else:
            for file_storage in new_files:
                if validate_image(file_storage) is not None:
                    errors.setdefault("images", "items.error.image_invalid")
                    break

        if not errors:
            saved = []
            try:
                db.execute(
                    "UPDATE items SET category_id = ?, title = ?, description = ?, "
                    "price = ?, original_price = ?, condition = ?, "
                    "trade_location = ?, updated_at = datetime('now', 'localtime') "
                    "WHERE id = ?",
                    (
                        category_id,
                        values["title"],
                        values["description"],
                        price,
                        original,
                        values["condition"] or None,
                        values["trade_location"] or None,
                        item_id,
                    ),
                )
                for image_id in remove_ids:
                    image = next(
                        (row for row in images if row["id"] == image_id), None
                    )
                    if image:
                        db.execute(
                            "DELETE FROM item_images WHERE id = ?", (image_id,)
                        )
                        delete_image(image["filename"])

                max_sort = max(
                    (
                        image["sort_order"]
                        for image in images
                        if image["id"] not in remove_ids
                    ),
                    default=-1,
                )
                for offset, file_storage in enumerate(new_files):
                    path = save_image(file_storage)
                    saved.append(path)
                    db.execute(
                        "INSERT INTO item_images (item_id, filename, sort_order) "
                        "VALUES (?, ?, ?)",
                        (item_id, path, max_sort + 1 + offset),
                    )
            except Exception:
                for path in saved:
                    delete_image(path)
                raise

            flash(t("flash.success.updated"), "success")
            return redirect(url_for("items.detail", item_id=item_id))

    return render_template(
        "edit_item.html",
        item=item,
        images=images,
        values=values,
        errors=errors,
        categories=categories,
    )


@bp.post("/item/<int:item_id>/status")
@login_required
def update_status(item_id: int):
    item = fetch_item(item_id)
    if item is None:
        abort(404)
    if g.user["id"] != item["seller_id"]:
        abort(403)
    if item["is_removed"]:
        abort(403)

    status = request.form.get("status", "")
    if status not in VALID_STATUSES:
        abort(400)

    db.execute(
        "UPDATE items SET status = ?, updated_at = datetime('now', 'localtime') "
        "WHERE id = ?",
        (status, item_id),
    )
    flash(t("flash.success.status"), "success")
    target = safe_next_url(request.form.get("next")) or url_for(
        "items.detail", item_id=item_id
    )
    return redirect(target)


@bp.post("/item/<int:item_id>/delete")
@login_required
def delete(item_id: int):
    item = fetch_item(item_id)
    if item is None:
        abort(404)
    if g.user["id"] != item["seller_id"]:
        abort(403)

    if item["is_removed"]:
        flash(t("items.error.already_removed"), "info")
        return redirect("/my/items")

    db.execute(
        "UPDATE items SET is_removed = 1, removed_by = 'seller', "
        "removed_reason = 'seller_deleted', "
        "removed_at = datetime('now', 'localtime'), "
        "updated_at = datetime('now', 'localtime') WHERE id = ?",
        (item_id,),
    )
    flash(t("flash.success.deleted"), "success")
    return redirect("/items")


@bp.post("/item/<int:item_id>/favorite")
@login_required
def toggle_favorite(item_id: int):
    item = fetch_item(item_id)
    if item is None:
        abort(404)

    existing = db.query_one(
        "SELECT 1 FROM favorites WHERE user_id = ? AND item_id = ?",
        (g.user["id"], item_id),
    )
    if existing:
        db.execute(
            "DELETE FROM favorites WHERE user_id = ? AND item_id = ?",
            (g.user["id"], item_id),
        )
        flash(t("flash.success.unfavorited"), "success")
    elif item["is_removed"] or item["status"] != "on_sale":
        flash(t("items.error.favorite_unavailable"), "info")
    else:
        db.execute(
            "INSERT INTO favorites (user_id, item_id, created_at) "
            "VALUES (?, ?, datetime('now', 'localtime'))",
            (g.user["id"], item_id),
        )
        flash(t("flash.success.favorited"), "success")

    target = safe_next_url(request.form.get("next")) or url_for(
        "items.detail", item_id=item_id
    )
    return redirect(target)


@bp.post("/item/<int:item_id>/report")
@login_required
def report(item_id: int):
    item = fetch_item(item_id)
    if item is None:
        abort(404)
    if g.user["id"] == item["seller_id"]:
        abort(403)
    if item["is_removed"] or item["status"] not in ("on_sale", "sold"):
        abort(400)

    reason = request.form.get("reason", "").strip()
    if not 5 <= len(reason) <= 200:
        flash(t("items.error.reason"), "error")
        return redirect(url_for("items.detail", item_id=item_id))

    conn = db.get_db()
    cursor = conn.execute(
        "INSERT OR IGNORE INTO reports "
        "(item_id, reporter_id, reason, created_at) "
        "VALUES (?, ?, ?, datetime('now', 'localtime'))",
        (item_id, g.user["id"], reason),
    )
    conn.commit()
    if cursor.rowcount:
        flash(t("flash.success.reported"), "success")
    else:
        flash(t("flash.info.already_reported"), "info")
    return redirect(url_for("items.detail", item_id=item_id))
