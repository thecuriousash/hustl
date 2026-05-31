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
        legal_name = request.form.get("legal_name", "").strip()
        display_name = request.form.get("display_name", "").strip()
        reg_number = request.form.get("reg_number", "").strip()
        whatsapp = request.form.get("whatsapp", "").strip()
        id_proof_link = request.form.get("id_proof_link", "").strip()
        social_link = request.form.get("social_link", "").strip()

        conn = get_db_connection()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """UPDATE public.users SET
                       user_type = 'seller', legal_name = %s, display_name = %s,
                       reg_number = %s, whatsapp = %s, id_proof_link = %s, social_link = %s
                       WHERE id = %s""",
                    (legal_name, display_name or None, reg_number, whatsapp, id_proof_link, social_link or None, session["user_id"]),
                )
                conn.commit()
        finally:
            close_db_connection(conn)
        session["is_seller"] = True
        if display_name:
            session["display_name"] = display_name
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
        whatsapp = request.form.get("whatsapp", "").strip()
        brand = request.form.get("brand", "").strip()
        file = request.files.get("image")

        if not title or not price:
            flash("Title and price are required.", "error")
            return redirect(url_for("seller.seller_dash"))

        image_path = None
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
                    image_path = unique_name
                except Exception as exc:
                    current_app.logger.error(
                        "Failed to upload image: %s", exc
                    )
                    flash("Image upload failed. Try again.", "error")

        conn = get_db_connection()
        try:
            with conn.cursor() as cur:
                is_approved = 1 if session.get("is_verified") else 0
                cur.execute(
                    """INSERT INTO market_items (title, description, price, category, condition, brand, whatsapp, image, user_id, is_approved)
                       VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
                    (title, description, str(price), category, condition, brand or None, whatsapp or None, image_path, session["user_id"], is_approved),
                )
                conn.commit()
        finally:
            close_db_connection(conn)
        flash("Item listed successfully!")
        return redirect(url_for("seller.seller_dash"))

    conn = get_db_connection()
    rows = []
    try:
        with conn.cursor() as cur:
            cur.execute(
                """SELECT id, title, price, image, is_sold, created_at, brand, whatsapp, is_approved
                   FROM market_items
                   WHERE user_id = %s
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
            "price": float(r[2]) if r[2] else 0,
            "image": r[3],
            "is_sold": r[4],
            "created_at": r[5],
            "brand": r[6],
            "is_approved": r[8],
        }
        for r in rows
    ]
    return render_template("seller_dash.html", items=items)


@bp.route("/seller/<int:seller_id>")
def seller_profile(seller_id: int):
    conn = get_db_connection()
    seller = None
    rows = []
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT display_name, email, whatsapp FROM public.users WHERE id = %s",
                (seller_id,),
            )
            seller = cur.fetchone()
            if not seller:
                return (
                    render_template("error.html", code=404, message="Seller not found."),
                    404,
                )
            cur.execute(
                """SELECT id, title, price, image
                   FROM market_items
                   WHERE user_id = %s AND is_sold = 0
                   ORDER BY created_at DESC""",
                (seller_id,),
            )
            rows = cur.fetchall()
    finally:
        close_db_connection(conn)

    name = seller[0] or seller[1].split("@")[0]

    items = [
        {
            "id": r[0],
            "title": r[1],
            "price": float(r[2]) if r[2] else 0,
            "image": r[3],
        }
        for r in rows
    ]
    return render_template(
        "seller_profile.html",
        name=name,
        join_date="Campus Student",
        whatsapp=seller[2],
        items=items,
    )
