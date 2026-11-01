import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-only-change-me")
    DEBUG = os.environ.get("FLASK_DEBUG", "0") == "1"
    DATABASE = os.environ.get(
        "DATABASE", str(BASE_DIR / "instance" / "campus_market.db")
    )
    UPLOAD_FOLDER = str(BASE_DIR / "static" / "uploads")
    MAX_CONTENT_LENGTH = 30 * 1024 * 1024
    ITEMS_PER_PAGE = 12
    ADMIN_ITEMS_PER_PAGE = 20
    MAX_IMAGES = 5
    MAX_IMAGE_BYTES = 5 * 1024 * 1024
    ALLOWED_IMAGE_EXTENSIONS = {"jpg", "jpeg", "png", "webp"}
