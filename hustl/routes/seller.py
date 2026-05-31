import uuid

from flask import (
    Blueprint,
    render_template,
    request,
    redirect,
    url_for,
    flash,
    session,
    current_app,
)

from ..auth import login_required
from ..db import get_db_connection, close_db_connection
from ..helpers import get_image_url, allowed_file

bp = Blueprint("seller", __name__, url_prefix="")


@bp.route("/seller-onboarding", methods=["GET", "POST"])
@login_required
def seller_onboarding():
    if request.method == "POST":
        conn = get_db_connection()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE users SET is_seller = TRUE WHERE id = %s",
                    (session["user_id"],),
                )
                conn.commit()
        finally:
            close_db_connection(conn)
        session["is_seller"] = True
        return redirect(url_for("seller.seller_dash"))
    return render_template("seller_onboarding.html")


@bp.route("/seller-dash", methods=["GET", "POST"])
@login_required
def seller_dash():
    if not session.get("is_seller"):
        return redirect(url_for("seller.seller_onboarding"))

    if request.method == "POST":
        title = request.form.get("title", "").strip()
        description = request.form.get("description", "").strip()
        price = request.form.get("price", type=float)
        category = request.form.get("category", "").strip()
        condition = request.form.get("condition", "").strip()
        file = request.files.get("image")

        if not title or not price:
            flash("Title and price are required.", "error")
            return redirect(url_for("seller.seller_dash"))

        image_url = None
        if file and allowed_file(file.filename):
            ext = file.filename.rsplit(".", 1)[1].lower()
            unique_name = f"{uuid.uuid4().hex}.{ext}"
            supabase = current_app.config.get("supabase")
            bucket = current_app.config.get("STORAGE_BUCKET", "listing-images")
            if supabase:
                try:
                    supabase.storage.from_(bucket).upload(
                        file=file.read(),
                        path=unique_name,
                        file_options={"content-type": file.content_type},
                    )
                    image_url = unique_name
                except Exception as exc:
                    current_app.logger.error(
                        "Failed to upload image: %s", exc
                    )
                    flash("Image upload failed. Try again.", "error")

        conn = get_db_connection()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """INSERT INTO market_items (title, description, price, category, condition, image_url, seller_id)
                       VALUES (%s, %s, %s, %s, %s, %s, %s)""",
                    (title, description, price, category, condition, image_url, session["user_id"]),
                )
                conn.commit()
        finally:
            close_db_connection(conn)
        flash("Item listed successfully!")
        return redirect(url_for("seller.seller_dash"))

    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """SELECT id, title, price, image_url, status, created_at
                   FROM market_items
                   WHERE seller_id = %s
                   ORDER BY created_at DESC""",
                (session["user_id"],),
            )
            rows = cur.fetchall()
    finally:
        close_db_connection(conn)

    items = [
        {
            "id": r[0],
            "title": r[1],
            "price": float(r[2]),
            "image": r[3],
            "brand": None,
            "is_sold": 1 if r[4] == "sold" else 0,
            "status": r[4],
            "created_at": r[5],
        }
        for r in rows
    ]
    return render_template("seller_dash.html", items=items)


@bp.route("/seller/<int:seller_id>")
def seller_profile(seller_id: int):
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT username, created_at FROM users WHERE id = %s", (seller_id,)
            )
            seller = cur.fetchone()
            if not seller:
                return (
                    render_template("error.html", code=404, message="Seller not found."),
                    404,
                )
            cur.execute(
                """SELECT id, title, price, image_url
                   FROM market_items
                   WHERE seller_id = %s AND status = 'active'
                   ORDER BY created_at DESC""",
                (seller_id,),
            )
            rows = cur.fetchall()
    finally:
        close_db_connection(conn)

    name = seller[0]
    join_date = seller[1].strftime("%b %Y") if seller[1] else "Recently"

    items = [
        {
            "id": r[0],
            "title": r[1],
            "price": float(r[2]),
            "image": r[3],
        }
        for r in rows
    ]
    return render_template(
        "seller_profile.html",
        name=name,
        join_date=join_date,
        whatsapp=None,
        items=items,
    )
