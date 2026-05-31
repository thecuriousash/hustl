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

bp = Blueprint("market", __name__, url_prefix="")


def _user_context():
    return get_current_user()


def _item_row_to_dict(row) -> dict:
    return {
        "id": row[0],
        "title": row[1],
        "price": float(row[2]),
        "image": row[3],
        "category": row[4] if len(row) > 4 else None,
        "condition": row[5] if len(row) > 5 else None,
        "created_at": row[6] if len(row) > 6 else None,
    }


def _enrich_item(item: dict, seller_name: str = None) -> dict:
    item["brand"] = None
    item["is_verified"] = 0
    item["is_sold"] = 1 if item.get("status") == "sold" else 0
    item["seller_display"] = seller_name or "Campus Student"
    return item


@bp.route("/")
def home():
    conn = get_db_connection()
    rows = []
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id, title, price, image_url FROM market_items WHERE status = 'active' ORDER BY created_at DESC LIMIT 6"
            )
            rows = cur.fetchall()
    finally:
        close_db_connection(conn)

    items = [_enrich_item(_item_row_to_dict(r)) for r in rows]
    user = _user_context()
    return render_template(
        "market.html",
        items=items,
        user=user,
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
    try:
        with conn.cursor() as cur:
            if category:
                cur.execute(
                    "SELECT COUNT(*) FROM market_items WHERE status = 'active' AND category = %s",
                    (category,),
                )
                total_count = cur.fetchone()[0]
                cur.execute(
                    """SELECT m.id, m.title, m.price, m.image_url, m.category, m.condition, m.created_at, u.username
                       FROM market_items m
                       JOIN users u ON m.seller_id = u.id
                       WHERE m.status = 'active' AND m.category = %s
                       ORDER BY m.created_at DESC LIMIT %s OFFSET %s""",
                    (category, per_page, offset),
                )
            else:
                cur.execute(
                    "SELECT COUNT(*) FROM market_items WHERE status = 'active'"
                )
                total_count = cur.fetchone()[0]
                cur.execute(
                    """SELECT m.id, m.title, m.price, m.image_url, m.category, m.condition, m.created_at, u.username
                       FROM market_items m
                       JOIN users u ON m.seller_id = u.id
                       WHERE m.status = 'active'
                       ORDER BY m.created_at DESC LIMIT %s OFFSET %s""",
                    (per_page, offset),
                )
            rows = cur.fetchall()
    finally:
        close_db_connection(conn)

    items = []
    for r in rows:
        d = _item_row_to_dict(r[:7])
        d = _enrich_item(d, seller_name=r[7] if len(r) > 7 else None)
        items.append(d)

    total_pages = max(1, (total_count + per_page - 1) // per_page)
    user = _user_context()
    return render_template(
        "market.html",
        items=items,
        page=page,
        total_pages=total_pages,
        category=category,
        user=user,
    )


@bp.route("/listing/<int:listing_id>")
def listing_detail(listing_id: int):
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """SELECT m.id, m.title, m.description, m.price, m.image_url,
                          m.category, m.condition, m.status, m.seller_id, m.created_at,
                          u.username
                   FROM market_items m
                   JOIN users u ON m.seller_id = u.id
                   WHERE m.id = %s""",
                (listing_id,),
            )
            row = cur.fetchone()

            other_products = []
            if row:
                cur.execute(
                    """SELECT id, title, price, image_url
                       FROM market_items
                       WHERE seller_id = %s AND id != %s AND status = 'active'
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
        "price": float(row[3]),
        "image": row[4],
        "category": row[5],
        "condition": row[6],
        "status": row[7],
        "seller_id": row[8],
        "created_at": row[9],
        "seller_display": row[10],
        "brand": None,
        "is_verified": 0,
        "is_sold": 1 if row[7] == "sold" else 0,
        "whatsapp": None,
    }

    others = []
    for o in other_products:
        others.append({
            "id": o[0],
            "title": o[1],
            "price": float(o[2]),
            "image": o[3],
            "seller_display": row[10],
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
                       WHERE status = 'active' AND (title ILIKE %s OR description ILIKE %s)""",
                    (like_q, like_q),
                )
                total_count = cur.fetchone()[0]
                cur.execute(
                    """SELECT m.id, m.title, m.price, m.image_url, m.category, m.condition, m.created_at, u.username
                       FROM market_items m
                       JOIN users u ON m.seller_id = u.id
                       WHERE m.status = 'active' AND (m.title ILIKE %s OR m.description ILIKE %s)
                       ORDER BY m.created_at DESC LIMIT %s OFFSET %s""",
                    (like_q, like_q, per_page, offset),
                )
            else:
                cur.execute(
                    "SELECT COUNT(*) FROM market_items WHERE status = 'active'"
                )
                total_count = cur.fetchone()[0]
                cur.execute(
                    """SELECT m.id, m.title, m.price, m.image_url, m.category, m.condition, m.created_at, u.username
                       FROM market_items m
                       JOIN users u ON m.seller_id = u.id
                       WHERE m.status = 'active'
                       ORDER BY m.created_at DESC LIMIT %s OFFSET %s""",
                    (per_page, offset),
                )
            rows = cur.fetchall()
    finally:
        close_db_connection(conn)

    items = []
    for r in rows:
        d = _item_row_to_dict(r[:7])
        d = _enrich_item(d, seller_name=r[7] if len(r) > 7 else None)
        items.append(d)

    total_pages = max(1, (total_count + per_page - 1) // per_page)
    user = _user_context()
    return render_template(
        "market.html",
        items=items,
        page=page,
        total_pages=total_pages,
        category="",
        query=query,
        user=user,
    )


@bp.route("/market/sold/<int:item_id>", methods=["POST"])
@login_required
def mark_sold(item_id: int):
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT seller_id FROM market_items WHERE id = %s", (item_id,)
            )
            item = cur.fetchone()
            if not item:
                flash("Item not found.", "error")
                return redirect(url_for("seller.seller_dash"))
            if item[0] != session["user_id"]:
                flash("You can only mark your own items as sold.", "error")
                return redirect(url_for("market.market"))
            cur.execute(
                "UPDATE market_items SET status = 'sold' WHERE id = %s", (item_id,)
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
                "SELECT seller_id, image_url FROM market_items WHERE id = %s",
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
