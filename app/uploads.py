from pathlib import Path
from uuid import uuid4

from flask import current_app, has_app_context

DEFAULT_EXTENSIONS = {"jpg", "jpeg", "png", "webp"}
DEFAULT_MAX_BYTES = 5 * 1024 * 1024


def _limits():
    if has_app_context():
        return (
            current_app.config["ALLOWED_IMAGE_EXTENSIONS"],
            current_app.config["MAX_IMAGE_BYTES"],
        )
    return DEFAULT_EXTENSIONS, DEFAULT_MAX_BYTES


def _extension(filename: str) -> str:
    if not filename or "." not in filename:
        return ""
    return filename.rsplit(".", 1)[1].lower()


def validate_image(file_storage) -> str | None:
    allowed, max_bytes = _limits()
    if _extension(file_storage.filename) not in allowed:
        return "items.error.image_invalid"

    stream = file_storage.stream
    header = stream.read(12)
    stream.seek(0)
    stream.seek(0, 2)
    size = stream.tell()
    stream.seek(0)

    if size <= 0 or size > max_bytes:
        return "items.error.image_invalid"

    is_png = header.startswith(b"\x89PNG\r\n\x1a\n")
    is_jpeg = header.startswith(b"\xff\xd8\xff")
    is_webp = header[:4] == b"RIFF" and header[8:12] == b"WEBP"
    if not (is_png or is_jpeg or is_webp):
        return "items.error.image_invalid"
    return None


def save_image(file_storage) -> str:
    ext = _extension(file_storage.filename)
    name = f"{uuid4().hex}.{ext}"
    folder = Path(current_app.config["UPLOAD_FOLDER"])
    folder.mkdir(parents=True, exist_ok=True)
    file_storage.save(folder / name)
    return f"uploads/{name}"


def delete_image(static_path: str) -> None:
    if not static_path or not static_path.startswith("uploads/"):
        return
    name = static_path[len("uploads/"):]
    if "/" in name or "\\" in name or not name:
        return
    target = Path(current_app.config["UPLOAD_FOLDER"]) / name
    try:
        target.unlink()
    except FileNotFoundError:
        pass
