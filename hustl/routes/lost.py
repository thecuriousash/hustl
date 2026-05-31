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

bp = Blueprint("lost", __name__, url_prefix="")


@bp.route("/lost")
def lost_and_found():
    conn = get_db_connection()
    rows = []
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id, title, description, image_url, status, created_at FROM lost_items ORDER BY created_at DESC"
            )
            rows = cur.fetchall()
    finally:
        close_db_connection(conn)

    items = [
        {
            "id": r[0],
            "title": r[1],
            "description": r[2],
            "image": r[3],
            "status": r[4],
            "created_at": r[5],
            "location": "Campus (unreported)",
            "custody": "Lost & Found Office",
        }
        for r in rows
    ]
    return render_template(
        "lost.html",
        items=items,
        recovered_week=0,
        verified_returns=0,
    )


@bp.route("/lost-item", methods=["GET", "POST"])
def report_lost():
    if request.method == "POST":
        title = request.form.get("title", "").strip()
        description = request.form.get("description", "").strip()
        contact_email = request.form.get("contact_email", "").strip()
        file = request.files.get("image")

        if not title or not description or not contact_email:
            flash("All fields are required.", "error")
            return render_template("list_item.html")

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
                        "Failed to upload lost item image: %s", exc
                    )
                    flash("Image upload failed.", "error")

        conn = get_db_connection()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """INSERT INTO lost_items (title, description, image_url, submitted_by, contact_email)
                       VALUES (%s, %s, %s, %s, %s)""",
                    (
                        title,
                        description,
                        image_url,
                        session.get("user_id"),
                        contact_email,
                    ),
                )
                conn.commit()
        finally:
            close_db_connection(conn)
        flash("Lost item reported. Hope you find it!")
        return redirect(url_for("lost.lost_and_found"))

    return render_template("list_item.html")


@bp.route("/claim-item", methods=["POST"])
def claim_item():
    item_id = request.form.get("item_id", type=int)
    if not item_id:
        flash("Invalid claim request.", "error")
        return redirect(url_for("lost.lost_and_found"))

    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE lost_items SET status = 'claimed' WHERE id = %s AND status = 'open'",
                (item_id,),
            )
            conn.commit()
    finally:
        close_db_connection(conn)
    flash("Claim submitted successfully.")
    return redirect(url_for("lost.lost_and_found"))
