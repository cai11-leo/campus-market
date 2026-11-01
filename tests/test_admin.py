from app import db
from tests.helpers import get_csrf, login


def test_non_admin_gets_403(client, seed):
    login(client)
    assert client.get("/admin").status_code == 403


def test_admin_can_remove_and_restore_item(client, app, add_item, seed):
    item_id = add_item(title="待审核商品", seller_id=2)
    login(client, "admin", "Admin@12345")
    token = get_csrf(client, "/admin/items")
    client.post(f"/admin/items/{item_id}/remove", data={
        "reason": "疑似广告", "csrf_token": token,
    }, follow_redirects=True)
    anonymous = client.application.test_client()
    assert anonymous.get(f"/item/{item_id}").status_code == 404
    with app.app_context():
        row = db.query_one(
            "SELECT is_removed, removed_by, removed_reason FROM items WHERE id = ?",
            (item_id,),
        )
    assert row["removed_by"] == "admin"
    assert row["removed_reason"] == "疑似广告"
    token = get_csrf(client, "/admin/items")
    client.post(f"/admin/items/{item_id}/restore", data={
        "csrf_token": token,
    }, follow_redirects=True)
    assert client.get(f"/item/{item_id}").status_code == 200


def test_admin_cannot_restore_seller_deleted(client, app, add_item, seed):
    item_id = add_item(title="卖家删除", is_removed=1, removed_by="seller")
    login(client, "admin", "Admin@12345")
    client.post(f"/admin/items/{item_id}/restore", data={
        "csrf_token": get_csrf(client, "/admin/items"),
    }, follow_redirects=True)
    with app.app_context():
        assert db.query_one(
            "SELECT is_removed FROM items WHERE id = ?", (item_id,)
        )["is_removed"] == 1


def test_category_create_and_toggle(client, app, seed):
    login(client, "admin", "Admin@12345")
    token = get_csrf(client, "/admin/categories")
    client.post("/admin/categories", data={
        "slug": "music",
        "name_zh": "乐器",
        "name_en": "Instruments",
        "icon": "box",
        "sort_order": "8",
        "csrf_token": token,
    }, follow_redirects=True)
    with app.app_context():
        cat = db.query_one("SELECT * FROM categories WHERE slug = 'music'")
    assert cat["name_zh"] == "乐器"
    client.post(f"/admin/categories/{cat['id']}/toggle", data={
        "csrf_token": get_csrf(client, "/admin/categories"),
    }, follow_redirects=True)
    with app.app_context():
        assert db.query_one(
            "SELECT is_active FROM categories WHERE id = ?", (cat["id"],)
        )["is_active"] == 0


def test_report_flow(client, app, add_item, seed):
    item_id = add_item(title="举报商品", seller_id=2)
    login(client)
    client.post(f"/item/{item_id}/report", data={
        "reason": "疑似虚假描述",
        "csrf_token": get_csrf(client, f"/item/{item_id}"),
    }, follow_redirects=True)
    with app.app_context():
        report = db.query_one(
            "SELECT * FROM reports WHERE item_id = ?", (item_id,)
        )
    login(client, "admin", "Admin@12345")
    html = client.get("/admin/reports").get_data(as_text=True)
    assert "疑似虚假描述" in html
    client.post(f"/admin/reports/{report['id']}/remove-item", data={
        "csrf_token": get_csrf(client, "/admin/reports"),
    }, follow_redirects=True)
    with app.app_context():
        assert db.query_one(
            "SELECT is_removed FROM items WHERE id = ?", (item_id,)
        )["is_removed"] == 1
        assert db.query_one(
            "SELECT status FROM reports WHERE id = ?", (report["id"],)
        )["status"] == "resolved"
