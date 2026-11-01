def test_post_without_csrf_returns_400(client, seed):
    assert client.post("/login", data={"student_id": "x", "password": "y"}).status_code == 400


def test_post_with_wrong_csrf_returns_400(client, seed):
    assert client.post("/login", data={
        "student_id": "x", "password": "y", "csrf_token": "wrong",
    }).status_code == 400


def test_validate_password_rules():
    from app.security import validate_password
    assert validate_password("short") is not None
    assert validate_password("allletters") is not None
    assert validate_password("Passw0rd!") is None


def test_safe_next_url_blocks_control_characters():
    from app.security import safe_next_url
    assert safe_next_url("/items") == "/items"
    assert safe_next_url("/items?q=1") == "/items?q=1"
    assert safe_next_url("//evil.example") is None
    assert safe_next_url("/\evil.example") is None
    assert safe_next_url("https://evil.example") is None
    assert safe_next_url("/%09/evil.example") is None
    assert safe_next_url("/\t/evil.example") is None


def test_language_switch_blocks_encoded_redirect(client):
    response = client.get("/lang/en?next=/%09/evil.example/phish")
    assert response.status_code == 302
    assert response.headers["Location"].endswith("/")
