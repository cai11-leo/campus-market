from app import db


def test_public_list_excludes_unavailable_and_removed(client, add_item):
    add_item(title="在售教材")
    add_item(title="已售球拍", status="sold")
    add_item(title="暂停台灯", status="unavailable")
    add_item(title="被删耳机", is_removed=1, removed_by="admin")
    html = client.get("/items").get_data(as_text=True)
    assert "在售教材" in html
    assert "已售球拍" in html
    assert "暂停台灯" not in html
    assert "被删耳机" not in html


def test_search_escapes_like_wildcards(client, add_item):
    add_item(title="100% new 教材")
    add_item(title="普通教材")
    html = client.get("/items?q=100%25").get_data(as_text=True)
    assert "100% new 教材" in html
    assert "普通教材" not in html


def test_search_escapes_underscore(client, add_item):
    add_item(title="A_B 笔记")
    add_item(title="AXB 笔记")
    html = client.get("/items?q=A_B").get_data(as_text=True)
    assert "A_B 笔记" in html
    assert "AXB 笔记" not in html


def test_sort_price_ascending(client, add_item):
    add_item(title="便宜", price=5)
    add_item(title="昂贵", price=500)
    html = client.get("/items?sort=price_asc").get_data(as_text=True)
    assert html.index("便宜") < html.index("昂贵")


def test_pagination_clamps_to_last_page(client, add_item):
    for i in range(15):
        add_item(title=f"商品{i:02d}")
    page2 = client.get("/items?page=2").get_data(as_text=True)
    assert "商品14" not in page2
    assert "商品00" in page2
    overflow = client.get("/items?page=99").get_data(as_text=True)
    assert "商品00" in overflow


def test_category_count_matches_default_list(app, client, add_item):
    add_item(title="分类A", category_id=1, status="on_sale")
    add_item(title="分类B", category_id=1, status="sold")
    add_item(title="分类C", category_id=1, status="unavailable")
    with app.app_context():
        from app.queries import fetch_categories
        books = next(c for c in fetch_categories() if c["slug"] == "books")
    assert books["visible_count"] == 2
    html = client.get("/category/books").get_data(as_text=True)
    assert "分类A" in html and "分类B" in html and "分类C" not in html


def test_inactive_category_hidden_but_items_remain(client, app, add_item):
    add_item(title="停用分类商品", category_id=7)
    with app.app_context():
        db.get_db().execute("UPDATE categories SET is_active = 0 WHERE id = 7")
        db.get_db().commit()
    assert "其他闲置" not in client.get("/categories").get_data(as_text=True)
    assert "停用分类商品" in client.get("/items").get_data(as_text=True)
    assert client.get("/category/other").status_code == 404


def test_item_rows_expose_category_name(app, add_item):
    add_item(title="分类名称测试")
    with app.app_context():
        from app.queries import fetch_items
        from app.utils import category_name
        row = fetch_items("public")["items"][0]
        assert category_name(row) == "教材书籍"


def test_search_chinese_text(client, add_item):
    add_item(title="高等数学教材")
    add_item(title="蓝牙耳机")
    html = client.get("/items?q=教材").get_data(as_text=True)
    assert "高等数学教材" in html
    assert "蓝牙耳机" not in html
