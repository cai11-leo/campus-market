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
    f = FileStorage(
        stream=BytesIO(b"\x89PNG\r\n\x1a\n" + b"0" * (5 * 1024 * 1024)),
        filename="big.png",
    )
    assert validate_image(f) is not None


def test_save_uses_uuid_and_ignores_traversal(app):
    from app.uploads import save_image
    with app.app_context():
        f = FileStorage(
            stream=BytesIO(b"\x89PNG\r\n\x1a\n"), filename="../../evil.png"
        )
        path = save_image(f)
    assert path.startswith("uploads/")
    assert ".." not in path
    assert path.endswith(".png")
