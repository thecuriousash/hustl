import os

from flask import Flask, render_template
from flask_wtf.csrf import CSRFProtect
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

from .config import Config
from .db import init_supabase, init_db

csrf = CSRFProtect()
limiter = Limiter(key_func=get_remote_address, storage_uri="memory://")


def create_app() -> Flask:
    root = os.path.dirname(os.path.dirname(__file__))
    app = Flask(
        __name__,
        template_folder=os.path.join(root, "templates"),
        static_folder=os.path.join(root, "static"),
    )
    app.config.from_object(Config)

    Config.set_flask_config(app)

    csrf.init_app(app)
    limiter.init_app(app)

    from .helpers import get_image_url

    init_supabase(app)

    _register_blueprints(app)
    _register_handlers(app)

    # Lazy DB init — won't crash if DB is unreachable
    with app.app_context():
        try:
            init_db()
        except Exception as e:
            app.logger.error(
                "Failed to initialize database at startup: %s. "
                "The app will continue but database operations may fail.",
                e,
            )

    return app


def _register_blueprints(app: Flask) -> None:
    from .routes.auth import bp as auth_bp
    from .routes.market import bp as market_bp
    from .routes.seller import bp as seller_bp
    from .routes.lost import bp as lost_bp
    from .routes.admin import bp as admin_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(market_bp)
    app.register_blueprint(seller_bp)
    app.register_blueprint(lost_bp)
    app.register_blueprint(admin_bp)


def _register_handlers(app: Flask) -> None:
    from .helpers import get_image_url

    @app.context_processor
    def utility_processor() -> dict:
        return dict(get_image_url=get_image_url)

    @app.after_request
    def add_security_headers(resp):
        resp.headers["X-Content-Type-Options"] = "nosniff"
        resp.headers["X-Frame-Options"] = "DENY"
        resp.headers["X-XSS-Protection"] = "1; mode=block"
        resp.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        return resp

    @app.errorhandler(404)
    def not_found(e):
        return render_template("error.html", code=404, message="Page not found."), 404

    @app.errorhandler(403)
    def forbidden(e):
        return (
            render_template("error.html", code=403, message="Permission denied."),
            403,
        )

    @app.errorhandler(500)
    def server_error(e):
        app.logger.error("Internal server error: %s", e)
        return (
            render_template("error.html", code=500, message="Something went wrong."),
            500,
        )

    @app.route("/health")
    def health():
        return {"status": "ok"}, 200
