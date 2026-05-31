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
    pending_items = []
    claim_requests = []
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id, display_name, email FROM public.users WHERE user_type = 'seller' AND is_verified = 0 ORDER BY id DESC"
            )
            pending_users = [
                {"id": r[0], "display_name": r[1], "email": r[2]}
                for r in cur.fetchall()
            ]
            cur.execute("SELECT COUNT(*) FROM public.users")
            total_users = cur.fetchone()[0]
            cur.execute(
                "SELECT id, title, price, image FROM market_items WHERE is_sold = 0 ORDER BY created_at DESC"
            )
            market_oversight = [
                {"id": r[0], "title": r[1], "price": float(r[2]) if r[2] else 0, "image": r[3]}
                for r in cur.fetchall()
            ]
            cur.execute("SELECT COUNT(*) FROM lost_items WHERE is_recovered = 0")
            active_reports = cur.fetchone()[0]

            # Pending approval items (not yet approved by admin)
            cur.execute(
                """SELECT m.id, m.title, m.price, m.image, COALESCE(u.display_name, u.email)
                   FROM market_items m
                   LEFT JOIN public.users u ON m.user_id = u.id
                   WHERE m.is_approved = 0
                   ORDER BY m.created_at DESC"""
            )
            pending_items = [
                {"id": r[0], "title": r[1], "price": float(r[2]) if r[2] else 0, "image": r[3], "seller": r[4] or "Unknown"}
                for r in cur.fetchall()
            ]

            # Claim requests (pending admin review)
            cur.execute(
                """SELECT id, title, claimant_name, claimant_proof
                   FROM lost_items
                   WHERE claim_status = 'pending'
                   ORDER BY created_at DESC"""
            )
            claim_requests = [
                {"id": r[0], "item_title": r[1], "requester_email": r[2] or "Unknown", "proof_details": r[3] or ""}
                for r in cur.fetchall()
            ]
    finally:
        close_db_connection(conn)

    return render_template(
        "admin/dashboard.html",
        pending_users=pending_users,
        total_users=total_users,
        market_oversight=market_oversight,
        active_reports=active_reports,
        pending_items=pending_items,
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
                "SELECT id, display_name, email, user_type, is_verified FROM public.users ORDER BY id DESC"
            )
            rows = cur.fetchall()
    finally:
        close_db_connection(conn)

    user_list = [
        {
            "display_name": r[1],
            "email": r[2],
            "user_type": r[3] or "buyer",
            "is_verified": r[4] or 0,
            "created_at": None,
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
            cur.execute("DELETE FROM market_items WHERE user_id = %s", (user_id,))
            cur.execute("DELETE FROM public.users WHERE id = %s", (user_id,))
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
                "UPDATE market_items SET is_approved = 1 WHERE id = %s",
                (item_id,),
            )
            conn.commit()
    finally:
        close_db_connection(conn)
    flash("Item approved.")
    return redirect(url_for("admin.dashboard"))


@bp.route("/reject-item/<int:item_id>", methods=["POST"])
@admin_required
def reject_item(item_id: int):
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE market_items SET is_approved = 0 WHERE id = %s",
                (item_id,),
            )
            conn.commit()
    finally:
        close_db_connection(conn)
    flash("Item rejected.")
    return redirect(url_for("admin.dashboard"))


@bp.route("/approve-claim/<int:item_id>", methods=["POST"])
@admin_required
def approve_claim(item_id: int):
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE lost_items SET is_recovered = 1, claim_status = 'approved' WHERE id = %s",
                (item_id,),
            )
            conn.commit()
    finally:
        close_db_connection(conn)
    flash("Claim approved, item marked as recovered.")
    return redirect(url_for("admin.dashboard"))


@bp.route("/reject-claim/<int:item_id>", methods=["POST"])
@admin_required
def reject_claim(item_id: int):
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE lost_items SET claim_status = 'rejected' WHERE id = %s",
                (item_id,),
            )
            conn.commit()
    finally:
        close_db_connection(conn)
    flash("Claim rejected.")
    return redirect(url_for("admin.dashboard"))


@bp.route("/verify/<int:user_id>", methods=["POST"])
@admin_required
def verify_user(user_id: int):
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE public.users SET is_verified = 1 WHERE id = %s",
                (user_id,),
            )
            conn.commit()
    finally:
        close_db_connection(conn)
    flash("User verified.")
    return redirect(url_for("admin.dashboard"))


@bp.route("/unverify/<int:user_id>", methods=["POST"])
@admin_required
def unverify_user(user_id: int):
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE public.users SET is_verified = 0 WHERE id = %s",
                (user_id,),
            )
            conn.commit()
    finally:
        close_db_connection(conn)
    flash("User unverified.")
    return redirect(url_for("admin.dashboard"))


@bp.route("/pending-approval")
@admin_required
def pending_approval():
    return render_template("pending_approval.html")


@bp.route("/delete-item/<int:item_id>", methods=["POST"])
@admin_required
def delete_item(item_id: int):
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM market_items WHERE id = %s", (item_id,))
            conn.commit()
    finally:
        close_db_connection(conn)
    flash("Item deleted.")
    return redirect(url_for("admin.all_listings"))


@bp.route("/listings")
@admin_required
def all_listings():
    conn = get_db_connection()
    rows = []
    try:
        with conn.cursor() as cur:
            cur.execute(
                """SELECT m.id, m.title, m.price, m.image, m.is_sold, m.created_at,
                          COALESCE(u.display_name, u.email), u.legal_name, m.brand
                   FROM market_items m
                   LEFT JOIN public.users u ON m.user_id = u.id
                   ORDER BY m.created_at DESC"""
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
            "user_display": r[6] or "Unknown",
            "legal_name": r[7] or "Student",
            "brand": r[8],
        }
        for r in rows
    ]
    return render_template("admin/manage_items.html", items=items)
