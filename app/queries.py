import math

from . import db

ITEM_SELECT = """
SELECT i.*, c.slug AS category_slug,
       c.name_zh AS category_name_zh, c.name_en AS category_name_en,
       u.username AS seller_name, u.student_id AS seller_student_id,
       u.contact_wechat, u.contact_phone,
       (SELECT filename FROM item_images
        WHERE item_id = i.id ORDER BY sort_order, id LIMIT 1) AS cover
FROM items i
JOIN categories c ON c.id = i.category_id
JOIN users u ON u.id = i.seller_id
"""

SORTS = {
    "latest": "i.created_at DESC, i.id DESC",
    "price_asc": "i.price ASC, i.id DESC",
    "price_desc": "i.price DESC, i.id DESC",
    "views": "i.view_count DESC, i.id DESC",
}

VALID_STATUSES = ("on_sale", "sold", "unavailable")


def _escape_like(value: str) -> str:
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def fetch_items(
    scope: str = "public",
    *,
    q=None,
    category_slug=None,
    status=None,
    removed=None,
    seller_id=None,
    sort="latest",
    page=1,
    per_page=12,
):
    where = []
    args = []

    if scope == "public":
        where.append("i.is_removed = 0")
        where.append("i.status IN ('on_sale', 'sold')")
        if status in ("on_sale", "sold"):
            where.append("i.status = ?")
            args.append(status)
    elif scope == "seller":
        where.append("i.seller_id = ?")
        args.append(seller_id)
        where.append("NOT (i.is_removed = 1 AND i.removed_by = 'seller')")
        if status in VALID_STATUSES:
            where.append("i.status = ?")
            args.append(status)
    elif scope == "admin":
        if removed == "none":
            where.append("i.is_removed = 0")
        elif removed in ("admin", "seller"):
            where.append("i.is_removed = 1 AND i.removed_by = ?")
            args.append(removed)
        if status in VALID_STATUSES:
            where.append("i.status = ?")
            args.append(status)
    else:
        raise ValueError(f"unknown scope: {scope}")

    if q:
        like = f"%{_escape_like(q)}%"
        where.append(
            "(i.title LIKE ? ESCAPE '\\' OR i.description LIKE ? ESCAPE '\\')"
        )
        args.extend([like, like])

    if category_slug:
        where.append("c.slug = ?")
        args.append(category_slug)

    where_sql = (" WHERE " + " AND ".join(where)) if where else ""
    per_page = max(1, int(per_page))

    total = db.query_one(
        "SELECT COUNT(*) AS n FROM items i "
        "JOIN categories c ON c.id = i.category_id"
        + where_sql,
        args,
    )["n"]

    pages = max(1, math.ceil(total / per_page))
    page = max(1, min(int(page or 1), pages))
    offset = (page - 1) * per_page
    order = SORTS.get(sort, SORTS["latest"])

    rows = db.query_all(
        ITEM_SELECT
        + where_sql
        + f" ORDER BY {order} LIMIT ? OFFSET ?",
        [*args, per_page, offset],
    )

    return {
        "items": rows,
        "total": total,
        "page": page,
        "pages": pages,
        "per_page": per_page,
    }


def fetch_item(item_id: int):
    if not isinstance(item_id, int) or not 1 <= item_id <= 2_147_483_647:
        return None
    return db.query_one(ITEM_SELECT + " WHERE i.id = ?", (item_id,))


def fetch_item_images(item_id: int):
    return db.query_all(
        "SELECT * FROM item_images WHERE item_id = ? ORDER BY sort_order, id",
        (item_id,),
    )


def fetch_favorites(user_id: int):
    return db.query_all(
        """
        SELECT i.*, c.slug AS category_slug,
               c.name_zh AS category_name_zh, c.name_en AS category_name_en,
               u.username AS seller_name, u.student_id AS seller_student_id,
               f.created_at AS favorite_created_at,
               (SELECT filename FROM item_images
                WHERE item_id = i.id ORDER BY sort_order, id LIMIT 1) AS cover
        FROM favorites f
        JOIN items i ON i.id = f.item_id
        JOIN categories c ON c.id = i.category_id
        JOIN users u ON u.id = i.seller_id
        WHERE f.user_id = ?
        ORDER BY f.created_at DESC, i.id DESC
        """,
        (user_id,),
    )


def fetch_history(user_id: int, limit=50):
    return db.query_all(
        """
        SELECT i.*, c.slug AS category_slug,
               c.name_zh AS category_name_zh, c.name_en AS category_name_en,
               u.username AS seller_name,
               h.viewed_at AS viewed_at,
               (SELECT filename FROM item_images
                WHERE item_id = i.id ORDER BY sort_order, id LIMIT 1) AS cover
        FROM browse_history h
        JOIN items i ON i.id = h.item_id
        JOIN categories c ON c.id = i.category_id
        JOIN users u ON u.id = i.seller_id
        WHERE h.user_id = ?
          AND i.is_removed = 0
          AND i.status IN ('on_sale', 'sold')
        ORDER BY h.viewed_at DESC, i.id DESC
        LIMIT ?
        """,
        (user_id, limit),
    )


def admin_stats():
    def count(sql, args=()):
        return db.query_one(sql, args)["n"]

    category_counts = db.query_all(
        """
        SELECT c.id, c.slug, c.name_zh, c.name_en,
               COUNT(i.id) AS item_count
        FROM categories c
        LEFT JOIN items i ON i.category_id = c.id AND i.is_removed = 0
        GROUP BY c.id
        ORDER BY c.sort_order, c.id
        """
    )
    max_category = max((row["item_count"] for row in category_counts), default=1) or 1

    return {
        "users": count("SELECT COUNT(*) AS n FROM users"),
        "items_total": count(
            "SELECT COUNT(*) AS n FROM items WHERE is_removed = 0"
        ),
        "on_sale": count(
            "SELECT COUNT(*) AS n FROM items "
            "WHERE is_removed = 0 AND status = 'on_sale'"
        ),
        "sold": count(
            "SELECT COUNT(*) AS n FROM items "
            "WHERE is_removed = 0 AND status = 'sold'"
        ),
        "unavailable": count(
            "SELECT COUNT(*) AS n FROM items "
            "WHERE is_removed = 0 AND status = 'unavailable'"
        ),
        "removed_admin": count(
            "SELECT COUNT(*) AS n FROM items "
            "WHERE is_removed = 1 AND removed_by = 'admin'"
        ),
        "removed_seller": count(
            "SELECT COUNT(*) AS n FROM items "
            "WHERE is_removed = 1 AND removed_by = 'seller'"
        ),
        "views": db.query_one(
            "SELECT COALESCE(SUM(view_count), 0) AS n FROM items "
            "WHERE is_removed = 0"
        )["n"],
        "pending_reports": count(
            "SELECT COUNT(*) AS n FROM reports WHERE status = 'pending'"
        ),
        "category_counts": category_counts,
        "max_category": max_category,
    }


def fetch_categories(active_only=True):
    sql = (
        "SELECT c.*, "
        "(SELECT COUNT(*) FROM items i WHERE i.category_id = c.id "
        "AND i.is_removed = 0 AND i.status IN ('on_sale', 'sold')) "
        "AS visible_count "
        "FROM categories c"
    )
    if active_only:
        sql += " WHERE c.is_active = 1"
    sql += " ORDER BY c.sort_order, c.id"
    return db.query_all(sql)


def fetch_category_by_slug(slug, active_only=True):
    sql = "SELECT * FROM categories WHERE slug = ?"
    if active_only:
        sql += " AND is_active = 1"
    return db.query_one(sql, (slug,))
