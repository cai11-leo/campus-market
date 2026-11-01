def test_default_language_is_chinese(client):
    html = client.get("/").get_data(as_text=True)
    assert 'lang="zh-CN"' in html
    assert "校园集市" in html
    assert "首页" in html


def test_switch_to_english_persists(client):
    response = client.get("/lang/en?next=/")
    assert response.status_code == 302
    html = client.get("/").get_data(as_text=True)
    assert 'lang="en"' in html
    assert "Campus Market" in html
    assert "Home" in html


def test_invalid_language_returns_404(client):
    assert client.get("/lang/fr").status_code == 404
