# Campus Market Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a runnable bilingual campus second-hand marketplace with real accounts, listings, status control, moderation, tests, and course-ready documentation.

**Architecture:** Flask application factory with five blueprints (auth, main, items, account, admin), server-rendered Jinja templates, a thin SQL query layer over SQLite, session-based authentication and i18n, and local file uploads. No build step, no CDN, no external services.

**Tech Stack:** Python 3.13, Flask 3.1.3, SQLite (stdlib `sqlite3`), Jinja2, vanilla CSS/JS, pytest.

**Spec:** `docs/superpowers/specs/2026-11-01-campus-market-design.md`

## Global Constraints

- Python 3.13; Flask 3.1.3; pytest 8+; no runtime dependency beyond Flask.
- SQLite only; `PRAGMA foreign_keys = ON` on every connection.
- All data, fonts, icons, and images local; no CDN or external network calls at runtime.
- UTF-8 everywhere; templates and responses return UTF-8 HTML.
- Default language `zh`; English via session; every system string goes through `t()`.
- Images: 1–5 per item, each ≤ 5 MB, formats `jpg/jpeg/png/webp`, validated by extension + magic bytes; stored under `static/uploads/` with UUID names.
- Public item lists: 12 per page; admin item lists: 20 per page.
- Status values: `on_sale`, `sold`, `unavailable`. Soft-delete values: `is_removed`, `removed_by` in `admin|seller`.
- CSRF token required on every POST; missing/invalid token returns 400.
- Do not run `git commit` unless the human partner explicitly asks. Each task ends with a test checkpoint instead.
- Never hard-delete items, users, or categories through the app.

## Review Focus

These are the inputs and failures the spec implies but no single feature test owns. Each gets a test in the task noted.

1. Direct-URL access to paused, admin-removed, and seller-deleted items must not leak contact details or editable controls — Task 5.
2. Uploaded files with a fake extension, oversized body, too many files, or traversal-style names must be rejected or neutralized — Task 6.
3. Crafted POSTs from non-owners (edit, status, delete) and POSTs without CSRF must fail with 403/400 — Task 6.
4. Validation errors and flash messages must still be translated after switching to English — Task 3 and Task 6.
5. Search with Chinese text, `%`, `_`, pagination overflow, and category counts must agree with the rendered list — Task 4.

---

### Task 1: Project Scaffold, Config, and Database Schema

**Files:**
- Create: `requirements.txt`, `config.py`, `run.py`, `schema.sql`, `.gitignore`, `pytest.ini`
- Create: `app/__init__.py`, `app/db.py`
- Create: `tests/__init__.py`, `tests/conftest.py`, `tests/test_app.py`

**Interfaces:**
- Consumes: nothing.
- Produces:
  - `create_app(test_config: dict | None = None) -> Flask`
  - `get_db() -> sqlite3.Connection` (row factory `sqlite3.Row`, foreign keys ON)
  - `close_db(exception=None) -> None`
  - `init_db() -> None` (executes `schema.sql` in the current app context)
  - `query_one(sql, args=()) -> sqlite3.Row | None`
  - `query_all(sql, args=()) -> list[sqlite3.Row]`
  - `execute(sql, args=()) -> int` (commits, returns `lastrowid`)

- [ ] **Step 1: Write the test fixture and failing schema test**

`tests/conftest.py`:

```python
import pytest


@pytest.fixture
def app(tmp_path):
    from app import create_app
    app = create_app({
        "TESTING": True,
        "SECRET_KEY": "test-secret",
        "DATABASE": str(tmp_path / "test.db"),
        "UPLOAD_FOLDER": str(tmp_path / "uploads"),
        "ITEMS_PER_PAGE": 12,
        "MAX_IMAGES": 5,
    })
    yield app


@pytest.fixture
def client(app):
    return app.test_client()
```

`tests/test_app.py`:

```python
from app import db


def test_schema_creates_all_tables(app):
    with app.app_context():
        names = {
            row["name"]
            for row in db.get_db().execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            )
        }
    assert {
        "users", "categories", "items", "item_images",
        "favorites", "browse_history", "reports",
    } <= names


def test_foreign_keys_are_enabled(app):
    with app.app_context():
        assert db.get_db().execute("PRAGMA foreign_keys").fetchone()[0] == 1
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python -m pytest tests/test_app.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app'`.

- [ ] **Step 3: Implement config, schema, and app factory**

`requirements.txt`:

```text
Flask==3.1.3
pytest>=8.0
```

`pytest.ini`:

```ini
[pytest]
testpaths = tests
pythonpath = .
```

`tests/__init__.py` is empty.

`config.py` defines a `Config` class with these exact defaults:

```python
BASE_DIR = Path(__file__).resolve().parent
SECRET_KEY = os.environ.get("SECRET_KEY", "dev-only-change-me")
DATABASE = os.environ.get("DATABASE", str(BASE_DIR / "instance" / "campus_market.db"))
UPLOAD_FOLDER = str(BASE_DIR / "static" / "uploads")
MAX_CONTENT_LENGTH = 30 * 1024 * 1024
ITEMS_PER_PAGE = 12
ADMIN_ITEMS_PER_PAGE = 20
MAX_IMAGES = 5
MAX_IMAGE_BYTES = 5 * 1024 * 1024
ALLOWED_IMAGE_EXTENSIONS = {"jpg", "jpeg", "png", "webp"}
```

`schema.sql` (exact; execute with `executescript`):

```sql
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id TEXT NOT NULL UNIQUE,
    username TEXT NOT NULL,
    password_hash TEXT NOT NULL,
    contact_wechat TEXT,
    contact_phone TEXT,
    role TEXT NOT NULL DEFAULT 'student' CHECK (role IN ('student', 'admin')),
    is_active INTEGER NOT NULL DEFAULT 1 CHECK (is_active IN (0, 1)),
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS categories (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    slug TEXT NOT NULL UNIQUE,
    name_zh TEXT NOT NULL,
    name_en TEXT NOT NULL,
    icon TEXT NOT NULL DEFAULT 'box',
    sort_order INTEGER NOT NULL DEFAULT 0,
    is_active INTEGER NOT NULL DEFAULT 1 CHECK (is_active IN (0, 1))
);

CREATE TABLE IF NOT EXISTS items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    seller_id INTEGER NOT NULL REFERENCES users(id),
    category_id INTEGER NOT NULL REFERENCES categories(id),
    title TEXT NOT NULL,
    description TEXT NOT NULL,
    price REAL NOT NULL CHECK (price >= 0 AND price <= 99999),
    original_price REAL CHECK (
        original_price IS NULL
        OR (original_price >= 0 AND original_price <= 99999)
    ),
    condition TEXT CHECK (
        condition IS NULL
        OR condition IN ('new', 'like_new', 'good', 'fair')
    ),
    trade_location TEXT,
    status TEXT NOT NULL DEFAULT 'on_sale'
        CHECK (status IN ('on_sale', 'sold', 'unavailable')),
    view_count INTEGER NOT NULL DEFAULT 0,
    is_removed INTEGER NOT NULL DEFAULT 0 CHECK (is_removed IN (0, 1)),
    removed_by TEXT CHECK (removed_by IS NULL OR removed_by IN ('admin', 'seller')),
    removed_reason TEXT,
    removed_at TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS item_images (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    item_id INTEGER NOT NULL REFERENCES items(id) ON DELETE CASCADE,
    filename TEXT NOT NULL,
    sort_order INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS favorites (
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    item_id INTEGER NOT NULL REFERENCES items(id) ON DELETE CASCADE,
    created_at TEXT NOT NULL,
    PRIMARY KEY (user_id, item_id)
);

CREATE TABLE IF NOT EXISTS browse_history (
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    item_id INTEGER NOT NULL REFERENCES items(id) ON DELETE CASCADE,
    viewed_at TEXT NOT NULL,
    PRIMARY KEY (user_id, item_id)
);

CREATE TABLE IF NOT EXISTS reports (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    item_id INTEGER NOT NULL REFERENCES items(id) ON DELETE CASCADE,
    reporter_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    reason TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending'
        CHECK (status IN ('pending', 'resolved', 'dismissed')),
    created_at TEXT NOT NULL,
    handled_at TEXT
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_reports_pending_unique
    ON reports(item_id, reporter_id) WHERE status = 'pending';
CREATE INDEX IF NOT EXISTS idx_items_public
    ON items(is_removed, status, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_items_category
    ON items(category_id, is_removed, status);
CREATE INDEX IF NOT EXISTS idx_items_seller ON items(seller_id);
CREATE INDEX IF NOT EXISTS idx_items_views ON items(view_count DESC);
CREATE INDEX IF NOT EXISTS idx_images_item ON item_images(item_id, sort_order);
CREATE INDEX IF NOT EXISTS idx_favorites_user ON favorites(user_id);
CREATE INDEX IF NOT EXISTS idx_history_user ON browse_history(user_id, viewed_at DESC);
CREATE INDEX IF NOT EXISTS idx_reports_status ON reports(status, created_at);
```

`app/db.py`:

```python
import sqlite3
from pathlib import Path

from flask import current_app, g


def get_db() -> sqlite3.Connection:
    if "db" not in g:
        g.db = sqlite3.connect(current_app.config["DATABASE"])
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
    return g.db


def close_db(exception=None) -> None:
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db() -> None:
    db = get_db()
    schema_path = Path(current_app.root_path).parent / "schema.sql"
    db.executescript(schema_path.read_text(encoding="utf-8"))
    db.commit()


def query_one(sql, args=()):
    return get_db().execute(sql, args).fetchone()


def query_all(sql, args=()):
    return get_db().execute(sql, args).fetchall()


def execute(sql, args=()):
    db = get_db()
    cur = db.execute(sql, args)
    db.commit()
    return cur.lastrowid


def init_app(app) -> None:
    app.teardown_appcontext(close_db)
```

`app/__init__.py` implements the factory:

```python
def create_app(test_config: dict | None = None) -> Flask:
    app = Flask(__name__, instance_relative_config=True)
    app.config.from_object(Config)
    if test_config:
        app.config.update(test_config)
    Path(app.instance_path).mkdir(parents=True, exist_ok=True)
    Path(app.config["UPLOAD_FOLDER"]).mkdir(parents=True, exist_ok=True)
    db.init_app(app)
    with app.app_context():
        db.init_db()
    return app
```

`run.py` imports `create_app`, creates `app`, and runs `app.run(debug=True)`.

`.gitignore` must exclude `.venv/`, `__pycache__/`, `*.pyc`, `instance/`, `.pytest_cache/`, and `static/uploads/*` while keeping `static/uploads/.gitkeep`.

- [ ] **Step 4: Run the tests to verify they pass**

Run: `python -m pytest tests/test_app.py -v`
Expected: 2 passed.

- [ ] **Step 5: Checkpoint**

Run: `python -c "from app import create_app; print(create_app().name)"`
Expected: prints `app` with no traceback.

---

### Task 2: i18n Foundation, Base Layout, and Home Shell

**Files:**
- Create: `app/i18n.py`, `app/utils.py`
- Create: `app/blueprints/__init__.py`, `app/blueprints/main.py`
- Create: `templates/base.html`, `templates/partials/nav.html`, `templates/partials/footer.html`, `templates/partials/flash.html`
- Create: `templates/index.html`
- Create: `static/css/style.css`, `static/js/app.js`, `static/img/logo.svg`
- Modify: `app/__init__.py`
- Test: `tests/test_i18n.py`

**Interfaces:**
- Consumes: `create_app` from Task 1.
- Produces:
  - `t(key: str, **kwargs) -> str` — returns the translation or the key itself if missing.
  - `get_locale() -> str` — `"zh"` or `"en"` from `session["lang"]`; default `"zh"`.
  - Jinja globals: `t`, `locale`, `languages`, `current_user` (None until Task 3), `csrf_token` (empty placeholder until Task 3), `category_name`, `status_label`, `condition_label`, `money`, `dt`, `url_with_page`.
  - `main.bp` with `GET /`, `GET /lang/<lang>`, `POST`-free language switch.

- [ ] **Step 1: Write the failing i18n tests**

`tests/test_i18n.py`:

```python
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
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python -m pytest tests/test_i18n.py -v`
Expected: FAIL with 404 or missing strings because the home route does not exist.

- [ ] **Step 3: Implement i18n, base layout, and home**

`app/i18n.py` must contain at least these exact entries:

| Key | zh | en |
|---|---|---|
| `brand.name` | 校园集市 | Campus Market |
| `brand.tagline` | 让闲置在校园里继续发光 | Give idle things a second life on campus |
| `nav.home` | 首页 | Home |
| `nav.items` | 全部商品 | All items |
| `nav.categories` | 分类浏览 | Categories |
| `nav.publish` | 发布闲置 | Post item |
| `nav.my_items` | 我的发布 | My listings |
| `nav.profile` | 个人中心 | Profile |
| `nav.login` | 登录 | Log in |
| `nav.register` | 注册 | Sign up |
| `nav.logout` | 退出登录 | Log out |
| `nav.admin` | 后台管理 | Admin |
| `status.on_sale` | 在售 | On sale |
| `status.sold` | 已售 | Sold |
| `status.unavailable` | 暂停出售 | Paused |
| `condition.new` | 全新 | New |
| `condition.like_new` | 95新 | Like new |
| `condition.good` | 8成新 | Good |
| `condition.fair` | 一般 | Fair |
| `home.hero.title` | 让闲置在校园里继续发光 | Give idle things a second life on campus |
| `home.hero.subtitle` | 只面向本校学生的二手集市，状态实时更新，告别无效询问。 | A campus-only marketplace with live item status, so you never chase a sold item again. |
| `home.latest` | 最新发布 | Just posted |
| `home.popular` | 最热浏览 | Most viewed |
| `home.categories` | 按分类逛 | Browse by category |
| `home.empty` | 还没有商品，来发布第一件闲置吧。 | Nothing here yet. Post the first item. |
| `common.view_all` | 查看全部 | View all |
| `common.search` | 搜索 | Search |
| `common.empty` | 暂无内容 | Nothing here yet |

`t()` formats placeholders with `str.format(**kwargs)`, so entries may contain `{count}`. `init_app(app)` registers a context processor returning `t`, `locale`, `languages`, and locale-aware helpers, and a Jinja global for each helper.

`app/utils.py` provides:

```python
def money(value) -> str                 # "¥20.00"; None -> "—"
def dt(value: str) -> str               # zh: 2026年11月1日; en: 1 Nov 2026
def category_name(row) -> str           # picks name_zh/name_en from row
def status_label(status: str) -> str    # t("status." + status)
def condition_label(condition) -> str   # t("condition." + condition) or "—"
def url_with_page(page: int) -> str     # current endpoint + args with page replaced
```

`app/blueprints/main.py`:

```python
bp = Blueprint("main", __name__)

@bp.get("/")
def index():
    return render_template("index.html")

@bp.get("/lang/<lang>")
def set_language(lang: str):
    if lang not in ("zh", "en"):
        abort(404)
    session["lang"] = lang
    target = request.args.get("next", "/")
    return redirect(target if target.startswith("/") and not target.startswith("//") else "/")
```

`templates/base.html` sets `<html lang="{{ 'en' if locale == 'en' else 'zh-CN' }}">`, includes nav/flash/footer, and defines `{% block title %}`, `{% block content %}`, `{% block scripts %}`. The nav shows the logo, brand name, Home link, language switch (`中文` / `English`), and nothing else until later tasks add links.

`templates/index.html` renders the hero with the tagline, a static three-slide carousel shell (text-only slides; JS added in Task 10), and empty-state sections for latest/popular/categories. All text uses `t()`.

`static/css/style.css` starts with the design tokens from the spec §8.2 and base layout styles. Invoke the `frontend-design` skill before writing this file and follow the spec's visual direction: light blue and white, 18px radius, friendly campus noticeboard feel, no template-default look. `static/js/app.js` is created empty with a comment.

- [ ] **Step 4: Run the tests to verify they pass**

Run: `python -m pytest tests/test_i18n.py -v`
Expected: 3 passed.

- [ ] **Step 5: Checkpoint**

Run: `python -m pytest -q`
Expected: all tests pass.

---

### Task 3: Authentication, Sessions, CSRF, and Navigation User Area

**Files:**
- Create: `app/security.py`, `app/blueprints/auth.py`
- Create: `templates/login.html`, `templates/register.html`
- Modify: `app/__init__.py`, `templates/partials/nav.html`, `static/css/style.css`
- Modify: `tests/conftest.py`
- Test: `tests/test_auth.py`, `tests/test_security.py`

**Interfaces:**
- Consumes: `query_one`, `execute`, `t`, `get_locale`.
- Produces:
  - `get_current_user() -> sqlite3.Row | None`
  - `login_required(view)` / `admin_required(view)` decorators, redirecting to `auth.login?next=...` or aborting 403.
  - `csrf_token() -> str` Jinja global and `validate_csrf()` request hook.
  - `safe_next_url(target: str | None) -> str | None`
  - `validate_password(password: str) -> str | None` returning an i18n key or None.
  - Session keys: `user_id`, `lang`, `csrf_token`.
  - `auth.bp` endpoints `auth.login`, `auth.register`, `auth.logout`.
  - `tests/helpers.py` with `get_csrf(client, path="/login")` and `login(client, student_id="2023001", password="Demo@12345")`.

- [ ] **Step 1: Extend the fixture and write failing auth tests**

Extend `tests/conftest.py` with a `seed` fixture that inserts the 7 categories and 4 users:

- Categories: `books/教材书籍/Books`, `digital/电子数码/Electronics`, `life/生活用品/Daily life`, `sports/运动健身/Sports`, `fashion/美妆衣物/Fashion`, `stationery/文具文创/Stationery`, `other/其他闲置/Other`.
- Users: `2023001/林小雨/student`, `2023002/陈子昂/student`, `2023003/苏晴/student`, `admin/平台管理员/admin`.
- Passwords: students `Demo@12345`; admin `Admin@12345`.
- Contacts: `contact_wechat = "wx_" + student_id`, `contact_phone = "1380000000" + last digit`.

`tests/helpers.py`:

```python
import re


def get_csrf(client, path="/login"):
    html = client.get(path).get_data(as_text=True)
    return re.search(r'name="csrf_token" value="([^"]+)"', html).group(1)


def login(client, student_id="2023001", password="Demo@12345"):
    token = get_csrf(client, "/login")
    return client.post(
        "/login",
        data={"student_id": student_id, "password": password, "csrf_token": token},
        follow_redirects=True,
    )
```

`tests/test_auth.py`:

```python
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


def test_login_success_and_logout(client, seed):
    response = login(client)
    assert "林小雨" in response.get_data(as_text=True)
    token = get_csrf(client, "/")
    client.post("/logout", data={"csrf_token": token}, follow_redirects=True)
    assert "登录" in client.get("/").get_data(as_text=True)


def test_english_validation_message(client, seed):
    client.get("/lang/en")
    response = login(client, password="wrong")
    assert "Incorrect student ID or password" in response.get_data(as_text=True)


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
```

`tests/test_security.py`:

```python
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
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python -m pytest tests/test_auth.py tests/test_security.py -v`
Expected: FAIL with 404 or missing routes.

- [ ] **Step 3: Implement security and auth**

`app/security.py`:

- `get_current_user()` reads `session.get("user_id")`, queries `users`, returns `None` if missing or `is_active = 0`.
- `login_required(view)` wraps the view; if no user, flashes `flash.login_required` and redirects to `url_for("auth.login", next=request.full_path)`.
- `admin_required(view)` calls `login_required` behavior first, then `abort(403)` unless `current_user["role"] == "admin"`.
- `init_app(app)` registers a `before_request` hook that sets `g.user`, ensures `session["csrf_token"]` exists, and validates `request.form["csrf_token"]` on POST with `secrets.token_hex` comparison (`abort(400)` on failure). Static requests may skip the user query.
- `safe_next_url` returns the target only when it starts with `/` and not `//`.
- `validate_password` requires length ≥ 8, at least one letter, and at least one digit; returns `"auth.error.password_weak"` otherwise.
- Context processor exposes `current_user` and `csrf_token()`.

`app/blueprints/auth.py`:

- `GET/POST /register`: fields `student_id`, `username`, `password`, `confirm_password`, `contact_wechat`, `contact_phone`. Validate student ID with `^[A-Za-z0-9]{4,20}$`, username 2–30 characters, passwords match, password rules, and at least one contact. Insert with `generate_password_hash`; set `session["user_id"]`; flash `auth.flash.welcome`; redirect `/`.
- `GET/POST /login`: render the login page even when a session already exists (this lets a user switch accounts in one browser and keeps tests simple). Find by `student_id`, check `check_password_hash`; on success preserve `lang`, clear session, set `user_id`, regenerate CSRF token, redirect to `safe_next_url(next)` or `/`; on failure re-render with `auth.error.invalid_credentials`.
- `POST /logout`: clear session, redirect `/`.

Add these i18n entries exactly:

| Key | zh | en |
|---|---|---|
| `auth.login.title` | 登录校园集市 | Log in to Campus Market |
| `auth.register.title` | 注册校园集市 | Join Campus Market |
| `auth.field.student_id` | 学号 | Student ID |
| `auth.field.username` | 昵称 | Display name |
| `auth.field.password` | 密码 | Password |
| `auth.field.confirm_password` | 确认密码 | Confirm password |
| `auth.field.wechat` | 微信号 | WeChat |
| `auth.field.phone` | 手机号 | Phone |
| `auth.error.invalid_credentials` | 学号或密码不正确 | Incorrect student ID or password |
| `auth.error.password_weak` | 密码至少 8 位，且包含字母和数字 | Password must be at least 8 characters with letters and digits |
| `auth.error.password_mismatch` | 两次输入的密码不一致 | Passwords do not match |
| `auth.error.student_id_taken` | 该学号已注册 | This student ID is already registered |
| `auth.error.contact_required` | 请至少填写一种联系方式 | Provide at least one contact method |
| `auth.error.invalid_student_id` | 学号需为 4–20 位字母或数字 | Student ID must be 4–20 letters or digits |
| `flash.login_required` | 请先登录 | Please log in first |
| `auth.flash.welcome` | 欢迎，{name} | Welcome, {name} |
| `auth.flash.logged_out` | 已退出登录 | Logged out |

Templates: `login.html` and `register.html` extend `base.html`, include the CSRF hidden field, show field-level errors, and link to each other. Update `nav.html`: when logged in show username, My listings (link added in Task 7; until then render plain text), and a Logout **POST form** containing the CSRF hidden input; otherwise show Log in and Sign up. The logout form is what lets tests and later pages obtain a session CSRF token from any authenticated page.

- [ ] **Step 4: Run the tests to verify they pass**

Run: `python -m pytest tests/test_auth.py tests/test_security.py -v`
Expected: all pass.

- [ ] **Step 5: Checkpoint**

Run: `python -m pytest -q`
Expected: all tests pass.

---

### Task 4: Query Layer, Listings, Search, Sorting, Pagination, Categories

**Files:**
- Create: `app/queries.py`, `app/blueprints/items.py`
- Create: `templates/items.html`, `templates/categories.html`
- Create: `templates/partials/item_card.html`, `templates/partials/pagination.html`, `templates/partials/empty_state.html`
- Modify: `app/blueprints/main.py`, `templates/partials/nav.html`, `app/__init__.py`, `static/css/style.css`
- Test: `tests/test_listing.py`

**Interfaces:**
- Consumes: db helpers, i18n, `get_current_user` not required.
- Produces:
  - `fetch_items(scope="public", *, q=None, category_slug=None, status=None, removed=None, seller_id=None, sort="latest", page=1, per_page=12) -> dict` with keys `items`, `total`, `page`, `pages`, `per_page`.
  - `fetch_categories(active_only=True) -> list[sqlite3.Row]` including `visible_count`.
  - `fetch_category_by_slug(slug) -> sqlite3.Row | None`.
  - Item rows include: all `items.*`, `category_slug`, `category_name_zh`, `category_name_en`, `seller_name`, `seller_student_id`, `contact_wechat`, `contact_phone`, `cover`.
  - `items.bp` endpoints `items.list_items`, `items.category`.
  - `main.categories` endpoint.
  - Jinja macro `item_card(item)` from `partials/item_card.html`.

- [ ] **Step 1: Write failing listing tests**

Add a fixture/factory in `tests/conftest.py`:

```python
@pytest.fixture
def add_item(app, seed):
    def _add(**overrides):
        data = {
            "seller_id": 1, "category_id": 1, "title": "旧教材",
            "description": "九成新，无笔记", "price": 20.0,
            "status": "on_sale", "view_count": 0, "is_removed": 0,
            "removed_by": None, "created_at": "2026-10-01 10:00:00",
        }
        data.update(overrides)
        with app.app_context():
            cur = db.get_db().execute(
                """INSERT INTO items
                (seller_id, category_id, title, description, price, status,
                 view_count, is_removed, removed_by, removed_at,
                 created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    data["seller_id"], data["category_id"], data["title"],
                    data["description"], data["price"], data["status"],
                    data["view_count"], data["is_removed"], data["removed_by"],
                    "2026-10-02 10:00:00" if data["is_removed"] else None,
                    data["created_at"], data["created_at"],
                ),
            )
            db.get_db().commit()
            return cur.lastrowid
    return _add
```

`tests/test_listing.py`:

```python
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
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python -m pytest tests/test_listing.py -v`
Expected: FAIL with 404 or missing query module.

- [ ] **Step 3: Implement queries and listing pages**

`app/queries.py` builds a shared SELECT:

```sql
SELECT i.*, c.slug AS category_slug,
       c.name_zh AS category_name_zh, c.name_en AS category_name_en,
       u.username AS seller_name, u.student_id AS seller_student_id,
       u.contact_wechat, u.contact_phone,
       (SELECT filename FROM item_images
        WHERE item_id = i.id ORDER BY sort_order, id LIMIT 1) AS cover
FROM items i
JOIN categories c ON c.id = i.category_id
JOIN users u ON u.id = i.seller_id
```

Scope SQL:

- `public`: `i.is_removed = 0 AND i.status IN ('on_sale','sold')`; optional `status` narrows to one of those.
- `seller`: `i.seller_id = ? AND NOT (i.is_removed = 1 AND i.removed_by = 'seller')`; optional status any of the three.
- `admin`: no default removal filter; `removed` filter `none` (`is_removed = 0`), `admin`, `seller`, or omitted for all.

Filters: `q` matches `title LIKE ? ESCAPE '\' OR description LIKE ? ESCAPE '\'`, with `\`, `%`, `_` escaped. Category by slug. Sort map:

```python
{"latest": "i.created_at DESC, i.id DESC",
 "price_asc": "i.price ASC, i.id DESC",
 "price_desc": "i.price DESC, i.id DESC",
 "views": "i.view_count DESC, i.id DESC"}
```

Pagination: clamp `page` to ≥ 1; compute `pages = max(1, ceil(total / per_page))`; clamp page to `pages`; apply `LIMIT ? OFFSET ?`.

`fetch_categories` uses a correlated count of visible items (`is_removed = 0 AND status IN ('on_sale','sold')`) as `visible_count`, ordered by `sort_order, id`; `active_only` adds `is_active = 1`.

`items.list_items` reads `q`, `category`, `status`, `sort`, `page`, `per_page = 12`; renders `items.html`. `items.category` looks up the slug (active only, else 404) and renders the same template with the category locked. `main.categories` renders active categories with counts. Add nav links for All items and Categories.

`templates/items.html` renders a filter bar (search input, category select, status chips, sort select), the grid of item cards, pagination, and empty state. `partials/item_card.html`:

```jinja
{% macro item_card(item) %}
<a class="item-card {{ 'is-sold' if item.status == 'sold' }}"
   href="/item/{{ item.id }}">
  <div class="item-card__media">
    <img src="{{ url_for('static', filename=item.cover or 'img/placeholders/other-1.svg') }}"
         alt="{{ item.title }}" loading="lazy">
    <span class="status-chip status-chip--{{ item.status }}">
      {{ status_label(item.status) }}
    </span>
  </div>
  <div class="item-card__body">
    <h3>{{ item.title }}</h3>
    <p class="price">{{ money(item.price) }}</p>
    {% if item.original_price %}<s>{{ money(item.original_price) }}</s>{% endif %}
    <p class="meta">{{ category_name(item) }} · {{ condition_label(item.condition) }}</p>
    <p class="meta">{{ dt(item.created_at) }} · {{ item.view_count }}</p>
  </div>
</a>
{% endmacro %}
```

Use `item.status` to add `status-chip--on_sale|sold|unavailable` classes. The status filter must never accept `unavailable` on public pages.

- [ ] **Step 4: Run the tests to verify they pass**

Run: `python -m pytest tests/test_listing.py -v`
Expected: all pass.

- [ ] **Step 5: Checkpoint**

Run: `python -m pytest -q`
Expected: all tests pass.

---

### Task 5: Item Detail, Access Modes, Contact Visibility, View Counts, History Recording

**Files:**
- Create: `app/permissions.py`, `templates/item_detail.html`
- Modify: `app/blueprints/items.py`, `app/queries.py`, `static/css/style.css`, `static/js/app.js`
- Test: `tests/test_detail.py`

**Interfaces:**
- Consumes: `fetch_items`, `fetch_item`, auth context.
- Produces:
  - `fetch_item(item_id: int) -> sqlite3.Row | None`
  - `fetch_item_images(item_id: int) -> list[sqlite3.Row]`
  - `item_access_mode(item: sqlite3.Row | None, user: sqlite3.Row | None) -> str` returning `full`, `paused_owner`, `paused_public`, `removed_admin`, `removed_seller`, or `denied`.
  - `items.detail` endpoint.
  - Session key `viewed` mapping item id → unix timestamp for 30-minute view dedupe.

- [ ] **Step 1: Write failing detail tests**

`tests/test_detail.py`:

```python
from tests.helpers import get_csrf, login


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
    login(client)
    html = client.get(f"/item/{item_id}").get_data(as_text=True)
    assert "已售球拍" in html
    assert "wx_2023001" not in html
    assert "status-chip--sold" in html


def test_paused_detail_hides_contact_and_shows_notice(client, add_item, seed):
    item_id = add_item(title="暂停台灯", status="unavailable")
    login(client)
    html = client.get(f"/item/{item_id}").get_data(as_text=True)
    assert "暂停出售" in html
    assert "wx_2023001" not in html
    assert "暂不出售" in html


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
        assert db.query_one("SELECT view_count FROM items WHERE id = ?", (item_id,))["view_count"] == 6
    login(client, "2023002")  # non-owner
    client.get(f"/item/{item_id}")
    with app.app_context():
        from app import db
        assert db.query_one("SELECT view_count FROM items WHERE id = ?", (item_id,))["view_count"] == 7
    login(client, "2023001")  # owner
    client.get(f"/item/{item_id}")
    with app.app_context():
        from app import db
        assert db.query_one("SELECT view_count FROM items WHERE id = ?", (item_id,))["view_count"] == 7
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python -m pytest tests/test_detail.py -v`
Expected: FAIL with 404.

- [ ] **Step 3: Implement permissions and detail page**

`app/permissions.py`:

```python
def item_access_mode(item, user) -> str:
    if item is None:
        return "denied"
    is_owner = user is not None and user["id"] == item["seller_id"]
    is_admin = user is not None and user["role"] == "admin"
    if not item["is_removed"]:
        if item["status"] == "unavailable":
            return "paused_owner" if (is_owner or is_admin) else "paused_public"
        return "full"
    if item["removed_by"] == "admin":
        return "removed_admin" if (is_owner or is_admin) else "denied"
    return "removed_seller" if is_admin else "denied"
```

Detail route:

- `item = fetch_item(item_id)`; `mode = item_access_mode(item, g.user)`; `mode == "denied"` → 404.
- Render `item_detail.html` with `item`, `images`, `mode`, `can_manage = mode in {"full","paused_owner"} and (owner or admin) and not removed`.
- Contact visible when `mode in {"full","paused_owner"}` and `g.user` is not None; owner/admin always see it. For sold items `mode == "full"` but contact must be hidden: add `contact_allowed = mode in {"full","paused_owner"} and item["status"] == "on_sale" and g.user is not None`.
- View count: increment only when `mode == "full"` and viewer is not the seller and not already counted within 30 minutes. Store `session["viewed"] = {str(id): unix_ts}`; mark `session.modified = True`.
- History: when `mode == "full"` and a logged-in non-owner views, upsert `browse_history` (`INSERT ... ON CONFLICT(user_id,item_id) DO UPDATE SET viewed_at = excluded.viewed_at`).
- Buttons: favorite/report only when `mode == "full"`; status controls later. Read-only banners for `paused_owner`, `removed_admin`, `removed_seller`; public paused notice for `paused_public`.

`item_detail.html` shows a gallery (all images with clickable thumbnails), status chip, title, price, original price, condition, location, description, seller nickname, date, view count, contact block, and action buttons. Sold items get a muted overlay. All state text uses `t()`/helpers.

Add i18n keys:

| Key | zh | en |
|---|---|---|
| `item.contact` | 联系卖家 | Contact seller |
| `item.login_to_contact` | 登录后查看联系方式 | Log in to see contact details |
| `item.not_available` | 暂不出售 | Temporarily unavailable |
| `item.sold_notice` | 该商品已售出 | This item has been sold |
| `item.removed_notice` | 该商品已被管理员下架 | This listing was removed by an admin |
| `item.removed_reason` | 下架原因 | Reason |
| `item.deleted_notice` | 该商品已被卖家删除 | This listing was deleted by the seller |
| `item.views` | {count} 次浏览 | {count} views |
| `item.description` | 商品描述 | Description |
| `item.location` | 交易地点 | Trade location |
| `item.condition` | 成色 | Condition |
| `item.posted_at` | 发布于 {date} | Posted {date} |
| `item.favorite` | 收藏 | Save |
| `item.favorited` | 已收藏 | Saved |
| `item.report` | 举报 | Report |
| `item.original_price` | 原价 | Original price |

- [ ] **Step 4: Run the tests to verify they pass**

Run: `python -m pytest tests/test_detail.py -v`
Expected: all pass.

- [ ] **Step 5: Checkpoint**

Run: `python -m pytest -q`
Expected: all tests pass.

---

### Task 6: Publish, Image Upload, Edit, Status Switching, Seller Delete

**Files:**
- Create: `app/uploads.py`, `templates/publish.html`, `templates/edit_item.html`
- Modify: `app/blueprints/items.py`, `app/security.py`, `templates/partials/nav.html`, `templates/item_detail.html`, `static/js/app.js`, `static/css/style.css`
- Test: `tests/test_publish.py`, `tests/test_status.py`, `tests/test_uploads.py`

**Interfaces:**
- Consumes: `login_required`, `get_current_user`, `fetch_item`, `item_access_mode`, `execute`.
- Produces:
  - `validate_image(file_storage) -> str | None` — returns an i18n error key or None.
  - `save_image(file_storage) -> str` — returns `"uploads/<uuid>.<ext>"`.
  - `delete_image(static_path: str) -> None` — only removes paths under `uploads/`.
  - `items.publish`, `items.edit`, `items.update_status`, `items.delete` endpoints.
  - `items.toggle_favorite`, `items.report` endpoints (favorite/report UI wired here; account page in Task 7).

- [ ] **Step 1: Write failing publish/status/upload tests**

`tests/test_uploads.py`:

```python
from io import BytesIO
from werkzeug.datastructures import FileStorage


def test_accepts_real_png_header():
    from app.uploads import validate_image
    f = FileStorage(stream=BytesIO(b"\x89PNG\r\n\x1a\n" + b"0" * 20), filename="a.png")
    assert validate_image(f) is None


def test_rejects_fake_extension():
    from app.uploads import validate_image
    f = FileStorage(stream=BytesIO(b"not an image"), filename="evil.png")
    assert validate_image(f) is not None


def test_rejects_oversized_file():
    from app.uploads import validate_image
    f = FileStorage(stream=BytesIO(b"\x89PNG\r\n\x1a\n" + b"0" * (5 * 1024 * 1024)), filename="big.png")
    assert validate_image(f) is not None


def test_save_uses_uuid_and_ignores_traversal(app):
    from app.uploads import save_image
    with app.app_context():
        f = FileStorage(stream=BytesIO(b"\x89PNG\r\n\x1a\n"), filename="../../evil.png")
        path = save_image(f)
    assert path.startswith("uploads/")
    assert ".." not in path
    assert path.endswith(".png")
```

`tests/test_publish.py`:

```python
from io import BytesIO
from werkzeug.datastructures import FileStorage

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
        "/publish", data=data, content_type="multipart/form-data",
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
        images = db.query_all("SELECT * FROM item_images WHERE item_id = ?", (item["id"],))
    assert item["status"] == "on_sale"
    assert item["price"] == 35.0
    assert len(images) == 1


def test_publish_requires_contact(client, app, seed):
    with app.app_context():
        from app import db
        db.get_db().execute("UPDATE users SET contact_wechat = NULL, contact_phone = NULL WHERE id = 1")
        db.get_db().commit()
    login(client)
    response = _post_item(client)
    assert response.status_code == 302
    assert response.headers["Location"].endswith("/profile")


def test_publish_rejects_missing_image(client, seed):
    login(client)
    response = client.post("/publish", data={
        "title": "无图商品", "category_id": "1", "price": "10",
        "description": "没有图片", "csrf_token": get_csrf(client, "/publish"),
    }, content_type="multipart/form-data")
    assert "请上传 1–5 张图片" in response.get_data(as_text=True)


def test_publish_rejects_more_than_five_images(client, seed):
    login(client)
    files = [(BytesIO(PNG), f"{i}.png") for i in range(6)]
    response = client.post("/publish", data={
        "title": "六图商品", "category_id": "1", "price": "10",
        "description": "图片太多", "csrf_token": get_csrf(client, "/publish"),
        "images": files,
    }, content_type="multipart/form-data")
    assert "请上传 1–5 张图片" in response.get_data(as_text=True)


def test_upload_error_is_translated(client, seed):
    client.get("/lang/en")
    login(client)
    response = client.post("/publish", data={
        "title": "No image", "category_id": "1", "price": "10",
        "description": "no image here", "csrf_token": get_csrf(client, "/publish"),
    }, content_type="multipart/form-data")
    assert "Upload 1–5 images" in response.get_data(as_text=True)
```

`tests/test_status.py`:

```python
from tests.helpers import get_csrf, login


def _set_status(client, item_id, status):
    return client.post(f"/item/{item_id}/status", data={
        "status": status, "csrf_token": get_csrf(client, "/"),
    }, follow_redirects=True)


def test_owner_can_mark_sold_and_relist(app, client, add_item, seed):
    item_id = add_item(title="状态商品", seller_id=1)
    login(client)
    _set_status(client, item_id, "sold")
    with app.app_context():
        from app import db
        assert db.query_one("SELECT status FROM items WHERE id = ?", (item_id,))["status"] == "sold"
    _set_status(client, item_id, "on_sale")
    with app.app_context():
        from app import db
        assert db.query_one("SELECT status FROM items WHERE id = ?", (item_id,))["status"] == "on_sale"


def test_non_owner_cannot_change_status(client, add_item, seed):
    item_id = add_item(title="别人的商品", seller_id=2)
    login(client)
    assert client.post(f"/item/{item_id}/status", data={
        "status": "sold", "csrf_token": get_csrf(client, "/items"),
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
    response = client.post(f"/item/{item_id}/delete", data={
        "csrf_token": get_csrf(client, "/"),
    }, follow_redirects=True)
    with app.app_context():
        from app import db
        row = db.query_one("SELECT is_removed, removed_by FROM items WHERE id = ?", (item_id,))
    assert row["is_removed"] == 1 and row["removed_by"] == "seller"
    assert "待删除商品" not in client.get("/items").get_data(as_text=True)


def test_non_owner_cannot_edit_or_delete(client, add_item, seed):
    item_id = add_item(title="他人商品", seller_id=2)
    login(client)
    assert client.get(f"/item/{item_id}/edit").status_code == 403
    assert client.post(f"/item/{item_id}/delete", data={
        "csrf_token": get_csrf(client, "/"),
    }).status_code == 403
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python -m pytest tests/test_publish.py tests/test_status.py tests/test_uploads.py -v`
Expected: FAIL with missing modules/routes.

- [ ] **Step 3: Implement upload helpers and item mutations**

`app/uploads.py`:

- `validate_image` checks filename extension is in `ALLOWED_IMAGE_EXTENSIONS`, reads 12 bytes, matches PNG (`\x89PNG\r\n\x1a\n`), JPEG (`\xff\xd8\xff`), or WEBP (`RIFF` + `WEBP` at bytes 8–12), and checks size via seek/tell ≤ `MAX_IMAGE_BYTES`; resets stream.
- `save_image` uses `uuid4().hex` plus the lowercased extension, writes to `UPLOAD_FOLDER`, returns `uploads/<name>`.
- `delete_image` resolves the path under `UPLOAD_FOLDER` only when it starts with `uploads/`; missing files are ignored.

`items.publish`:

- `@login_required`, GET renders `publish.html`.
- POST strips fields; validates title 2–60, description 5–2000, price finite 0–99999, optional original price finite 0–99999, condition empty or in the four values, active category exists, trade location ≤ 60, and 1–5 non-empty image files.
- If the seller has no WeChat and no phone: flash `items.error.contact_required` and `redirect("/profile")` (literal path; the profile route arrives in Task 7).
- Validate every image before saving; on any error re-render with values and error messages. Insert item, save images, insert `item_images` rows with `sort_order = index`; redirect to detail with `flash.success.published`.

`items.edit`:

- Owner or admin, and item must not be removed; otherwise 403/flash.
- Reuse the same field validation. Total images after removals/new uploads must be 1–5.
- Remove checked image rows and files; append new images with increasing sort order; update `updated_at`; redirect to detail.

`items.update_status`:

- Owner only; item must not be removed; status in the three values; update `status` and `updated_at`; redirect to `safe_next_url(next)` when provided, otherwise `url_for("items.detail", item_id=...)` (the my-listings page arrives in Task 7 and can pass `next`).

`items.delete`:

- Owner only; only when `is_removed = 0`; set `is_removed = 1`, `removed_by = 'seller'`, `removed_reason = 'seller_deleted'`, `removed_at = now`; flash and `redirect("/items")`.
- Seller cannot delete an item already removed by admin (flash error).

`items.toggle_favorite`:

- Login required. If the user already favorited the item, delete the favorite regardless of the item's current status (this is how sold/paused/invalid favorites are cleaned up). Otherwise, only allow adding when the item is `on_sale` and not removed. Redirect to safe `next` or the item detail; the favorites page posts here with `next=/my/favorites`.

`items.report`:

- Login required; not the seller; item `on_sale` or `sold`, not removed; reason 5–200; `INSERT OR IGNORE` into reports; flash success or duplicate info; redirect detail.

`publish.html` / `edit_item.html` include: image upload with `multiple`, preview area, existing image thumbnails with remove checkboxes, all required fields, condition select, category select (active only), location input with a datalist of 宿舍楼下/食堂/教学楼, and status display. Add favorite, report, edit, status, and delete forms to `item_detail.html` now, gated by the access mode from Task 5. All forms include CSRF. Add i18n keys for every label and error, including:

| Key | zh | en |
|---|---|---|
| `items.error.contact_required` | 发布前请先填写联系方式 | Add a contact method before posting |
| `items.error.images_count` | 请上传 1–5 张图片 | Upload 1–5 images |
| `items.error.image_invalid` | 图片格式不支持或超过 5 MB | Unsupported image or over 5 MB |
| `items.error.title` | 标题需为 2–60 个字符 | Title must be 2–60 characters |
| `items.error.description` | 描述需为 5–2000 个字符 | Description must be 5–2000 characters |
| `items.error.price` | 请输入 0–99999 之间的价格 | Enter a price between 0 and 99999 |
| `flash.success.published` | 发布成功 | Listing published |
| `flash.success.updated` | 修改已保存 | Changes saved |
| `flash.success.status` | 状态已更新 | Status updated |
| `flash.success.deleted` | 商品已删除 | Listing deleted |
| `items.confirm_delete` | 确定删除这件商品吗？此操作不可恢复。 | Delete this listing? This cannot be undone. |

- [ ] **Step 4: Run the tests to verify they pass**

Run: `python -m pytest tests/test_publish.py tests/test_status.py tests/test_uploads.py -v`
Expected: all pass.

- [ ] **Step 5: Checkpoint**

Run: `python -m pytest -q`
Expected: all tests pass.

---

### Task 7: My Listings, Favorites, History, Profile

**Files:**
- Create: `app/blueprints/account.py`
- Create: `templates/my_items.html`, `templates/favorites.html`, `templates/history.html`, `templates/profile.html`
- Modify: `app/queries.py`, `app/blueprints/items.py`, `templates/partials/nav.html`, `app/__init__.py`
- Test: `tests/test_account.py`

**Interfaces:**
- Consumes: `fetch_items(scope="seller")`, `login_required`, `get_current_user`.
- Produces:
  - `fetch_favorites(user_id: int) -> list[sqlite3.Row]` with item fields plus `favorite_created_at`.
  - `fetch_history(user_id: int, limit=50) -> list[sqlite3.Row]` limited to `is_removed = 0 AND status IN ('on_sale','sold')`.
  - `account.my_items`, `account.favorites`, `account.history`, `account.profile` endpoints.

- [ ] **Step 1: Write failing account tests**

`tests/test_account.py`:

```python
from app import db
from tests.helpers import get_csrf, login


def test_my_items_excludes_seller_deleted_and_shows_admin_reason(client, app, add_item, seed):
    visible = add_item(title="我的在售", seller_id=1)
    removed = add_item(title="管理员下架商品", seller_id=1, is_removed=1, removed_by="admin")
    deleted = add_item(title="我删除的商品", seller_id=1, is_removed=1, removed_by="seller")
    login(client)
    html = client.get("/my/items").get_data(as_text=True)
    assert "我的在售" in html
    assert "管理员下架商品" in html
    assert "我删除的商品" not in html


def test_favorite_only_on_sale_and_invalid_favorites_remain(client, app, add_item, seed):
    on_sale = add_item(title="可收藏", status="on_sale", seller_id=2)
    sold = add_item(title="已售收藏", status="sold", seller_id=2)
    login(client)
    assert client.post(f"/item/{sold}/favorite", data={
        "csrf_token": get_csrf(client, f"/item/{sold}"),
    }).status_code == 302
    with app.app_context():
        assert db.query_one("SELECT * FROM favorites WHERE item_id = ?", (sold,)) is None
    client.post(f"/item/{on_sale}/favorite", data={
        "csrf_token": get_csrf(client, f"/item/{on_sale}"),
    })
    with app.app_context():
        db.get_db().execute("INSERT INTO favorites (user_id, item_id, created_at) VALUES (1, ?, ?)",
                            (sold, "2026-10-01 10:00:00"))
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
        count = db.query_one("SELECT COUNT(*) AS n FROM browse_history WHERE item_id = ?", (item,))["n"]
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
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python -m pytest tests/test_account.py -v`
Expected: FAIL with 404.

- [ ] **Step 3: Implement account pages**

`account.my_items`: `@login_required`, reads `status` and `page`, calls `fetch_items(scope="seller", seller_id=current_user["id"], status=..., page=...)`, renders `my_items.html` with cards showing status, edit/status/delete controls, and an admin-removed banner with reason. Disable controls when `is_removed = 1`.

`account.favorites`: `fetch_favorites` joins items/categories and includes a computed `favorite_state` in Python: `available` (on sale, not removed), `sold`, or `invalid`. Renders cards; invalid/sold cards show labels and an unfavorite form, and only available cards link to detail.

`account.history`: `fetch_history` excludes removed and unavailable items, orders by `viewed_at DESC`, limit 50; renders cards.

`account.profile` GET/POST: shows student ID, counts of listings/favorites/sold; edits username and contacts (at least one required); optional password change requires current password and matching confirmation. Updates `users`; flash success.

Add nav links when logged in: My listings, Profile. Add i18n keys for all headings, labels, status filters, empty states, and errors.

- [ ] **Step 4: Run the tests to verify they pass**

Run: `python -m pytest tests/test_account.py -v`
Expected: all pass.

- [ ] **Step 5: Checkpoint**

Run: `python -m pytest -q`
Expected: all tests pass.

---

### Task 8: Admin Dashboard, Item Moderation, Categories, Reports

**Files:**
- Create: `app/blueprints/admin.py`
- Create: `templates/admin/dashboard.html`, `templates/admin/items.html`, `templates/admin/categories.html`, `templates/admin/reports.html`
- Create: `templates/partials/admin_nav.html`
- Modify: `app/queries.py`, `app/__init__.py`, `templates/partials/nav.html`, `static/css/style.css`
- Test: `tests/test_admin.py`

**Interfaces:**
- Consumes: `admin_required`, `fetch_items(scope="admin")`, `execute`, `query_one`.
- Produces:
  - `admin_stats() -> dict` with keys `users`, `items_total`, `on_sale`, `sold`, `unavailable`, `removed_admin`, `removed_seller`, `views`, `pending_reports`, `category_counts`.
  - Admin endpoints listed in the spec, plus `admin.remove_reported_item`.
  - `admin.bp` registered under prefix `/admin`.

- [ ] **Step 1: Write failing admin tests**

`tests/test_admin.py`:

```python
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
        row = db.query_one("SELECT is_removed, removed_by, removed_reason FROM items WHERE id = ?", (item_id,))
    assert row["removed_by"] == "admin" and row["removed_reason"] == "疑似广告"
    token = get_csrf(client, "/admin/items")
    client.post(f"/admin/items/{item_id}/restore", data={"csrf_token": token}, follow_redirects=True)
    assert client.get(f"/item/{item_id}").status_code == 200


def test_admin_cannot_restore_seller_deleted(client, app, add_item, seed):
    item_id = add_item(title="卖家删除", is_removed=1, removed_by="seller")
    login(client, "admin", "Admin@12345")
    client.post(f"/admin/items/{item_id}/restore", data={
        "csrf_token": get_csrf(client, "/admin/items"),
    }, follow_redirects=True)
    with app.app_context():
        assert db.query_one("SELECT is_removed FROM items WHERE id = ?", (item_id,))["is_removed"] == 1


def test_category_create_and_toggle(client, app, seed):
    login(client, "admin", "Admin@12345")
    token = get_csrf(client, "/admin/categories")
    client.post("/admin/categories", data={
        "slug": "music", "name_zh": "乐器", "name_en": "Instruments",
        "icon": "box", "sort_order": "8", "csrf_token": token,
    }, follow_redirects=True)
    with app.app_context():
        cat = db.query_one("SELECT * FROM categories WHERE slug = 'music'")
    assert cat["name_zh"] == "乐器"
    client.post(f"/admin/categories/{cat['id']}/toggle", data={
        "csrf_token": get_csrf(client, "/admin/categories"),
    }, follow_redirects=True)
    with app.app_context():
        assert db.query_one("SELECT is_active FROM categories WHERE id = ?", (cat["id"],))["is_active"] == 0


def test_report_flow(client, app, add_item, seed):
    item_id = add_item(title="举报商品", seller_id=2)
    login(client)
    client.post(f"/item/{item_id}/report", data={
        "reason": "疑似虚假描述",
        "csrf_token": get_csrf(client, f"/item/{item_id}"),
    }, follow_redirects=True)
    with app.app_context():
        report = db.query_one("SELECT * FROM reports WHERE item_id = ?", (item_id,))
    login(client, "admin", "Admin@12345")
    html = client.get("/admin/reports").get_data(as_text=True)
    assert "疑似虚假描述" in html
    client.post(f"/admin/reports/{report['id']}/remove-item", data={
        "csrf_token": get_csrf(client, "/admin/reports"),
    }, follow_redirects=True)
    with app.app_context():
        assert db.query_one("SELECT is_removed FROM items WHERE id = ?", (item_id,))["is_removed"] == 1
        assert db.query_one("SELECT status FROM reports WHERE id = ?", (report["id"],))["status"] == "resolved"
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python -m pytest tests/test_admin.py -v`
Expected: FAIL with 404 or 403 for all requests.

- [ ] **Step 3: Implement admin pages**

All admin routes use `@admin_required`. Register the blueprint with `url_prefix="/admin"`.

- Dashboard: `admin_stats()` counts users, non-removed items, statuses, removed by source, total views, pending reports, and category distribution (non-removed). Render stat cards and a CSS bar chart.
- Items: `fetch_items(scope="admin", q=..., category_slug=..., status=..., removed=...)` with `per_page=20`; table with title, seller, category, price, status, removal source/reason, actions.
- Remove: reason 2–200 required; only when `is_removed = 0`; set admin fields; flash.
- Restore: only `removed_by = 'admin'`; clear removal fields; keep prior status; flash.
- Categories: list all with item counts; create validates slug `^[a-z0-9-]{2,30}$` and uniqueness, names 1–30; edit same; toggle active.
- Reports: filter status; join item and reporter; actions resolve, dismiss, and remove-item (sets report resolved and item removed with reason `reported: <reason>`).

Admin templates extend `base.html` and include `partials/admin_nav.html` (dashboard, items, categories, reports). Add nav link to Admin for admin users. Add i18n keys for all admin labels and flash messages.

- [ ] **Step 4: Run the tests to verify they pass**

Run: `python -m pytest tests/test_admin.py -v`
Expected: all pass.

- [ ] **Step 5: Checkpoint**

Run: `python -m pytest -q`
Expected: all tests pass.

---

### Task 9: Seed Data, Placeholder Images, Home Content, Error Pages

**Files:**
- Create: `seed.py`
- Create: `templates/errors/400.html`, `errors/403.html`, `errors/404.html`, `errors/500.html`
- Modify: `app/__init__.py`, `app/queries.py`, `app/blueprints/main.py`, `templates/index.html`, `static/css/style.css`
- Test: `tests/test_seed.py`, `tests/test_home.py`

**Interfaces:**
- Consumes: all previous tasks.
- Produces:
  - `seed_data() -> dict` — requires app context; inserts users, categories, items, images, favorites, history, reports; returns counts.
  - `write_placeholder_images() -> None` — writes 14 SVGs (7 slugs × 2 variants) to `static/img/placeholders/`.
  - `python seed.py --reset` — deletes the SQLite file and upload files, recreates schema, writes placeholders, seeds data.
  - `build_home_data() -> dict` in `app/blueprints/main.py` with keys `latest`, `popular`, `categories`, `stats`.
  - Error handlers for 400/403/404/500.

- [ ] **Step 1: Write failing seed/home tests**

`tests/test_seed.py`:

```python
def test_seed_data_creates_demo_content(app):
    from seed import seed_data
    with app.app_context():
        counts = seed_data()
        from app import db
        assert counts["categories"] == 7
        assert counts["items"] == 28
        assert db.query_one("SELECT COUNT(*) AS n FROM users")["n"] == 4
        demos = db.query_all("SELECT status, is_removed, removed_by FROM items")
    statuses = [row["status"] for row in demos if not row["is_removed"]]
    assert statuses.count("on_sale") == 18
    assert statuses.count("sold") == 6
    assert statuses.count("unavailable") == 2
    removed = [row for row in demos if row["is_removed"]]
    assert len(removed) == 2
```

`tests/test_home.py`:

```python
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
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python -m pytest tests/test_seed.py tests/test_home.py -v`
Expected: FAIL with missing module or missing strings.

- [ ] **Step 3: Implement seed, home sections, and error pages**

`seed.py`:

- Users and categories exactly as in the fixture (passwords per spec).
- 28 items: 4 per category, distributed across the three students; 18 on_sale, 6 sold, 2 unavailable, 1 admin-removed (`removed_by='admin'`, reason `违规广告`), 1 seller-deleted (`removed_by='seller'`, reason `seller_deleted`).
- Realistic Chinese titles/descriptions per category (books: 高数教材, 考研英语真题; digital: 蓝牙耳机, 充电宝; life: 台灯, 收纳箱; sports: 羽毛球拍, 跑鞋; fashion: 卫衣, 面霜; stationery: 手账本, 中性笔套装; other: 雨伞, 小风扇).
- Prices 5–1200, conditions varied, trade locations from 宿舍楼下/一食堂/教学楼, created_at spread over the last 30 days, view_count 0–300.
- Images: two rows per item referencing `img/placeholders/<slug>-1.svg` or `-2.svg`; cover is sort_order 0.
- Favorites for user 2023001 include one on_sale, one sold, one unavailable, one admin-removed; history includes visible items plus one unavailable (query hides it); one pending report by 2023002 against an on_sale item.
- `write_placeholder_images()` writes a 800×600 SVG per category variant with a category-specific gradient, a simple icon, the English category name, and the brand name. Use these color pairs: books `#5B8DEF/#3B6FD4`, digital `#7C5CFC/#5B3FD6`, life `#38B2AC/#2C8A85`, sports `#F6A623/#D98A12`, fashion `#EC6F91/#D24B70`, stationery `#4FB286/#359468`, other `#64748B/#475569`.
- `python seed.py --reset` deletes `instance/campus_market.db` and files in `static/uploads/` before creating the app.

Home route now provides:

- `latest`: 8 visible items (`on_sale` or `sold`, not removed, not unavailable), newest first.
- `popular`: 8 `on_sale`, non-removed items, highest `view_count` first.
- `categories`: active categories with counts.
- `stats`: non-removed item count, student count, sold count.
- Render latest/popular grids with `item_card`, category tiles with icons/counts, and a three-slide carousel with translated content (static slides, JS in Task 10).

Error handlers render the custom templates with the translated messages (`errors.404.title` = 页面不存在 / Page not found, etc.). Add a 400 page for CSRF failures.

- [ ] **Step 4: Run the tests to verify they pass**

Run: `python -m pytest tests/test_seed.py tests/test_home.py -v`
Expected: all pass.

- [ ] **Step 5: Verify the real seed script**

Run: `python seed.py --reset`
Expected: prints a summary with 7 categories, 28 items, 4 users; `static/img/placeholders/` contains 14 SVG files; no traceback.

- [ ] **Step 6: Checkpoint**

Run: `python -m pytest -q`
Expected: all tests pass.

---

### Task 10: Responsive UI, Carousel, Interactive Details, Accessibility, Smoke Coverage

**Files:**
- Modify: `static/css/style.css`, `static/js/app.js`
- Modify: all templates as needed for responsive classes and accessibility
- Create: `tests/test_smoke.py`
- Test: `tests/test_smoke.py`

**Interfaces:**
- Consumes: all routes.
- Produces: no new Python interfaces.

- [ ] **Step 1: Write the failing route smoke test**

`tests/test_smoke.py`:

```python
import pytest

from tests.helpers import login


@pytest.mark.parametrize("path", ["/", "/items", "/categories", "/login", "/register"])
def test_public_pages(client, seed, path):
    assert client.get(path).status_code == 200


@pytest.mark.parametrize("path", ["/publish", "/my/items", "/my/favorites", "/my/history", "/profile"])
def test_member_pages(client, seed, path):
    login(client)
    assert client.get(path).status_code == 200


@pytest.mark.parametrize("path", ["/admin", "/admin/items", "/admin/categories", "/admin/reports"])
def test_admin_pages(client, seed, path):
    login(client, "admin", "Admin@12345")
    assert client.get(path).status_code == 200
```

- [ ] **Step 2: Run the test to verify it fails or exposes template errors**

Run: `python -m pytest tests/test_smoke.py -v`
Expected: any template/route gaps fail here.

- [ ] **Step 3: Implement responsive and interaction polish**

- CSS: complete the design tokens, typography scale, nav (desktop + mobile hamburger), hero, carousel, category tiles, item grid at 4/3/2/1 columns, status chips, forms, file preview, detail gallery, tables, admin sidebar, flash, pagination, empty states, footer, focus-visible states, and `prefers-reduced-motion`.
- JS: mobile nav toggle; carousel auto-advance every 6 seconds with pause on hover/focus, dots, and keyboard arrows; image preview/removal before upload; confirm dialogs for delete/remove/sold; flash auto-dismiss with a close button; no external libraries.
- Accessibility: alt text on all images, labels bound to inputs, `aria-live` on flash, status conveyed by text as well as color, color contrast AA, minimum 44px touch targets.
- Responsive check by hand at 375px, 768px, 1024px, 1440px: no horizontal overflow; cards single column at 375px; tables scroll horizontally.
- Invoke the `frontend-design` skill before the final visual pass and follow spec §8.3–8.4.

- [ ] **Step 4: Run the tests to verify they pass**

Run: `python -m pytest tests/test_smoke.py -v`
Expected: 14 passed.

- [ ] **Step 5: Checkpoint**

Run: `python -m pytest -q`
Expected: all tests pass.

---

### Task 11: Documentation and Final Acceptance

**Files:**
- Create: `README.md`
- Create: `docs/01-数据库设计.md`, `docs/02-功能与页面说明.md`, `docs/03-UI设计说明.md`, `docs/04-Capstone报告素材.md`, `docs/05-演示与答辩脚本.md`
- Modify: any doc references if implementation names changed

**Interfaces:**
- Consumes: the complete working app.
- Produces: course-ready documentation, screenshot checklist, and a final verification record.

- [ ] **Step 1: Write README and run instructions**

README must include: project summary, features, tech stack, directory map, prerequisites (Python 3.10+, tested on 3.13), setup steps (`python -m venv .venv`, activate, `pip install -r requirements.txt`, `python seed.py --reset`, `python run.py`), URL `http://127.0.0.1:5000`, demo accounts, test command, image storage note, troubleshooting (port in use, Windows terminal UTF-8), and a bilingual one-paragraph overview. Keep Chinese first, English second.

- [ ] **Step 2: Write database and feature documentation**

`docs/01-数据库设计.md`: Mermaid ER diagram, 7 tables, field dictionary with types/constraints, PK/FK table, relationship cardinalities, normalization explanation, indexes, status/removal semantics, sample queries.

`docs/02-功能与页面说明.md`: page inventory, route table, role/permission matrix, status state machine (including seller delete vs admin remove), core user flows, validation rules, edge cases, and a table mapping each spec requirement to its implementation.

`docs/03-UI设计说明.md`: palette with hex values, type scale, spacing, component inventory, responsive breakpoints, accessibility decisions, and a screenshot checklist (home, listing filters, detail on-sale, detail sold, publish form, my listings with statuses, favorites invalid state, admin dashboard, admin reports, English home).

- [ ] **Step 3: Write the Capstone report material**

`docs/04-Capstone报告素材.md` must include:

- Chinese abstract and keywords.
- English abstract and keywords (copy-ready, 150–200 words).
- Background and problem statement (campus group chat pain points).
- Objectives and scope (goals, non-goals).
- Literature/context comparison (campus groups, general marketplaces) without fabricated citations; mark sources to add.
- Technology selection and justification.
- System architecture and module breakdown.
- Database design summary referencing `docs/01`.
- Feature implementation and screenshots checklist.
- Innovation points: campus-only ecosystem, real-time status mechanism, bilingual UI, lightweight zero-build stack.
- Testing strategy and results table (fill from the final `pytest` run).
- Limitations and future work (no chat/payments/SSO, image CDN, notifications).
- Conclusion in Chinese and an English conclusion paragraph.
- A short mapping table from the user's original requirements to implementation.

- [ ] **Step 4: Write the demo script**

`docs/05-演示与答辩脚本.md`: 5–8 minute sequence with exact clicks and accounts:

1. Home + language switch.
2. Register a new student.
3. Publish an item with two images.
4. Browse/search/filter, open detail, log in to see contact.
5. Mark sold; show grayed card and hidden contact.
6. Pause and show removal from public list.
7. Admin login: dashboard, remove a violating item, restore it, handle the pending report, add a category.
8. Show favorites/history/profile and bilingual admin.
9. Q&A: why SQLite, how CSRF works, how status prevents invalid inquiries, what would change at scale.

- [ ] **Step 5: Run the final verification**

Run: `python -m pytest -q`
Expected: all tests pass; record the count.

Run: `python seed.py --reset`
Expected: demo data created with no traceback.

Run: `python -c "from app import create_app; c=create_app().test_client(); print(c.get('/').status_code, c.get('/items').status_code)"`
Expected: `200 200`.

Manually verify the spec §14 acceptance list, including 375px layout and English switch, and note any deviations in the final message.

- [ ] **Step 6: Checkpoint**

Run: `python -m pytest -q` once more.
Expected: all tests pass.

---

## Appendix A: Demo Accounts

| Role | Student ID | Password | Name |
|---|---|---|---|
| Admin | `admin` | `Admin@12345` | 平台管理员 |
| Student | `2023001` | `Demo@12345` | 林小雨 |
| Student | `2023002` | `Demo@12345` | 陈子昂 |
| Student | `2023003` | `Demo@12345` | 苏晴 |

## Appendix B: Seed Item Distribution

| Category | Items | On sale | Sold | Paused | Removed |
|---|---|---|---|---|---|
| 教材书籍 | 4 | 3 | 1 | 0 | 0 |
| 电子数码 | 4 | 2 | 1 | 1 | 0 |
| 生活用品 | 4 | 3 | 1 | 0 | 0 |
| 运动健身 | 4 | 3 | 1 | 0 | 0 |
| 美妆衣物 | 4 | 3 | 1 | 0 | 0 |
| 文具文创 | 4 | 2 | 1 | 1 | 0 |
| 其他闲置 | 4 | 2 | 0 | 0 | 2 |
| **Total** | **28** | **18** | **6** | **2** | **2** |

The two removed items are one admin-removed (visible in admin moderation and seller's "my listings" with reason) and one seller-deleted (visible only to admin). The paused items are excluded from public lists but reachable by direct URL with a notice.

## Appendix C: i18n Key Naming

Use dot-separated groups: `nav.*`, `auth.*`, `item.*`, `items.*`, `home.*`, `account.*`, `admin.*`, `status.*`, `condition.*`, `errors.*`, `flash.*`. Never hardcode Chinese or English in templates except the brand wordmark and user-generated content. `t()` returns the key when a translation is missing so omissions are visible during review.
