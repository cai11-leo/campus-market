from tests.helpers import get_csrf, login


def _set_status(client, item_id, status):
    return client.post(f"/item/{item_id}/status", data={
        "status": status,
        "csrf_token": get_csrf(client, "/"),
    }, follow_redirects=True)


def test_owner_can_mark_sold_and_relist(app, client, add_item, seed):
    item_id = add_item(title="状态商品", seller_id=1)
    login(client)
    _set_status(client, item_id, "sold")
    with app.app_context():
        from app import db
        assert db.query_one(
            "SELECT status FROM items WHERE id = ?", (item_id,)
        )["status"] == "sold"
    _set_status(client, item_id, "on_sale")
    with app.app_context():
        from app import db
        assert db.query_one(
            "SELECT status FROM items WHERE id = ?", (item_id,)
        )["status"] == "on_sale"


def test_non_owner_cannot_change_status(client, add_item, seed):
    item_id = add_item(title="别人的商品", seller_id=2)
    login(client)
    assert client.post(f"/item/{item_id}/status", data={
        "status": "sold",
        "csrf_token": get_csrf(client, "/"),
    }).status_code == 403


def test_paused_item_disappears_from_public_list(client, add_item, seed):
    item_id = add_item(title="下架商品", seller_id=1)
    login(client)
    _set_status(client, item_id, "unavailable")
    client.post("/logout", data={"csrf_token": get_csrf(client, "/")})
    assert "下架商品" not in client.get("/items").get_data(as_text=True)


def test_seller_delete_hides_item_everywhere(app, client, add_item, seed):
    item_id = add_item(title="待删除商品", seller_id=1)
    login(client)
    client.post(f"/item/{item_id}/delete", data={
        "csrf_token": get_csrf(client, "/"),
    }, follow_redirects=True)
    with app.app_context():
        from app import db
        row = db.query_one(
            "SELECT is_removed, removed_by FROM items WHERE id = ?", (item_id,)
        )
    assert row["is_removed"] == 1 and row["removed_by"] == "seller"
    assert "待删除商品" not in client.get("/items").get_data(as_text=True)


def test_non_owner_cannot_edit_or_delete(client, add_item, seed):
    item_id = add_item(title="他人商品", seller_id=2)
    login(client)
    assert client.get(f"/item/{item_id}/edit").status_code == 403
    assert client.post(f"/item/{item_id}/delete", data={
        "csrf_token": get_csrf(client, "/"),
    }).status_code == 403


def test_non_owner_post_edit_is_403(client, add_item, seed):
    item_id = add_item(title="他人商品", seller_id=2)
    login(client)
    response = client.post(f"/item/{item_id}/edit", data={
        "title": "被篡改",
        "category_id": "1",
        "price": "10",
        "description": "尝试越权修改",
        "condition": "good",
        "trade_location": "宿舍楼下",
        "csrf_token": get_csrf(client, "/"),
    })
    assert response.status_code == 403


def test_status_post_without_csrf_is_400(client, add_item, seed):
    item_id = add_item(title="CSRF商品", seller_id=1)
    login(client)
    assert client.post(f"/item/{item_id}/status", data={
        "status": "sold",
    }).status_code == 400
