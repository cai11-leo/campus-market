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


def test_debug_defaults_off(monkeypatch):
    monkeypatch.delenv("FLASK_DEBUG", raising=False)
    import importlib
    import config
    module = importlib.reload(config)
    assert module.Config.DEBUG is False
