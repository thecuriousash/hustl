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
    from flask import session as s

    user_id = s.get("user_id")
    username = s.get("username")
    if user_id is None:
        return None
    return {"id": user_id, "username": username, "is_seller": s.get("is_seller", False)}
