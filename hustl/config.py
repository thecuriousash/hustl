import os
from datetime import timedelta

from dotenv import load_dotenv

load_dotenv()


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-key-change-in-production")
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    SUPABASE_URL = os.environ.get("SUPABASE_URL")
    SUPABASE_KEY = os.environ.get("SUPABASE_KEY")
    DATABASE_URL = os.environ.get("DATABASE_URL")
    STORAGE_BUCKET = os.environ.get("STORAGE_BUCKET", "listing-images")

    SESSION_LIFETIME_HOURS = int(os.environ.get("SESSION_LIFETIME_HOURS", "4"))
    WTF_CSRF_TIME_LIMIT = None
    MAX_CONTENT_LENGTH = 10 * 1024 * 1024
    UPLOAD_FOLDER = "/tmp/hustl_uploads"

    # Flask-Limiter
    RATELIMIT_STORAGE_URI = "memory://"
    RATELIMIT_DEFAULT = "200 per day;50 per hour"

    def set_flask_config(app):
        app.secret_key = Config.SECRET_KEY
        app.permanent_session_lifetime = timedelta(hours=Config.SESSION_LIFETIME_HOURS)
        app.config["MAX_CONTENT_LENGTH"] = Config.MAX_CONTENT_LENGTH
        app.config["SESSION_COOKIE_SECURE"] = True
        app.config["SESSION_COOKIE_HTTPONLY"] = True
        app.config["SESSION_COOKIE_SAMESITE"] = "Lax"


def validate_env() -> None:
    required = ["SECRET_KEY", "SUPABASE_URL", "SUPABASE_KEY", "DATABASE_URL"]
    missing = [k for k in required if not os.environ.get(k)]
    if missing:
        raise RuntimeError(f"Missing required env vars: {', '.join(missing)}")

    if Config.SECRET_KEY == "generate-a-random-string-here":
        raise RuntimeError(
            "SECRET_KEY is still the placeholder 'generate-a-random-string-here'."
            " Generate a random secret and set it in .env or Render dashboard."
        )
