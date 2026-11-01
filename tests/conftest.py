import pytest
from werkzeug.security import generate_password_hash


@pytest.fixture
def app(tmp_path):
    from app import create_app
    app = create_app({
        "TESTING": True,
        "SECRET_KEY": "test-secret",
        "DATABASE": str(tmp_path / "test.db"),
        "UPLOAD_FOLDER": str(tmp_path / "uploads"),
        "ITEMS_PER_PAGE": 12,
        "MAX_IMAGES": 5,
    })
    yield app


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def seed(app):
    from app import db

    categories = [
        ("books", "教材书籍", "Books", "book", 1),
        ("digital", "电子数码", "Electronics", "device", 2),
        ("life", "生活用品", "Daily life", "lamp", 3),
        ("sports", "运动健身", "Sports", "ball", 4),
        ("fashion", "美妆衣物", "Fashion", "shirt", 5),
        ("stationery", "文具文创", "Stationery", "pen", 6),
        ("other", "其他闲置", "Other", "box", 7),
    ]
    users = [
        ("2023001", "林小雨", "student", "Demo@12345"),
        ("2023002", "陈子昂", "student", "Demo@12345"),
        ("2023003", "苏晴", "student", "Demo@12345"),
        ("admin", "平台管理员", "admin", "Admin@12345"),
    ]

    with app.app_context():
        conn = db.get_db()
        conn.executemany(
            "INSERT INTO categories "
            "(slug, name_zh, name_en, icon, sort_order, is_active) "
            "VALUES (?, ?, ?, ?, ?, 1)",
            categories,
        )
        for index, (student_id, username, role, password) in enumerate(users, start=1):
            conn.execute(
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
                    "2026-10-01 10:00:00",
                ),
            )
        conn.commit()
    yield app


@pytest.fixture
def add_item(app, seed):
    from app import db

    def _add(**overrides):
        data = {
            "seller_id": 1,
            "category_id": 1,
            "title": "旧教材",
            "description": "九成新，无笔记",
            "price": 20.0,
            "status": "on_sale",
            "view_count": 0,
            "is_removed": 0,
            "removed_by": None,
            "created_at": "2026-10-01 10:00:00",
        }
        data.update(overrides)
        with app.app_context():
            cur = db.get_db().execute(
                "INSERT INTO items "
                "(seller_id, category_id, title, description, price, status, "
                "view_count, is_removed, removed_by, removed_at, "
                "created_at, updated_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    data["seller_id"],
                    data["category_id"],
                    data["title"],
                    data["description"],
                    data["price"],
                    data["status"],
                    data["view_count"],
                    data["is_removed"],
                    data["removed_by"],
                    "2026-10-02 10:00:00" if data["is_removed"] else None,
                    data["created_at"],
                    data["created_at"],
                ),
            )
            db.get_db().commit()
            return cur.lastrowid

    return _add
