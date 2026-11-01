import re
from io import BytesIO

from tests.helpers import get_csrf, login

PNG = b"\x89PNG\r\n\x1a\n" + b"0" * 20


def _post_item(client, **overrides):
    follow = overrides.pop("follow_redirects", False)
    data = {
        "title": "二手台灯",
        "category_id": "3",
        "price": "35",
        "description": "用了一学期，功能正常",
        "condition": "good",
        "trade_location": "三食堂门口",
        "csrf_token": get_csrf(client, "/publish"),
        "images": (BytesIO(PNG), "lamp.png"),
    }
    data.update(overrides)
    return client.post(
        "/publish",
        data=data,
        content_type="multipart/form-data",
        follow_redirects=follow,
    )


def test_publish_requires_login(client, seed):
    assert client.get("/publish").status_code == 302


def test_publish_creates_on_sale_item_with_image(app, client, seed):
    login(client)
    response = _post_item(client)
    assert response.status_code == 302
    with app.app_context():
        from app import db
        item = db.query_one("SELECT * FROM items WHERE title = '二手台灯'")
        images = db.query_all(
            "SELECT * FROM item_images WHERE item_id = ?", (item["id"],)
        )
    assert item["status"] == "on_sale"
    assert item["price"] == 35.0
    assert len(images) == 1


def test_publish_requires_contact(client, app, seed):
    with app.app_context():
        from app import db
        db.get_db().execute(
            "UPDATE users SET contact_wechat = NULL, contact_phone = NULL WHERE id = 1"
        )
        db.get_db().commit()
    login(client)
    response = _post_item(client)
    assert response.status_code == 302
    assert response.headers["Location"].endswith("/profile")


def test_publish_rejects_missing_image(client, seed):
    login(client)
    response = client.post("/publish", data={
        "title": "无图商品",
        "category_id": "1",
        "price": "10",
        "description": "没有图片",
        "csrf_token": get_csrf(client, "/publish"),
    }, content_type="multipart/form-data")
    assert "请上传 1–5 张图片" in response.get_data(as_text=True)


def test_publish_rejects_more_than_five_images(client, seed):
    login(client)
    files = [(BytesIO(PNG), f"{i}.png") for i in range(6)]
    response = client.post("/publish", data={
        "title": "六图商品",
        "category_id": "1",
        "price": "10",
        "description": "图片太多",
        "csrf_token": get_csrf(client, "/publish"),
        "images": files,
    }, content_type="multipart/form-data")
    assert "请上传 1–5 张图片" in response.get_data(as_text=True)


def test_upload_error_is_translated(client, seed):
    client.get("/lang/en")
    login(client)
    response = client.post("/publish", data={
        "title": "No image",
        "category_id": "1",
        "price": "10",
        "description": "no image here",
        "csrf_token": get_csrf(client, "/publish"),
    }, content_type="multipart/form-data")
    assert "Upload 1–5 images" in response.get_data(as_text=True)


def test_edit_keeps_disabled_current_category(app, client, add_item, seed):
    item_id = add_item(title="停用分类商品", seller_id=1, category_id=2)
    with app.app_context():
        from app import db
        db.get_db().execute(
            "INSERT INTO item_images (item_id, filename, sort_order) VALUES (?, ?, 0)",
            (item_id, "img/placeholders/digital-1.svg"),
        )
        db.get_db().execute("UPDATE categories SET is_active = 0 WHERE id = 2")
        db.get_db().commit()
    login(client)
    html = client.get(f"/item/{item_id}/edit").get_data(as_text=True)
    assert re.search(r'<option value="2"[^>]*selected', html)
    token = get_csrf(client, f"/item/{item_id}/edit")
    response = client.post(f"/item/{item_id}/edit", data={
        "title": "停用分类商品",
        "category_id": "2",
        "price": "20",
        "description": "九成新，无笔记",
        "condition": "good",
        "trade_location": "宿舍楼下",
        "csrf_token": token,
    }, follow_redirects=True)
    assert response.status_code == 200
    with app.app_context():
        from app import db
        assert db.query_one(
            "SELECT category_id FROM items WHERE id = ?", (item_id,)
        )["category_id"] == 2


def test_publish_location_suggestions_are_translated(client, seed):
    login(client)
    zh = client.get("/publish").get_data(as_text=True)
    assert "宿舍楼下" in zh
    client.get("/lang/en")
    en = client.get("/publish").get_data(as_text=True)
    datalist = en.split('id="trade-locations"')[1].split("</datalist>")[0]
    assert "Dorm entrance" in datalist
    assert "宿舍楼下" not in datalist


def test_publish_rejects_fake_image_through_route(client, seed):
    login(client)
    response = _post_item(client, images=(BytesIO(b"not an image"), "evil.png"))
    assert "图片格式不支持或超过 5 MB" in response.get_data(as_text=True)


def test_publish_rejects_oversized_category_id(client, seed):
    login(client)
    response = _post_item(client, category_id="999999999999999999999")
    assert response.status_code == 200
    assert "请选择有效分类" in response.get_data(as_text=True)
