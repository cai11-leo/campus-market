from app import db
from tests.helpers import get_csrf, login


def test_register_creates_user_and_logs_in(app, client, seed):
    token = get_csrf(client, "/register")
    response = client.post("/register", data={
        "student_id": "2023999",
        "username": "新同学",
        "password": "Passw0rd!",
        "confirm_password": "Passw0rd!",
        "contact_wechat": "wx_new",
        "csrf_token": token,
    }, follow_redirects=True)
    assert response.status_code == 200
    with app.app_context():
        user = db.query_one("SELECT * FROM users WHERE student_id = ?", ("2023999",))
    assert user["username"] == "新同学"
    assert "新同学" in response.get_data(as_text=True)


def test_register_rejects_duplicate_student_id(client, seed):
    token = get_csrf(client, "/register")
    response = client.post("/register", data={
        "student_id": "2023001",
        "username": "重复",
        "password": "Passw0rd!",
        "confirm_password": "Passw0rd!",
        "contact_wechat": "wx",
        "csrf_token": token,
    })
    assert "该学号已注册" in response.get_data(as_text=True)


def test_login_wrong_password_shows_error(client, seed):
    response = login(client, password="wrong")
    assert "学号或密码不正确" in response.get_data(as_text=True)


def test_english_validation_message(client, seed):
    client.get("/lang/en")
    response = login(client, password="wrong")
    assert "Incorrect student ID or password" in response.get_data(as_text=True)


def test_login_success_and_logout(client, seed):
    response = login(client)
    assert "林小雨" in response.get_data(as_text=True)
    token = get_csrf(client, "/")
    client.post("/logout", data={"csrf_token": token}, follow_redirects=True)
    assert "登录" in client.get("/").get_data(as_text=True)


def test_open_redirect_is_blocked(client, seed):
    token = get_csrf(client, "/login")
    response = client.post("/login", data={
        "student_id": "2023001",
        "password": "Demo@12345",
        "next": "https://evil.example/phish",
        "csrf_token": token,
    })
    assert response.status_code == 302
    assert response.headers["Location"].endswith("/")


def test_login_blocks_encoded_control_redirect(client, seed):
    token = get_csrf(client, "/login")
    response = client.post("/login", data={
        "student_id": "2023001",
        "password": "Demo@12345",
        "next": "/%09/evil.example/phish",
        "csrf_token": token,
    })
    assert response.status_code == 302
    assert response.headers["Location"].endswith("/")


def test_share_admin_password_override(client, seed, monkeypatch):
    from werkzeug.security import generate_password_hash
    monkeypatch.setenv(
        "CAMPUS_SHARE_ADMIN_HASH", generate_password_hash("SharePass1")
    )
    original = login(client, "admin", "Admin@12345")
    assert "学号或密码不正确" in original.get_data(as_text=True)
    shared = login(client, "admin", "SharePass1")
    assert "平台管理员" in shared.get_data(as_text=True)
