import os
import re

from flask import current_app

EMAIL_RE = re.compile(r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$")

ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "gif", "webp"}

ADMIN_USERNAME = "admin"
ADMIN_PASSWORD_HASH = (
    "scrypt:32768:8:1$lR2mNj8G0tFZo0ny$c8b99ecd840be29c981b4d3f881ea36d11fcd41b3"
    "a9396b366f1414ac52bf50213cdea9eaa6a4a48715588a2aa7bf21096c5c356e21d89e6b"
    "5d690da1fc209b6"
)


def get_image_url(image_path: str | None) -> str | None:
    if not image_path:
        return None
    bucket = current_app.config.get("STORAGE_BUCKET", "listing-images")
    supabase = current_app.config.get("supabase")
    if supabase is None:
        return None
    try:
        public_url = supabase.storage.from_(bucket).get_public_url(image_path)
        return public_url
    except Exception as exc:
        current_app.logger.error("Failed to get public URL for %s: %s", image_path, exc)
        return None


def allowed_file(filename: str) -> bool:
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS
