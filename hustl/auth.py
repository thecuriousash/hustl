from functools import wraps

from flask import abort, session


def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if "user_id" not in session:
            abort(403)
        return f(*args, **kwargs)

    return decorated_function


def get_current_user() -> dict | None:
    user_id = session.get("user_id")
    display_name = session.get("display_name")
    if user_id is None:
        return None
    return {
        "id": user_id,
        "display_name": display_name,
        "is_seller": session.get("is_seller", False),
        "is_verified": session.get("is_verified", 0),
        "user_type": "seller" if session.get("is_seller") else "buyer",
    }
