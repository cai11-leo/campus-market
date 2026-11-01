from app import db
from tests.helpers import get_csrf, login


def test_my_items_excludes_seller_deleted_and_shows_admin_reason(
    client, app, add_item, seed
):
    add_item(title="我的在售", seller_id=1)
    add_item(title="管理员下架商品", seller_id=1, is_removed=1, removed_by="admin")
    add_item(title="我删除的商品", seller_id=1, is_removed=1, removed_by="seller")
    login(client)
    html = client.get("/my/items").get_data(as_text=True)
    assert "我的在售" in html
    assert "管理员下架商品" in html
    assert "我删除的商品" not in html


def test_favorite_only_on_sale_and_invalid_favorites_remain(
    client, app, add_item, seed
):
    on_sale = add_item(title="可收藏", status="on_sale", seller_id=2)
    sold = add_item(title="已售收藏", status="sold", seller_id=2)
    login(client)
    assert client.post(f"/item/{sold}/favorite", data={
        "csrf_token": get_csrf(client, f"/item/{sold}"),
    }).status_code == 302
    with app.app_context():
        assert db.query_one(
            "SELECT * FROM favorites WHERE item_id = ?", (sold,)
        ) is None
    client.post(f"/item/{on_sale}/favorite", data={
        "csrf_token": get_csrf(client, f"/item/{on_sale}"),
    })
    with app.app_context():
        db.get_db().execute(
            "INSERT INTO favorites (user_id, item_id, created_at) VALUES (1, ?, ?)",
            (sold, "2026-10-01 10:00:00"),
        )
        db.get_db().commit()
    html = client.get("/my/favorites").get_data(as_text=True)
    assert "可收藏" in html
    assert "已售收藏" in html


def test_history_hides_unavailable_and_dedupes(client, app, add_item, seed):
    item = add_item(title="浏览商品", seller_id=2)
    paused = add_item(title="暂停商品", seller_id=2, status="unavailable")
    login(client)
    client.get(f"/item/{item}")
    client.get(f"/item/{item}")
    with app.app_context():
        db.get_db().execute(
            "INSERT INTO browse_history (user_id, item_id, viewed_at) VALUES (1, ?, ?)",
            (paused, "2026-10-01 10:00:00"),
        )
        db.get_db().commit()
        count = db.query_one(
            "SELECT COUNT(*) AS n FROM browse_history WHERE item_id = ?", (item,)
        )["n"]
    assert count == 1
    html = client.get("/my/history").get_data(as_text=True)
    assert "浏览商品" in html
    assert "暂停商品" not in html


def test_profile_updates_contact_and_password(client, app, seed):
    login(client)
    token = get_csrf(client, "/profile")
    response = client.post("/profile", data={
        "username": "小雨",
        "contact_wechat": "wx_new",
        "contact_phone": "13900000000",
        "current_password": "Demo@12345",
        "new_password": "NewPass1!",
        "confirm_password": "NewPass1!",
        "csrf_token": token,
    }, follow_redirects=True)
    assert "修改已保存" in response.get_data(as_text=True)
    with app.app_context():
        user = db.query_one("SELECT * FROM users WHERE id = 1")
        from werkzeug.security import check_password_hash
        assert user["contact_wechat"] == "wx_new"
        assert check_password_hash(user["password_hash"], "NewPass1!")
