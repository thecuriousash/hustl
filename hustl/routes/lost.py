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
                "SELECT id, title, description, image, is_recovered, location, custody, created_at, claim_status FROM lost_items ORDER BY created_at DESC"
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
            "is_recovered": r[4],
            "location": r[5] or "Campus (unreported)",
            "custody": r[6] or "Lost & Found Office",
            "created_at": r[7],
            "claim_status": r[8] or "none",
        }
        for r in rows
    ]
    active_count = sum(1 for i in items if not i["is_recovered"])
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
        location = request.form.get("location", "").strip()
        file = request.files.get("image")

        if not title or not description:
            flash("Title and description are required.", "error")
            return render_template("list_item.html")

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
                        "Failed to upload lost item image: %s", exc
                    )
                    flash("Image upload failed.", "error")

        conn = get_db_connection()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """INSERT INTO lost_items (title, description, location, image)
                       VALUES (%s, %s, %s, %s)""",
                    (title, description, location, image_path),
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
    proof = request.form.get("proof", "").strip()
    claimant_name = request.form.get("claimant_name", "").strip() or session.get("display_name", "Anonymous")

    if not item_id:
        flash("Invalid claim request.", "error")
        return redirect(url_for("lost.lost_and_found"))

    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """UPDATE lost_items
                   SET claim_status = 'pending', claimant_name = %s, claimant_proof = %s
                   WHERE id = %s AND is_recovered = 0 AND claim_status = 'none'""",
                (claimant_name, proof, item_id),
            )
            if cur.rowcount == 0:
                flash("This item has already been claimed or recovered.", "error")
            else:
                conn.commit()
                flash("Claim submitted. Awaiting admin review.")
    finally:
        close_db_connection(conn)
    return redirect(url_for("lost.lost_and_found"))
