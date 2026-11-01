def test_home_renders_latest_and_popular(client, seed, add_item):
    add_item(title="首页在售商品", seller_id=1, view_count=50)
    add_item(title="首页已售商品", seller_id=1, status="sold", view_count=999)
    html = client.get("/").get_data(as_text=True)
    assert "首页在售商品" in html
    assert "首页已售商品" in html


def test_home_popular_only_includes_on_sale(app, client, seed, add_item):
    on_sale = add_item(title="热门在售", seller_id=1, view_count=50)
    sold = add_item(title="热门已售", seller_id=1, status="sold", view_count=999)
    with app.app_context():
        from app.blueprints.main import build_home_data
        popular_ids = {row["id"] for row in build_home_data()["popular"]}
    assert on_sale in popular_ids
    assert sold not in popular_ids
    assert "热门在售" in client.get("/").get_data(as_text=True)


def test_custom_error_pages(client):
    html = client.get("/does-not-exist").get_data(as_text=True)
    assert "页面不存在" in html
