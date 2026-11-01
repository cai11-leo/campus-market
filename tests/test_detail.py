from tests.helpers import login


def test_on_sale_detail_shows_contact_only_when_logged_in(client, add_item, seed):
    item_id = add_item(title="在售耳机")
    anonymous = client.get(f"/item/{item_id}").get_data(as_text=True)
    assert "在售耳机" in anonymous
    assert "wx_2023001" not in anonymous
    login(client)
    member = client.get(f"/item/{item_id}").get_data(as_text=True)
    assert "wx_2023001" in member


def test_sold_detail_is_visible_but_contact_hidden(client, add_item, seed):
    item_id = add_item(title="已售球拍", status="sold")
    login(client, "2023002")  # buyer / non-owner
    html = client.get(f"/item/{item_id}").get_data(as_text=True)
    assert "已售球拍" in html
    assert "wx_2023001" not in html
    assert "status-chip--sold" in html
    login(client, "2023001")  # owner sees own contact
    assert "wx_2023001" in client.get(f"/item/{item_id}").get_data(as_text=True)


def test_paused_detail_hides_contact_and_shows_notice(client, add_item, seed):
    item_id = add_item(title="暂停台灯", status="unavailable")
    login(client, "2023002")
    html = client.get(f"/item/{item_id}").get_data(as_text=True)
    assert "暂停出售" in html
    assert "wx_2023001" not in html
    assert "暂不出售" in html
    login(client, "2023001")
    assert "wx_2023001" in client.get(f"/item/{item_id}").get_data(as_text=True)


def test_admin_removed_public_404_owner_sees_reason(client, add_item, seed):
    item_id = add_item(title="违规商品", is_removed=1, removed_by="admin")
    assert client.get(f"/item/{item_id}").status_code == 404
    login(client)
    html = client.get(f"/item/{item_id}").get_data(as_text=True)
    assert "已下架" in html
    assert "违规商品" in html


def test_seller_deleted_only_admin_can_view(client, add_item, seed):
    item_id = add_item(title="删除商品", is_removed=1, removed_by="seller")
    login(client)
    assert client.get(f"/item/{item_id}").status_code == 404
    login(client, "admin", "Admin@12345")
    assert client.get(f"/item/{item_id}").status_code == 200


def test_view_count_increments_for_non_owner_only(client, app, add_item, seed):
    item_id = add_item(title="计数商品", seller_id=1, view_count=5)
    client.get(f"/item/{item_id}")
    with app.app_context():
        from app import db
        assert db.query_one(
            "SELECT view_count FROM items WHERE id = ?", (item_id,)
        )["view_count"] == 6
    login(client, "2023002")  # non-owner
    client.get(f"/item/{item_id}")
    with app.app_context():
        from app import db
        assert db.query_one(
            "SELECT view_count FROM items WHERE id = ?", (item_id,)
        )["view_count"] == 7
    login(client, "2023001")  # owner
    client.get(f"/item/{item_id}")
    with app.app_context():
        from app import db
        assert db.query_one(
            "SELECT view_count FROM items WHERE id = ?", (item_id,)
        )["view_count"] == 7


def test_paused_public_detail_has_no_private_controls(client, add_item, seed):
    item_id = add_item(title="暂停台灯", status="unavailable")
    login(client, "2023002")
    html = client.get(f"/item/{item_id}").get_data(as_text=True)
    assert "暂不出售" in html
    assert "wx_2023001" not in html
    for fragment in (
        f"/item/{item_id}/edit",
        f"/item/{item_id}/status",
        f"/item/{item_id}/delete",
        f"/item/{item_id}/favorite",
        f"/item/{item_id}/report",
    ):
        assert fragment not in html


def test_removed_read_only_views_have_no_controls(client, add_item, seed):
    admin_removed = add_item(title="下架商品", is_removed=1, removed_by="admin")
    seller_deleted = add_item(title="删除商品", is_removed=1, removed_by="seller")
    login(client, "2023001")
    html = client.get(f"/item/{admin_removed}").get_data(as_text=True)
    assert "已下架" in html
    for fragment in (
        f"/item/{admin_removed}/edit",
        f"/item/{admin_removed}/status",
        f"/item/{admin_removed}/delete",
        f"/item/{admin_removed}/favorite",
        f"/item/{admin_removed}/report",
    ):
        assert fragment not in html
    login(client, "admin", "Admin@12345")
    html = client.get(f"/item/{seller_deleted}").get_data(as_text=True)
    assert "已被卖家删除" in html
    assert f"/item/{seller_deleted}/edit" not in html


def test_huge_item_id_returns_404(client):
    assert client.get("/item/999999999999999999999999").status_code == 404
