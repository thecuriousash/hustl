import psycopg2
from psycopg2.extras import RealDictCursor
from supabase import create_client, Client
import os
import re
import uuid
from datetime import timedelta
from dotenv import load_dotenv

load_dotenv()

from flask import Flask, render_template, request, redirect, session, url_for, flash, abort
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash
from flask_wtf.csrf import CSRFProtect
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
import logging

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'hustl_dev_fallback_key')
if app.secret_key == 'hustl_dev_fallback_key':
    logging.warning("Using fallback SECRET_KEY. Set SECRET_KEY environment variable for production.")

csrf = CSRFProtect(app)

limiter = Limiter(
    get_remote_address,
    app=app,
    default_limits=["200 per day", "50 per hour"],
    storage_uri="memory://",
)

app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(
    hours=int(os.environ.get('SESSION_LIFETIME_HOURS', 4))
)

app.config['SESSION_COOKIE_SECURE'] = os.environ.get('SESSION_COOKIE_SECURE', 'True') == 'True'
app.config['SESSION_COOKIE_HTTPONLY'] = os.environ.get('SESSION_COOKIE_HTTPONLY', 'True') == 'True'
app.config['SESSION_COOKIE_SAMESITE'] = os.environ.get('SESSION_COOKIE_SAMESITE', 'Lax')

app.config['MAX_CONTENT_LENGTH'] = int(os.environ.get('MAX_CONTENT_LENGTH', 4 * 1024 * 1024))
ALLOWED_EXTENSIONS = set(os.environ.get('ALLOWED_EXTENSIONS', 'png,jpg,jpeg,gif').split(','))

ADMIN_USERNAME = os.environ.get('ADMIN_USERNAME', 'admin')
ADMIN_PASSWORD_HASH = generate_password_hash(os.environ.get('ADMIN_PASSWORD', 'changeme'))

SUPABASE_URL = os.environ.get('SUPABASE_URL')
SUPABASE_KEY = os.environ.get('SUPABASE_KEY')
DATABASE_URL = os.environ.get('DATABASE_URL')
STORAGE_BUCKET = os.environ.get('STORAGE_BUCKET', 'market-images')

if SUPABASE_URL and SUPABASE_KEY:
    supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
else:
    supabase = None
    logging.warning("Missing SUPABASE_URL or SUPABASE_KEY. Image uploads will fail.")

EMAIL_RE = re.compile(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$')


def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def get_db_connection():
    if not DATABASE_URL:
        raise Exception("DATABASE_URL is not set. Please configure it in your environment.")
    conn = psycopg2.connect(DATABASE_URL)
    conn.autocommit = False
    return conn


def safe_execute(conn, sql, params=(), commit=False, fetchone=False, fetchall=False):
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(sql, params)
            if commit:
                conn.commit()
            if fetchone:
                return cur.fetchone()
            if fetchall:
                return cur.fetchall()
            return cur
    except psycopg2.Error as e:
        conn.rollback()
        app.logger.error('DB error executing SQL: %s | params=%s | Error: %s', sql, params, e)
        return None


def init_db():
    if not DATABASE_URL:
        logging.warning("DATABASE_URL not set, skipping DB init.")
        return
    conn = get_db_connection()
    try:
        safe_execute(conn, '''CREATE TABLE IF NOT EXISTS users (
                        id SERIAL PRIMARY KEY,
                        email TEXT UNIQUE, password_hash TEXT, reg_number TEXT, whatsapp TEXT,
                        display_name TEXT, legal_name TEXT, user_type TEXT,
                        id_proof_link TEXT, social_link TEXT,
                        role TEXT DEFAULT 'pending_verification',
                        is_verified INTEGER DEFAULT 0)''', commit=True)
        safe_execute(conn, 'ALTER TABLE users ADD COLUMN IF NOT EXISTS password_hash TEXT', commit=True)

        safe_execute(conn, '''CREATE TABLE IF NOT EXISTS market_items (
                        id SERIAL PRIMARY KEY,
                        title TEXT, brand TEXT, price TEXT, whatsapp TEXT, image TEXT,
                        is_sold INTEGER DEFAULT 0,
                        seller_brand TEXT, user_id INTEGER)''', commit=True)

        safe_execute(conn, '''CREATE TABLE IF NOT EXISTS lost_items (
                        id SERIAL PRIMARY KEY,
                        title TEXT, description TEXT, location TEXT, custody TEXT,
                        image TEXT, is_recovered INTEGER DEFAULT 0)''', commit=True)
        safe_execute(conn, 'ALTER TABLE lost_items ADD COLUMN IF NOT EXISTS is_recovered INTEGER DEFAULT 0', commit=True)

        safe_execute(conn, '''CREATE TABLE IF NOT EXISTS claim_requests (
                        id SERIAL PRIMARY KEY,
                        item_id INTEGER REFERENCES lost_items(id) ON DELETE CASCADE,
                        requester_email TEXT NOT NULL,
                        proof_details TEXT NOT NULL,
                        status TEXT DEFAULT 'pending',
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''', commit=True)
    finally:
        conn.close()


try:
    init_db()
except Exception as e:
    app.logger.error("Failed to initialize database at startup: %s. The app will continue but database operations may fail until the issue is resolved.", e)


def get_image_url(filename):
    if not filename or filename == 'default.png':
        return url_for('static', filename='images/default.png')
    if supabase:
        try:
            return supabase.storage.from_(STORAGE_BUCKET).get_public_url(filename)
        except Exception:
            pass
    return url_for('static', filename=f'images/{filename}')


@app.context_processor
def utility_processor():
    return dict(get_image_url=get_image_url)


@app.after_request
def add_security_headers(resp):
    resp.headers['X-Content-Type-Options'] = 'nosniff'
    resp.headers['X-Frame-Options'] = 'DENY'
    resp.headers['X-XSS-Protection'] = '1; mode=block'
    resp.headers['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains'
    return resp


@app.errorhandler(404)
def not_found(e):
    return render_template("error.html", code=404, message="Page not found."), 404


@app.errorhandler(403)
def forbidden(e):
    return render_template("error.html", code=403, message="You don't have permission to access this."), 403


@app.errorhandler(500)
def server_error(e):
    app.logger.error("Internal server error: %s", e)
    return render_template("error.html", code=500, message="Something went wrong."), 500


def get_current_user():
    email = session.get('email')
    if not email:
        return None
    try:
        conn = get_db_connection()
        try:
            user = safe_execute(conn, 'SELECT * FROM users WHERE email = %s', (email,), fetchone=True)
            return user
        finally:
            conn.close()
    except Exception as e:
        app.logger.error("Database error in get_current_user: %s", e)
        return None


@app.route("/health")
def health():
    return {"status": "ok"}, 200


@app.route("/")
def index():
    user = get_current_user()
    market_items = []
    lost_items = []
    try:
        conn = get_db_connection()
        try:
            market_items = safe_execute(
                conn,
                '''SELECT market_items.*, 
                          COALESCE(users.display_name, market_items.seller_brand, users.email, 'Campus Seller') AS seller_display
                   FROM market_items
                   LEFT JOIN users ON market_items.user_id = users.id
                   WHERE market_items.is_sold = 0
                   ORDER BY market_items.id DESC LIMIT 8''',
                fetchall=True
            ) or []
            lost_items = safe_execute(
                conn,
                'SELECT * FROM lost_items ORDER BY id DESC LIMIT 4',
                fetchall=True
            ) or []
        finally:
            conn.close()
    except Exception as e:
        app.logger.error("Database error in index route: %s", e)
        market_items = []
        lost_items = []
    return render_template("index.html", user=user, market_items=market_items, lost_items=lost_items)


@app.route("/login", methods=["GET", "POST"])
def login():
    if session.get('email'):
        return redirect(url_for('index'))
    if request.method == "POST":
        email = (request.form.get('email') or '').strip().lower()
        password = request.form.get('password')
        conn = get_db_connection()
        try:
            user = safe_execute(conn, 'SELECT * FROM users WHERE email = %s', (email,), fetchone=True)
            if user and user.get('password_hash') and check_password_hash(user['password_hash'], password):
                session.permanent = True
                session['email'] = email
                flash("Welcome back!", "success")
                return redirect(url_for('index'))

            if user and not user.get('password_hash'):
                flash("Please sign up to set a password for your old account.", "error")
            else:
                flash("Invalid email or password.", "error")
        finally:
            conn.close()
    return render_template("auth.html", is_login=True)


@app.route("/signup", methods=["GET", "POST"])
def signup():
    if session.get('email'):
        return redirect(url_for('index'))
    if request.method == "POST":
        email = (request.form.get('email') or '').strip().lower()
        password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')

        if not email or not EMAIL_RE.match(email):
            flash("Please enter a valid email address.", "error")
            return redirect(url_for('signup'))
        if not password or len(password) < 8:
            flash("Password must be at least 8 characters.", "error")
            return redirect(url_for('signup'))
        if password != confirm_password:
            flash("Passwords do not match.", "error")
            return redirect(url_for('signup'))

        hashed_pw = generate_password_hash(password)
        conn = get_db_connection()
        try:
            existing = safe_execute(conn, 'SELECT id, password_hash FROM users WHERE email = %s', (email,), fetchone=True)
            if existing and existing.get('password_hash'):
                flash("Account already exists. Please log in.", "error")
                return redirect(url_for('login'))

            if existing and not existing.get('password_hash'):
                safe_execute(conn, 'UPDATE users SET password_hash = %s WHERE email = %s', (hashed_pw, email), commit=True)
            else:
                safe_execute(conn, '''INSERT INTO users (email, password_hash, user_type, role) 
                                      VALUES (%s, %s, %s, %s)''',
                             (email, hashed_pw, 'buyer', 'buyer'), commit=True)
            session.permanent = True
            session['email'] = email
            flash("Account created successfully!", "success")
            return redirect(url_for('index'))
        finally:
            conn.close()
    return render_template("auth.html", is_login=False)


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for('index'))


@app.route("/seller-onboarding", methods=["GET", "POST"])
def seller_onboarding():
    if not session.get('email'):
        return redirect(url_for('login'))

    conn = get_db_connection()
    try:
        user = safe_execute(conn, 'SELECT * FROM users WHERE email = %s', (session['email'],), fetchone=True)
        if not user:
            return redirect(url_for('logout'))

        if request.method == "POST":
            legal_name = request.form.get('legal_name')
            display_name = request.form.get('display_name')
            reg_number = request.form.get('reg_number')
            whatsapp = request.form.get('whatsapp')
            id_proof_link = request.form.get('id_proof_link')
            social_link = request.form.get('social_link')

            safe_execute(conn, '''UPDATE users SET legal_name=%s, display_name=%s, reg_number=%s, whatsapp=%s,
                            id_proof_link=%s, social_link=%s, role='pending_verification', user_type='seller', is_verified=0
                            WHERE email = %s''',
                         (legal_name, display_name, reg_number, whatsapp, id_proof_link,
                          social_link, session['email']), commit=True)
            flash("Your seller profile has been submitted for review.", "success")
            return redirect(url_for('seller_onboarding'))

        if user.get('reg_number') and user.get('is_verified') == 0:
            return render_template("pending_approval.html")

    finally:
        conn.close()
    return render_template("seller_onboarding.html")


@app.route("/market", methods=["GET", "POST"])
def market():
    if not session.get('email'):
        return redirect(url_for('login'))
    conn = get_db_connection()
    try:
        user = safe_execute(conn, 'SELECT * FROM users WHERE email = %s', (session['email'],), fetchone=True)

        if request.method == "POST":
            if not user or user['is_verified'] != 1 or user['user_type'] != 'seller':
                flash("Only verified sellers can post items.", "error")
                return redirect(url_for('market'))

            img = request.files.get("image")
            filename = 'default.png'
            if img and img.filename:
                if not allowed_file(img.filename):
                    flash("File type not allowed.", "error")
                    return redirect(url_for('market'))
                filename = secure_filename(img.filename)

                if supabase:
                    file_content = img.read()
                    ext = filename.rsplit('.', 1)[1].lower() if '.' in filename else ''
                    unique_filename = f"{uuid.uuid4().hex}.{ext}" if ext else f"{uuid.uuid4().hex}"
                    try:
                        supabase.storage.from_(STORAGE_BUCKET).upload(
                            file=file_content,
                            path=unique_filename,
                            file_options={"content-type": img.content_type}
                        )
                        filename = unique_filename
                    except Exception as e:
                        app.logger.error("Failed to upload image to supabase: %s", e)
                        flash("Image upload failed. " + str(e), "error")
                        return redirect(url_for('market'))
                else:
                    flash("Database storage is not configured for remote uploads.", "error")

            brand = request.form.get('brand') or (user['display_name'] if user else None)
            seller_brand = user['display_name'] if user else None
            user_id = user['id'] if user else None

            safe_execute(conn, '''INSERT INTO market_items (title, brand, price, whatsapp, image, seller_brand, user_id)
                            VALUES (%s,%s,%s,%s,%s,%s,%s)''',
                         (request.form.get('title'), brand, request.form.get('price'),
                          request.form.get('whatsapp'), filename, seller_brand, user_id), commit=True)
            return redirect(url_for('market'))

        items = safe_execute(conn, '''SELECT market_items.*, 
                                        COALESCE(users.display_name, market_items.seller_brand, users.email, 'Campus Seller') AS seller_display
                                FROM market_items
                                LEFT JOIN users ON market_items.user_id = users.id
                                WHERE market_items.is_sold = 0
                                ORDER BY market_items.id DESC''', fetchall=True) or []
    finally:
        conn.close()
    return render_template("market.html", items=items,
                           user_type=(user['user_type'] if user else 'buyer'),
                           user=user)


@app.route("/listing/<int:item_id>")
def listing_detail(item_id):
    conn = get_db_connection()
    try:
        item = safe_execute(conn, '''SELECT market_items.*, 
                                        COALESCE(users.display_name, market_items.seller_brand, users.email, 'Campus Seller') AS seller_display
                                        FROM market_items 
                                        LEFT JOIN users ON market_items.user_id = users.id
                                        WHERE market_items.id = %s''', (item_id,), fetchone=True)
        if not item:
            abort(404)
        other_products = []
        if item['user_id']:
            other_products = safe_execute(
                conn,
                '''SELECT market_items.*, 
                          COALESCE(users.display_name, market_items.seller_brand, users.email, 'Campus Seller') AS seller_display
                   FROM market_items 
                   LEFT JOIN users ON market_items.user_id = users.id
                   WHERE market_items.user_id = %s AND market_items.id != %s AND market_items.is_sold = 0 
                   ORDER BY market_items.id DESC''',
                (item['user_id'], item_id), fetchall=True
            ) or []
    finally:
        conn.close()
    return render_template("listing_detail.html", item=item, other_products=other_products, quantity=1)


@app.route("/seller-dash")
def seller_dash():
    if not session.get('email'):
        return redirect(url_for('login'))
    conn = get_db_connection()
    try:
        user = safe_execute(conn, 'SELECT * FROM users WHERE email = %s', (session['email'],), fetchone=True)
        if not user or user['user_type'] != 'seller':
            return redirect(url_for('market'))
        items = safe_execute(
            conn,
            'SELECT * FROM market_items WHERE user_id = %s ORDER BY id DESC',
            (user['id'],), fetchall=True
        ) or []
    finally:
        conn.close()
    return render_template("seller_dash.html", items=items, user=user)


@app.route("/seller/<int:user_id>")
def seller_profile(user_id):
    conn = get_db_connection()
    try:
        seller = safe_execute(conn, 'SELECT * FROM users WHERE id = %s AND is_verified = 1',
                              (user_id,), fetchone=True)
        if not seller:
            abort(404)
        items = safe_execute(
            conn,
            'SELECT * FROM market_items WHERE user_id = %s AND is_sold = 0 ORDER BY id DESC',
            (user_id,), fetchall=True
        ) or []
    finally:
        conn.close()
    return render_template("seller_profile.html",
                           name=seller['display_name'],
                           whatsapp=seller['whatsapp'],
                           items=items,
                           join_date="2026")


@app.route("/market/sold/<int:item_id>")
def mark_sold(item_id):
    if not session.get('email'):
        return redirect(url_for('login'))
    conn = get_db_connection()
    try:
        user = safe_execute(conn, 'SELECT * FROM users WHERE email = %s', (session['email'],), fetchone=True)
        item = safe_execute(conn, 'SELECT * FROM market_items WHERE id = %s', (item_id,), fetchone=True)
        if not user or not item:
            abort(404)
        if item['user_id'] != user['id'] and not session.get('is_admin'):
            abort(403)
        safe_execute(conn, 'UPDATE market_items SET is_sold = 1 WHERE id = %s', (item_id,), commit=True)
    finally:
        conn.close()
    return redirect(url_for('seller_dash'))


@app.route("/lost", methods=["GET", "POST"])
def lost():
    conn = get_db_connection()
    try:
        if request.method == "POST":
            img = request.files.get("image")
            filename = None
            if img and img.filename and img.filename != '':
                if not allowed_file(img.filename):
                    flash("File type not allowed.", "error")
                    return redirect(url_for('lost'))
                orig_filename = secure_filename(img.filename)
                ext = orig_filename.rsplit('.', 1)[1].lower() if '.' in orig_filename else ''
                unique_filename = f"{uuid.uuid4().hex}.{ext}" if ext else f"{uuid.uuid4().hex}"
                try:
                    file_data = img.read()
                    supabase.storage.from_(STORAGE_BUCKET).upload(
                        file=file_data,
                        path=unique_filename,
                        file_options={"content-type": img.content_type}
                    )
                    filename = unique_filename
                    app.logger.info("Uploaded image to Supabase: %s", unique_filename)
                except Exception as e:
                    app.logger.error("Error uploading to Supabase: %s", e)
                    flash("Error uploading image to storage.", "error")
                    return redirect(url_for('lost'))

            title = request.form.get('title', 'Unknown Item')
            description = request.form.get('description', 'No description provided.')
            location = request.form.get('location', 'Unknown Location')
            custody = request.form.get('custody', 'With Mediator')

            safe_execute(conn,
                         'INSERT INTO lost_items (title, description, location, custody, image, is_recovered) VALUES (%s,%s,%s,%s,%s, 0)',
                         (title, description, location, custody, filename), commit=True)
            flash("Lost item reported successfully.", "success")
            return redirect(url_for('lost'))

        items = safe_execute(conn, 'SELECT * FROM lost_items WHERE is_recovered = 0 ORDER BY id DESC', fetchall=True) or []
        recovered_week = safe_execute(conn,
                                      "SELECT COUNT(*) as count FROM claim_requests WHERE status = 'approved' AND created_at > NOW() - INTERVAL '7 days'",
                                      fetchone=True)['count']
        verified_returns = safe_execute(conn,
                                        "SELECT COUNT(*) as count FROM claim_requests WHERE status = 'approved'",
                                        fetchone=True)['count']
    finally:
        conn.close()
    return render_template("lost.html",
                           items=items,
                           recovered_week=recovered_week,
                           verified_returns=verified_returns)


@app.route("/claim-item", methods=["POST"])
def claim_item():
    if not session.get('email'):
        flash("Please login to claim an item.", "error")
        return redirect(url_for('login'))

    item_id = request.form.get('item_id')
    proof = request.form.get('proof')

    if not item_id or not proof:
        flash("Missing claim details.", "error")
        return redirect(url_for('lost'))

    conn = get_db_connection()
    try:
        app.logger.info("Inserting claim for item %s by %s", item_id, session['email'])
        safe_execute(conn,
                     'INSERT INTO claim_requests (item_id, requester_email, proof_details) VALUES (%s,%s,%s)',
                     (item_id, session['email'], proof), commit=True)
        flash("Claim request submitted successfully! Admin will review it.", "success")
    finally:
        conn.close()

    return redirect(url_for('lost'))


@app.route("/admin", methods=["GET"])
def admin_dashboard():
    if not session.get('is_admin'):
        return redirect(url_for('admin_login'))

    conn = get_db_connection()
    try:
        pending_users = safe_execute(
            conn,
            'SELECT * FROM users WHERE is_verified = 0 AND reg_number IS NOT NULL',
            fetchall=True
        ) or []
        market_oversight = safe_execute(
            conn,
            '''SELECT market_items.*, users.display_name AS seller_display
               FROM market_items
               LEFT JOIN users ON market_items.user_id = users.id
               ORDER BY market_items.id DESC''',
            fetchall=True
        ) or []
        claim_requests = safe_execute(
            conn,
            '''SELECT claim_requests.*, lost_items.title AS item_title, lost_items.image AS item_image
               FROM claim_requests
               JOIN lost_items ON claim_requests.item_id = lost_items.id
               WHERE claim_requests.status = 'pending'
               ORDER BY claim_requests.created_at DESC''',
            fetchall=True
        ) or []

        total_users = safe_execute(conn, "SELECT COUNT(*) as count FROM users", fetchone=True)['count']
        active_reports = safe_execute(conn, "SELECT COUNT(*) as count FROM lost_items WHERE is_recovered = 0", fetchone=True)['count']

    finally:
        conn.close()
    return render_template("admin/dashboard.html",
                           pending_users=pending_users,
                           market_oversight=market_oversight,
                           claim_requests=claim_requests,
                           total_users=total_users,
                           active_reports=active_reports)


@app.route("/admin-login", methods=["GET", "POST"])
def admin_login():
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")
        if username == ADMIN_USERNAME and check_password_hash(ADMIN_PASSWORD_HASH, password):
            session.permanent = True
            session['is_admin'] = True
            session['email'] = ADMIN_USERNAME
            flash("Admin super-access granted.", "success")
            return redirect(url_for('admin_dashboard'))
        flash("Invalid credentials.", "error")
    return render_template("admin_login.html")


@app.route("/admin/verify/<int:uid>")
def verify_user(uid):
    if not session.get('is_admin'):
        return redirect("/")
    conn = get_db_connection()
    try:
        safe_execute(conn, 'UPDATE users SET is_verified = 1 WHERE id = %s', (uid,), commit=True)
    finally:
        conn.close()
    return redirect(url_for('admin_dashboard'))


@app.route("/admin/users")
def admin_manage_users():
    if not session.get('is_admin'):
        return redirect("/")
    conn = get_db_connection()
    try:
        users = safe_execute(conn, 'SELECT * FROM users ORDER BY id DESC', fetchall=True) or []
    finally:
        conn.close()
    return render_template("admin/users.html", users=users)


@app.route("/admin/manage-items")
def admin_manage_items():
    if not session.get('is_admin'):
        return redirect("/")
    conn = get_db_connection()
    try:
        items = safe_execute(conn, '''SELECT market_items.*, users.legal_name AS legal_name,
                                 COALESCE(users.display_name, market_items.seller_brand, users.email, 'Unknown') AS user_display
                                 FROM market_items LEFT JOIN users ON market_items.user_id = users.id
                                 ORDER BY market_items.id DESC''', fetchall=True) or []
    finally:
        conn.close()
    return render_template("admin/manage_items.html", items=items)


@app.route("/admin/delete-item/<int:item_id>")
def admin_delete_item(item_id):
    if not session.get('is_admin'):
        return redirect("/")
    conn = get_db_connection()
    try:
        item = safe_execute(conn, 'SELECT image FROM market_items WHERE id = %s', (item_id,), fetchone=True)
        if item and item['image'] and item['image'] != 'default.png':
            if supabase:
                try:
                    supabase.storage.from_(STORAGE_BUCKET).remove([item['image']])
                except Exception:
                    pass
        safe_execute(conn, 'DELETE FROM market_items WHERE id = %s', (item_id,), commit=True)
    finally:
        conn.close()
    return redirect(request.referrer or url_for('admin_manage_items'))


@app.route("/admin/approve-claim/<int:claim_id>")
def approve_claim(claim_id):
    if not session.get('is_admin'):
        return redirect("/")
    conn = get_db_connection()
    try:
        claim = safe_execute(conn, 'SELECT item_id FROM claim_requests WHERE id = %s', (claim_id,), fetchone=True)
        if claim:
            safe_execute(conn, "UPDATE claim_requests SET status = 'approved' WHERE id = %s", (claim_id,), commit=True)
            safe_execute(conn, "UPDATE lost_items SET is_recovered = 1 WHERE id = %s", (claim['item_id'],), commit=True)
            flash("Claim approved and item marked as recovered!", "success")
    finally:
        conn.close()
    return redirect(url_for('admin_dashboard'))


@app.route("/admin/reject-claim/<int:claim_id>")
def reject_claim(claim_id):
    if not session.get('is_admin'):
        return redirect("/")
    conn = get_db_connection()
    try:
        safe_execute(conn, "UPDATE claim_requests SET status = 'rejected' WHERE id = %s", (claim_id,), commit=True)
        flash("Claim request rejected.", "success")
    finally:
        conn.close()
    return redirect(url_for('admin_dashboard'))


if __name__ == "__main__":
    debug = os.environ.get('FLASK_ENV') == 'development'
    app.run(debug=debug, port=5000)
