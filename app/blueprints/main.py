from flask import Blueprint, abort, redirect, render_template, request, session

from .. import db
from ..queries import fetch_categories, fetch_items
from ..security import safe_next_url

bp = Blueprint("main", __name__)


def build_home_data():
    latest = fetch_items("public", sort="latest", per_page=8)["items"]
    popular = fetch_items(
        "public", status="on_sale", sort="views", per_page=8
    )["items"]
    stats = {
        "items": db.query_one(
            "SELECT COUNT(*) AS n FROM items WHERE is_removed = 0"
        )["n"],
        "students": db.query_one(
            "SELECT COUNT(*) AS n FROM users WHERE role = 'student'"
        )["n"],
        "sold": db.query_one(
            "SELECT COUNT(*) AS n FROM items "
            "WHERE is_removed = 0 AND status = 'sold'"
        )["n"],
    }
    return {
        "latest": latest,
        "popular": popular,
        "categories": fetch_categories(),
        "stats": stats,
    }


@bp.get("/")
def index():
    return render_template("index.html", data=build_home_data())


@bp.get("/categories")
def categories():
    return render_template("categories.html", categories=fetch_categories())


@bp.get("/lang/<lang>")
def set_language(lang: str):
    if lang not in ("zh", "en"):
        abort(404)
    session["lang"] = lang
    target = safe_next_url(request.args.get("next")) or "/"
    return redirect(target)
