import os
import sys
from datetime import datetime, timedelta
from pathlib import Path

from werkzeug.security import generate_password_hash

from app import create_app, db
from config import Config

CATEGORIES = [
    ("books", "教材书籍", "Books", "book"),
    ("digital", "电子数码", "Electronics", "device"),
    ("life", "生活用品", "Daily life", "lamp"),
    ("sports", "运动健身", "Sports", "ball"),
    ("fashion", "美妆衣物", "Fashion", "shirt"),
    ("stationery", "文具文创", "Stationery", "pen"),
    ("other", "其他闲置", "Other", "box"),
]

USERS = [
    ("admin", "平台管理员", "Admin@12345", "admin"),
    ("2023001", "林小雨", "Demo@12345", "student"),
    ("2023002", "陈子昂", "Demo@12345", "student"),
    ("2023003", "苏晴", "Demo@12345", "student"),
]

ITEMS = [
    # books
    ("books", "高等数学教材（第七版）", "同济版上下册，重点章节有少量标注，适合大一复习。", 25, 79, "good", "一食堂"),
    ("books", "大学英语四级真题", "近五年真题和模拟卷，答案完整，无缺页。", 15, 45, "like_new", "图书馆"),
    ("books", "考研英语词汇书", "恋练有词，只翻过前二十页，几乎全新。", 20, 68, "like_new", "教学楼"),
    ("books", "线性代数课本", "期末复习用完，笔记可擦除。", 12, 35, "good", "宿舍楼下"),
    # digital
    ("digital", "蓝牙耳机", "用了两个月，续航正常，附充电盒。", 89, 199, "like_new", "宿舍楼下"),
    ("digital", "20000mAh 充电宝", "支持快充，外观九成新。", 55, 129, "good", "二食堂"),
    ("digital", "无线鼠标", "静音款，接收器齐全。", 30, 89, "good", "教学楼"),
    ("digital", "可调光小台灯", "宿舍用，暖光三档。", 25, 59, "good", "宿舍楼下"),
    # life
    ("life", "宿舍收纳箱", "45L 带盖，搬宿舍前出。", 20, 59, "good", "宿舍楼下"),
    ("life", "折叠衣架十只装", "九成新，无变形。", 8, 25, "like_new", "一食堂"),
    ("life", "床上四件套", "1.2m 床适用，洗净消毒。", 60, 159, "good", "宿舍楼下"),
    ("life", "保温杯", "500ml，保温正常，杯身无磕碰。", 15, 49, "like_new", "教学楼"),
    # sports
    ("sports", "羽毛球拍一对", "入门款，送三个球。", 45, 120, "good", "体育馆"),
    ("sports", "跑步鞋 42 码", "跑了不到十次，鞋底磨损轻。", 80, 299, "like_new", "宿舍楼下"),
    ("sports", "瑜伽垫", "加厚防滑，附收纳带。", 30, 79, "good", "宿舍楼下"),
    ("sports", "篮球", "七成新，气足。", 35, 99, "good", "体育馆"),
    # fashion
    ("fashion", "灰色连帽卫衣", "M 码，洗过两次无起球。", 35, 99, "like_new", "宿舍楼下"),
    ("fashion", "保湿面霜", "全新未拆封，专柜购入。", 60, 129, "new", "教学楼"),
    ("fashion", "帆布包", "大容量，适合上课装书。", 15, 45, "good", "一食堂"),
    ("fashion", "冬季围巾", "只戴过一次。", 20, 59, "like_new", "宿舍楼下"),
    # stationery
    ("stationery", "手账本套装", "含贴纸和胶带，全新。", 25, 59, "new", "教学楼"),
    ("stationery", "中性笔套装", "十支黑笔加笔芯，未拆封。", 10, 25, "new", "一食堂"),
    ("stationery", "桌面收纳盒", "三层，适合放文具。", 18, 49, "good", "宿舍楼下"),
    ("stationery", "24 色马克笔", "用了几次，颜色齐全。", 22, 69, "good", "教学楼"),
    # other
    ("other", "折叠雨伞", "自动伞，骨架正常。", 15, 39, "good", "宿舍楼下"),
    ("other", "USB 小风扇", "充电款，三档风力。", 20, 55, "good", "教学楼"),
    ("other", "旧手机支架", "桌面可调节。", 5, 19, "fair", "一食堂"),
    ("other", "空收纳袋", "搬家剩余，未使用。", 5, 15, "new", "宿舍楼下"),
]

STATUS_OVERRIDES = {
    ("books", 3): "sold",
    ("digital", 2): "sold",
    ("digital", 3): "unavailable",
    ("life", 3): "sold",
    ("sports", 3): "sold",
    ("fashion", 3): "sold",
    ("stationery", 2): "sold",
    ("stationery", 3): "unavailable",
}

REMOVED_OVERRIDES = {
    ("other", 2): ("admin", "违规广告"),
    ("other", 3): ("seller", "seller_deleted"),
}

PLACEHOLDER_STYLES = {
    "books": ("#5B8DEF", "#3B6FD4", "BOOKS"),
    "digital": ("#7C5CFC", "#5B3FD6", "ELECTRONICS"),
    "life": ("#38B2AC", "#2C8A85", "DAILY LIFE"),
    "sports": ("#F6A623", "#D98A12", "SPORTS"),
    "fashion": ("#EC6F91", "#D24B70", "FASHION"),
    "stationery": ("#4FB286", "#359468", "STATIONERY"),
    "other": ("#64748B", "#475569", "OTHER"),
}


def seed_data() -> dict:
    conn = db.get_db()
    now = datetime.now()

    conn.execute("DELETE FROM reports")
    conn.execute("DELETE FROM browse_history")
    conn.execute("DELETE FROM favorites")
    conn.execute("DELETE FROM item_images")
    conn.execute("DELETE FROM items")
    conn.execute("DELETE FROM categories")
    conn.execute("DELETE FROM users")

    for slug, name_zh, name_en, icon in CATEGORIES:
        conn.execute(
            "INSERT INTO categories (slug, name_zh, name_en, icon, sort_order, is_active) "
            "VALUES (?, ?, ?, ?, ?, 1)",
            (slug, name_zh, name_en, icon, CATEGORIES.index((slug, name_zh, name_en, icon)) + 1),
        )

    category_ids = {
        row["slug"]: row["id"]
        for row in conn.execute("SELECT id, slug FROM categories")
    }

    user_ids = {}
    for index, (student_id, username, password, role) in enumerate(USERS, start=1):
        cursor = conn.execute(
            "INSERT INTO users "
            "(student_id, username, password_hash, contact_wechat, "
            "contact_phone, role, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                student_id,
                username,
                generate_password_hash(password),
                f"wx_{student_id}",
                f"1380000000{index}",
                role,
                "2026-09-01 09:00:00",
            ),
        )
        user_ids[student_id] = cursor.lastrowid

    grouped = {}
    for spec in ITEMS:
        grouped.setdefault(spec[0], []).append(spec)

    ordered = []
    max_per_category = max(len(items) for items in grouped.values())
    for position in range(max_per_category):
        for category in CATEGORIES:
            slug = category[0]
            if position < len(grouped.get(slug, [])):
                ordered.append((position, grouped[slug][position]))

    item_ids = []
    for index, (category_position, spec) in enumerate(ordered):
        slug, title, description, price, original, condition, location = spec

        status = STATUS_OVERRIDES.get((slug, category_position), "on_sale")
        removed_by, removed_reason = REMOVED_OVERRIDES.get(
            (slug, category_position), (None, None)
        )
        created_at = (now - timedelta(days=index, hours=index % 6)).strftime(
            "%Y-%m-%d %H:%M:%S"
        )
        view_count = (index * 37 + 13) % 300

        cursor = conn.execute(
            "INSERT INTO items "
            "(seller_id, category_id, title, description, price, original_price, "
            "condition, trade_location, status, view_count, is_removed, "
            "removed_by, removed_reason, removed_at, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                user_ids[["2023001", "2023002", "2023003"][index % 3]],
                category_ids[slug],
                title,
                description,
                float(price),
                float(original),
                condition,
                location,
                status,
                view_count,
                1 if removed_by else 0,
                removed_by,
                removed_reason,
                created_at if removed_by else None,
                created_at,
                created_at,
            ),
        )
        item_id = cursor.lastrowid
        item_ids.append(item_id)

        conn.execute(
            "INSERT INTO item_images (item_id, filename, sort_order) VALUES (?, ?, 0)",
            (item_id, f"img/placeholders/{slug}-1.svg"),
        )
        conn.execute(
            "INSERT INTO item_images (item_id, filename, sort_order) VALUES (?, ?, 1)",
            (item_id, f"img/placeholders/{slug}-2.svg"),
        )

    def pick(condition: str):
        row = conn.execute(
            f"SELECT id FROM items WHERE {condition} AND seller_id != ? LIMIT 1",
            (user_ids["2023001"],),
        ).fetchone()
        return row["id"] if row else None

    favorite_items = [
        pick("is_removed = 0 AND status = 'on_sale'"),
        pick("is_removed = 0 AND status = 'sold'"),
        pick("is_removed = 0 AND status = 'unavailable'"),
        pick("is_removed = 1 AND removed_by = 'admin'"),
    ]
    for item_id in [value for value in favorite_items if value]:
        conn.execute(
            "INSERT OR IGNORE INTO favorites (user_id, item_id, created_at) "
            "VALUES (?, ?, ?)",
            (user_ids["2023001"], item_id, "2026-10-20 12:00:00"),
        )

    history_items = [
        row["id"]
        for row in conn.execute(
            "SELECT id FROM items WHERE is_removed = 0 "
            "AND status IN ('on_sale', 'sold') ORDER BY id LIMIT 5"
        )
    ]
    paused = conn.execute(
        "SELECT id FROM items WHERE is_removed = 0 AND status = 'unavailable' LIMIT 1"
    ).fetchone()
    if paused:
        history_items.append(paused["id"])
    for offset, item_id in enumerate(history_items):
        conn.execute(
            "INSERT OR IGNORE INTO browse_history (user_id, item_id, viewed_at) "
            "VALUES (?, ?, ?)",
            (
                user_ids["2023001"],
                item_id,
                (now - timedelta(hours=offset)).strftime("%Y-%m-%d %H:%M:%S"),
            ),
        )

    reported = conn.execute(
        "SELECT id FROM items WHERE is_removed = 0 AND status = 'on_sale' "
        "AND seller_id != ? LIMIT 1",
        (user_ids["2023002"],),
    ).fetchone()
    if reported:
        conn.execute(
            "INSERT INTO reports (item_id, reporter_id, reason, status, created_at) "
            "VALUES (?, ?, ?, 'pending', ?)",
            (
                reported["id"],
                user_ids["2023002"],
                "描述与实物不符，希望管理员核实。",
                now.strftime("%Y-%m-%d %H:%M:%S"),
            ),
        )

    conn.commit()
    return {
        "users": len(USERS),
        "categories": len(CATEGORIES),
        "items": len(ITEMS),
    }


def write_placeholder_images() -> None:
    folder = Path(__file__).resolve().parent / "static" / "img" / "placeholders"
    folder.mkdir(parents=True, exist_ok=True)

    for slug, (color_a, color_b, label) in PLACEHOLDER_STYLES.items():
        for variant in (1, 2):
            circle_x = 640 if variant == 1 else 180
            circle_y = 120 if variant == 1 else 470
            circle_r = 190 if variant == 1 else 150
            svg = f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 800 600">
  <defs>
    <linearGradient id="g" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0" stop-color="{color_a}"/>
      <stop offset="1" stop-color="{color_b}"/>
    </linearGradient>
  </defs>
  <rect width="800" height="600" fill="url(#g)"/>
  <circle cx="{circle_x}" cy="{circle_y}" r="{circle_r}" fill="#ffffff" opacity="0.10"/>
  <circle cx="{800 - circle_x}" cy="{600 - circle_y}" r="{circle_r // 2}" fill="#ffffff" opacity="0.07"/>
  <rect x="60" y="60" width="680" height="480" rx="36" fill="#ffffff" opacity="0.08"/>
  <text x="70" y="300" font-family="Segoe UI, Arial, sans-serif" font-size="62"
        font-weight="700" fill="#ffffff">{label}</text>
  <text x="72" y="352" font-family="Segoe UI, Arial, sans-serif" font-size="26"
        fill="#ffffff" opacity="0.82">Campus Market</text>
  <text x="72" y="470" font-family="Segoe UI, Arial, sans-serif" font-size="20"
        fill="#ffffff" opacity="0.62">Campus-only second-hand</text>
</svg>
"""
            (folder / f"{slug}-{variant}.svg").write_text(svg, encoding="utf-8")


def main() -> None:
    reset = "--reset" in sys.argv
    if reset:
        database = Path(os.environ.get("DATABASE", Config.DATABASE))
        if database.exists():
            database.unlink()
        uploads = Path(Config.UPLOAD_FOLDER)
        if uploads.exists():
            for file_path in uploads.iterdir():
                if file_path.is_file() and file_path.name != ".gitkeep":
                    file_path.unlink()

    app = create_app()
    with app.app_context():
        counts = seed_data()

    write_placeholder_images()
    print(
        f"Seeded {counts['items']} items in {counts['categories']} categories "
        f"for {counts['users']} users."
    )
    print("Admin: admin / Admin@12345")
    print("Students: 2023001 / 2023002 / 2023003, password Demo@12345")


if __name__ == "__main__":
    main()
