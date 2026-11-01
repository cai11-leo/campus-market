from pathlib import Path

from flask import Flask, g, render_template

from config import Config

from . import db, security
from .blueprints import account, admin, auth, items, main
from .i18n import LANGUAGES, get_locale, t
from .utils import (
    category_name,
    condition_label,
    dt,
    money,
    status_label,
    url_with_page,
)


BASE_DIR = Path(__file__).resolve().parent.parent


def create_app(test_config: dict | None = None) -> Flask:
    app = Flask(
        __name__,
        instance_relative_config=True,
        template_folder=str(BASE_DIR / "templates"),
        static_folder=str(BASE_DIR / "static"),
    )
    app.config.from_object(Config)
    if test_config:
        app.config.update(test_config)

    Path(app.instance_path).mkdir(parents=True, exist_ok=True)
    Path(app.config["UPLOAD_FOLDER"]).mkdir(parents=True, exist_ok=True)

    db.init_app(app)
    security.init_app(app)
    with app.app_context():
        db.init_db()

    if (
        not app.config.get("TESTING")
        and app.config["SECRET_KEY"] == "dev-only-change-me"
    ):
        app.logger.warning(
            "Using the development SECRET_KEY. Set SECRET_KEY before "
            "exposing this app outside localhost."
        )

    app.register_blueprint(main.bp)
    app.register_blueprint(auth.bp)
    app.register_blueprint(items.bp)
    app.register_blueprint(account.bp)
    app.register_blueprint(admin.bp)

    app.jinja_env.globals.update(
        t=t,
        category_name=category_name,
        status_label=status_label,
        condition_label=condition_label,
        money=money,
        dt=dt,
        url_with_page=url_with_page,
    )

    @app.context_processor
    def inject_globals():
        return {
            "locale": get_locale(),
            "languages": LANGUAGES,
            "current_user": getattr(g, "user", None),
            "csrf_token": security.csrf_token,
        }

    @app.errorhandler(400)
    def bad_request(error):
        return render_template("errors/400.html"), 400

    @app.errorhandler(403)
    def forbidden(error):
        return render_template("errors/403.html"), 403

    @app.errorhandler(404)
    def not_found(error):
        return render_template("errors/404.html"), 404

    @app.errorhandler(500)
    def server_error(error):
        return render_template("errors/500.html"), 500

    return app
