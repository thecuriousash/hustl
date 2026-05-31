from flask import Blueprint, render_template, session, redirect, url_for, flash, request
from ..db import get_db_connection, close_db_connection
from ..helpers import get_image_url

bp = Blueprint("admin", __name__, url_prefix="/admin")


def admin_required(f):
    from functools import wraps
    @wraps(f)
    def wrapper(*args, **kwargs):
        if not session.get("is_admin"):
            return redirect(url_for("auth.login"))
        return f(*args, **kwargs)
    return wrapper


@bp.route("/")
@admin_required
def dashboard():
    conn = get_db_connection()
    pending_users = []
    total_users = 0
    market_oversight = []
    active_reports = 0
    claim_requests = []
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id, username, email FROM users WHERE is_seller = TRUE ORDER BY created_at DESC"
            )
            pending_users = [
                {"id": r[0], "display_name": r[1], "email": r[2]}
                for r in cur.fetchall()
            ]
            cur.execute("SELECT COUNT(*) FROM users")
            total_users = cur.fetchone()[0]
            cur.execute("SELECT id, title, price, image_url FROM market_items ORDER BY created_at DESC")
            market_oversight = [
                {"id": r[0], "title": r[1], "price": float(r[2]), "image": r[3]}
                for r in cur.fetchall()
            ]
            cur.execute("SELECT COUNT(*) FROM lost_items WHERE status = 'open'")
            active_reports = cur.fetchone()[0]
    finally:
        close_db_connection(conn)

    return render_template(
        "admin/dashboard.html",
        pending_users=pending_users,
        total_users=total_users,
        market_oversight=market_oversight,
        active_reports=active_reports,
        claim_requests=claim_requests,
    )


@bp.route("/users")
@admin_required
def users():
    conn = get_db_connection()
    rows = []
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id, username, email, is_seller, created_at FROM users ORDER BY created_at DESC"
            )
            rows = cur.fetchall()
    finally:
        close_db_connection(conn)

    user_list = [
        {
            "display_name": r[1],
            "email": r[2],
            "user_type": "seller" if r[3] else "buyer",
            "is_verified": 1,
            "created_at": r[4],
            "id": r[0],
        }
        for r in rows
    ]
    return render_template("admin/users.html", users=user_list)


@bp.route("/delete-user/<int:user_id>", methods=["POST"])
@admin_required
def delete_user(user_id: int):
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM users WHERE id = %s", (user_id,))
            conn.commit()
    finally:
        close_db_connection(conn)
    flash("User deleted.")
    return redirect(url_for("admin.users"))


@bp.route("/approve-item/<int:item_id>", methods=["POST"])
@admin_required
def approve_item(item_id: int):
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE market_items SET status = 'active' WHERE id = %s",
                (item_id,),
            )
            conn.commit()
    finally:
        close_db_connection(conn)
    flash("Item approved.")
    return redirect(url_for("admin.pending_approval"))


@bp.route("/reject-item/<int:item_id>", methods=["POST"])
@admin_required
def reject_item(item_id: int):
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE market_items SET status = 'rejected' WHERE id = %s",
                (item_id,),
            )
            conn.commit()
    finally:
        close_db_connection(conn)
    flash("Item rejected.")
    return redirect(url_for("admin.pending_approval"))


@bp.route("/pending-approval")
@admin_required
def pending_approval():
    return render_template("pending_approval.html")


@bp.route("/listings")
@admin_required
def all_listings():
    conn = get_db_connection()
    rows = []
    try:
        with conn.cursor() as cur:
            cur.execute(
                """SELECT m.id, m.title, m.price, m.image_url, m.status, m.created_at, u.username
                   FROM market_items m
                   JOIN users u ON m.seller_id = u.id
                   ORDER BY m.created_at DESC"""
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
            "status": r[4],
            "created_at": r[5],
            "user_display": r[6],
            "legal_name": "Student",
            "brand": None,
        }
        for r in rows
    ]
    return render_template("admin/manage_items.html", items=items)
