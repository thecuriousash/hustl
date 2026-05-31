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

from ..auth import login_required, get_current_user
from ..db import get_db_connection, close_db_connection
from ..helpers import get_image_url, allowed_file

bp = Blueprint("market", __name__, url_prefix="")


def _user_context():
    return get_current_user()


@bp.route("/")
def home():
    conn = get_db_connection()
    rows = []
    try:
        with conn.cursor() as cur:
            cur.execute(
                """SELECT m.id, m.title, m.price, m.image, m.brand, m.is_sold, COALESCE(u.display_name, u.email)
                   FROM market_items m
                   LEFT JOIN public.users u ON m.user_id = u.id
                   WHERE m.is_sold = 0
                   ORDER BY m.created_at DESC LIMIT 6"""
            )
            rows = cur.fetchall()
    finally:
        close_db_connection(conn)

    items = []
    for r in rows:
        items.append({
            "id": r[0],
            "title": r[1],
            "price": float(r[2]) if r[2] else 0,
            "image": r[3],
            "brand": r[4],
            "is_sold": r[5],
            "seller_display": r[6] or "Campus Student",
        })

    return render_template(
        "market.html",
        items=items,
        user=_user_context(),
        category="",
        page=1,
        total_pages=1,
    )


@bp.route("/market")
def market():
    page = request.args.get("page", 1, type=int)
    per_page = 12
    category = request.args.get("category", "")
    offset = (page - 1) * per_page

    conn = get_db_connection()
    total_count = 0
    rows = []
    try:
        with conn.cursor() as cur:
            if category:
                cur.execute(
                    "SELECT COUNT(*) FROM market_items WHERE is_sold = 0 AND category = %s",
                    (category,),
                )
                total_count = cur.fetchone()[0]
                cur.execute(
                    """SELECT m.id, m.title, m.price, m.image, m.brand, m.is_sold,
                              COALESCE(u.display_name, u.email)
                       FROM market_items m
                       LEFT JOIN public.users u ON m.user_id = u.id
                       WHERE m.is_sold = 0 AND m.category = %s
                       ORDER BY m.created_at DESC LIMIT %s OFFSET %s""",
                    (category, per_page, offset),
                )
            else:
                cur.execute(
                    "SELECT COUNT(*) FROM market_items WHERE is_sold = 0"
                )
                total_count = cur.fetchone()[0]
                cur.execute(
                    """SELECT m.id, m.title, m.price, m.image, m.brand, m.is_sold,
                              COALESCE(u.display_name, u.email)
                       FROM market_items m
                       LEFT JOIN public.users u ON m.user_id = u.id
                       WHERE m.is_sold = 0
                       ORDER BY m.created_at DESC LIMIT %s OFFSET %s""",
                    (per_page, offset),
                )
            rows = cur.fetchall()
    finally:
        close_db_connection(conn)

    items = []
    for r in rows:
        items.append({
            "id": r[0],
            "title": r[1],
            "price": float(r[2]) if r[2] else 0,
            "image": r[3],
            "brand": r[4],
            "is_sold": r[5],
            "seller_display": r[6] or "Campus Student",
        })

    total_pages = max(1, (total_count + per_page - 1) // per_page)
    return render_template(
        "market.html",
        items=items,
        page=page,
        total_pages=total_pages,
        category=category,
        user=_user_context(),
    )


@bp.route("/listing/<int:listing_id>")
def listing_detail(listing_id: int):
    conn = get_db_connection()
    row = None
    other_products = []
    try:
        with conn.cursor() as cur:
            cur.execute(
                """SELECT m.id, m.title, m.description, m.price, m.image,
                          m.category, m.condition, m.is_sold, m.user_id, m.created_at,
                          m.brand, m.whatsapp,
                          COALESCE(u.display_name, u.email), u.is_verified
                   FROM market_items m
                   LEFT JOIN public.users u ON m.user_id = u.id
                   WHERE m.id = %s""",
                (listing_id,),
            )
            row = cur.fetchone()

            if row:
                cur.execute(
                    """SELECT id, title, price, image
                       FROM market_items
                       WHERE user_id = %s AND id != %s AND is_sold = 0
                       ORDER BY created_at DESC LIMIT 4""",
                    (row[8], listing_id),
                )
                other_products = cur.fetchall()
    finally:
        close_db_connection(conn)

    if not row:
        return render_template("error.html", code=404, message="Listing not found."), 404

    item = {
        "id": row[0],
        "title": row[1],
        "description": row[2],
        "price": float(row[3]) if row[3] else 0,
        "image": row[4],
        "category": row[5],
        "condition": row[6],
        "is_sold": row[7],
        "seller_id": row[8],
        "created_at": row[9],
        "brand": row[10],
        "whatsapp": row[11],
        "seller_display": row[12] or "Campus Student",
        "is_verified": row[13] or 0,
    }

    others = []
    for o in other_products:
        others.append({
            "id": o[0],
            "title": o[1],
            "price": float(o[2]) if o[2] else 0,
            "image": o[3],
            "seller_display": item["seller_display"],
        })

    return render_template("listing_detail.html", item=item, other_products=others)


@bp.route("/search")
def search():
    query = request.args.get("q", "").strip()
    page = request.args.get("page", 1, type=int)
    per_page = 12
    offset = (page - 1) * per_page

    conn = get_db_connection()
    total_count = 0
    rows = []
    try:
        with conn.cursor() as cur:
            if query:
                like_q = f"%{query}%"
                cur.execute(
                    """SELECT COUNT(*) FROM market_items
                       WHERE is_sold = 0 AND (title ILIKE %s OR description ILIKE %s)""",
                    (like_q, like_q),
                )
                total_count = cur.fetchone()[0]
                cur.execute(
                    """SELECT m.id, m.title, m.price, m.image, m.brand, m.is_sold,
                              COALESCE(u.display_name, u.email)
                       FROM market_items m
                       LEFT JOIN public.users u ON m.user_id = u.id
                       WHERE m.is_sold = 0 AND (m.title ILIKE %s OR m.description ILIKE %s)
                       ORDER BY m.created_at DESC LIMIT %s OFFSET %s""",
                    (like_q, like_q, per_page, offset),
                )
            else:
                cur.execute(
                    "SELECT COUNT(*) FROM market_items WHERE is_sold = 0"
                )
                total_count = cur.fetchone()[0]
                cur.execute(
                    """SELECT m.id, m.title, m.price, m.image, m.brand, m.is_sold,
                              COALESCE(u.display_name, u.email)
                       FROM market_items m
                       LEFT JOIN public.users u ON m.user_id = u.id
                       WHERE m.is_sold = 0
                       ORDER BY m.created_at DESC LIMIT %s OFFSET %s""",
                    (per_page, offset),
                )
            rows = cur.fetchall()
    finally:
        close_db_connection(conn)

    items = []
    for r in rows:
        items.append({
            "id": r[0],
            "title": r[1],
            "price": float(r[2]) if r[2] else 0,
            "image": r[3],
            "brand": r[4],
            "is_sold": r[5],
            "seller_display": r[6] or "Campus Student",
        })

    total_pages = max(1, (total_count + per_page - 1) // per_page)
    return render_template(
        "market.html",
        items=items,
        page=page,
        total_pages=total_pages,
        category="",
        query=query,
        user=_user_context(),
    )


@bp.route("/market/sold/<int:item_id>", methods=["POST"])
@login_required
def mark_sold(item_id: int):
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT user_id FROM market_items WHERE id = %s", (item_id,)
            )
            item = cur.fetchone()
            if not item:
                flash("Item not found.", "error")
                return redirect(url_for("seller.seller_dash"))
            if item[0] != session["user_id"]:
                flash("You can only mark your own items as sold.", "error")
                return redirect(url_for("market.market"))
            cur.execute(
                "UPDATE market_items SET is_sold = 1 WHERE id = %s", (item_id,)
            )
            conn.commit()
    finally:
        close_db_connection(conn)
    flash("Item marked as sold!")
    return redirect(url_for("seller.seller_dash"))


@bp.route("/market/delete/<int:item_id>", methods=["POST"])
@login_required
def delete_listing(item_id: int):
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT user_id, image FROM market_items WHERE id = %s",
                (item_id,),
            )
            item = cur.fetchone()
            if not item:
                flash("Item not found.", "error")
                return redirect(url_for("market.market"))
            if item[0] != session["user_id"] and not session.get("is_admin"):
                flash("You can only delete your own listings.", "error")
                return redirect(url_for("market.market"))

            image_path = item[1]
            supabase = current_app.config.get("supabase")
            bucket = current_app.config.get("STORAGE_BUCKET", "listing-images")
            if supabase and image_path:
                try:
                    supabase.storage.from_(bucket).remove([image_path])
                except Exception as exc:
                    current_app.logger.error(
                        "Failed to delete image %s: %s", image_path, exc
                    )

            cur.execute("DELETE FROM market_items WHERE id = %s", (item_id,))
            conn.commit()
    finally:
        close_db_connection(conn)
    flash("Listing deleted.")
    return redirect(url_for("market.market"))
