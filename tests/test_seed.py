def test_seed_data_creates_demo_content(app):
    from seed import seed_data

    with app.app_context():
        counts = seed_data()
        from app import db
        assert counts["categories"] == 7
        assert counts["items"] == 28
        assert db.query_one("SELECT COUNT(*) AS n FROM users")["n"] == 4
        rows = db.query_all(
            "SELECT status, is_removed, removed_by FROM items"
        )

    statuses = [row["status"] for row in rows if not row["is_removed"]]
    assert statuses.count("on_sale") == 18
    assert statuses.count("sold") == 6
    assert statuses.count("unavailable") == 2
    removed = [row for row in rows if row["is_removed"]]
    assert len(removed) == 2
