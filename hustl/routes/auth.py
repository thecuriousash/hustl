from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from werkzeug.security import check_password_hash, generate_password_hash

from ..db import get_db_connection, close_db_connection
from ..helpers import EMAIL_RE, ADMIN_USERNAME, ADMIN_PASSWORD_HASH

bp = Blueprint("auth", __name__, url_prefix="")


@bp.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")

        if not username or not password:
            flash("Username and password are required.", "error")
            return render_template("auth.html", is_login=True)

        if username == ADMIN_USERNAME:
            if check_password_hash(ADMIN_PASSWORD_HASH, password):
                session.permanent = True
                session["user_id"] = 0
                session["username"] = "admin"
                session["is_seller"] = False
                session["is_admin"] = True
                return redirect(url_for("admin.dashboard"))
            flash("Invalid credentials.", "error")
            return render_template("auth.html", is_login=True)

        conn = get_db_connection()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT id, username, password_hash, is_seller FROM users WHERE username = %s",
                    (username,),
                )
                user = cur.fetchone()
        finally:
            close_db_connection(conn)

        if user and check_password_hash(user[2], password):
            session.permanent = True
            session["user_id"] = user[0]
            session["username"] = user[1]
            session["is_seller"] = user[3]
            return redirect(url_for("market.home"))
        flash("Invalid credentials.", "error")
        return render_template("auth.html", is_login=True)

    return render_template("auth.html", is_login=True)


@bp.route("/signup", methods=["GET", "POST"])
def signup():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        email = request.form.get("email", "").strip()
        password = request.form.get("password", "")

        if not username or not email or not password:
            flash("All fields are required.", "error")
            return render_template("auth.html", is_login=False)

        if not EMAIL_RE.match(email):
            flash("Invalid email address.", "error")
            return render_template("auth.html", is_login=False)

        if len(password) < 8:
            flash("Password must be at least 8 characters.", "error")
            return render_template("auth.html", is_login=False)

        conn = get_db_connection()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT id FROM users WHERE username = %s OR email = %s",
                    (username, email),
                )
                existing = cur.fetchone()
                if existing:
                    flash("Username or email already taken.", "error")
                    return render_template("auth.html", is_login=False)

                pw_hash = generate_password_hash(password)
                cur.execute(
                    "INSERT INTO users (username, email, password_hash) VALUES (%s, %s, %s) RETURNING id",
                    (username, email, pw_hash),
                )
                user_id = cur.fetchone()[0]
                conn.commit()
        finally:
            close_db_connection(conn)

        session.permanent = True
        session["user_id"] = user_id
        session["username"] = username
        session["is_seller"] = False
        return redirect(url_for("market.home"))

    return render_template("auth.html", is_login=False)


@bp.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("market.home"))
