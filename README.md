# Hustl. — Campus Mini-Economy

A Flask-based campus marketplace for students to **buy/sell items** and report **lost & found** assets, with admin-mediated identity verification.

## Features

- **Buyer / Seller roles** with identity verification
- **Market Exchange** — list, browse, and contact sellers via WhatsApp
- **Lost & Found** — report and track missing items
- **Admin Panel** — verify student IDs, manage listings, delete items
- **Seller Dashboard** — manage your own listings, mark items as sold
- **Search & filters** — search by keyword, filter by category, paginated results
- **Image uploads** — Supabase Storage via `market-images` bucket
- **Rate limiting** — 200 requests/day, 50/hour per IP
- **CSRF protection** — enabled on all mutating endpoints
- **Security headers** — X-Content-Type-Options, X-Frame-Options, STS, X-XSS-Protection

## Quick Start

```bash
# Install dependencies
pip install -r requirements.txt

# Copy env template
cp .env.example .env

# Run locally
python3 app.py
```

Open [http://127.0.0.1:5000](http://127.0.0.1:5000)

**Default admin login:** `admin` / `changeme` (change via env vars in production!)

## Environment Variables

Copy `.env.example` to `.env` and configure:

| Variable | Required | Default | Description |
|---|---|---|---|
| `DATABASE_URL` | ✅ | — | PostgreSQL connection string (`postgres://user:pass@host/db`) |
| `SUPABASE_URL` | ✅ | — | Supabase project URL |
| `SUPABASE_KEY` | ✅ | — | Supabase API key (anon) |
| `SECRET_KEY` | ✅ | `dev-key-change-in-production` | Flask session secret (change for production) |
| `ADMIN_USERNAME` | ✅ | `admin` | Admin login username |
| `ADMIN_PASSWORD` | ✅ | `changeme` | Admin login password |
| `STORAGE_BUCKET` | — | `market-images` | Supabase Storage bucket for uploads |
| `SESSION_LIFETIME_HOURS` | — | `4` | Session duration in hours |
| `MAX_CONTENT_LENGTH` | — | `10485760` (10 MB) | Max upload size |
| `SESSION_COOKIE_SECURE` | — | `True` | Set `True` for HTTPS |
| `SESSION_COOKIE_HTTPONLY` | — | `True` | Set `False` for dev only |
| `SESSION_COOKIE_SAMESITE` | — | `Lax` | CSRF protection (`Strict`, `Lax`, `None`) |

## Deploying to Render

1. Create a **Web Service** on [Render](https://render.com)
2. **Set ALL environment variables** in the Render dashboard (especially `DATABASE_URL`, `SUPABASE_URL`, `SUPABASE_KEY`, `SECRET_KEY`)
3. Build command: `pip install -r requirements.txt`
4. Start command: (uses `Procfile` automatically)
   ```
   gunicorn app:app --bind 0.0.0.0:$PORT --workers 1 --threads 4 --timeout 30
   ```
5. Database tables are created automatically on first run via `init_db()`
6. Make sure `STORAGE_BUCKET=market-images` is set in Render env vars

## Database & Storage

- **Database:** PostgreSQL (via Supabase) — required for production
- **Storage:** Supabase Storage bucket (`market-images`) for all file uploads
- **Connection Issues on Render?**
  - Ensure `DATABASE_URL` is set in Render's environment variables
  - Verify the PostgreSQL endpoint is reachable from Render (may require IPv4 enforcement)
  - Check Supabase network rules allow inbound connections

## Project Structure

```
├── app.py                   # Entry point: create_app() → gunicorn
├── Procfile                 # Render start command
├── .env.example             # Environment variable template
├── hustl/
│   ├── __init__.py          # create_app() factory, CSRF, limiter, blueprints
│   ├── config.py            # Config class + validate_env()
│   ├── db.py                # Supabase client, psycopg2 connection pool, init_db()
│   ├── auth.py              # login_required / admin_required decorators
│   ├── helpers.py           # get_image_url(), allowed_file(), admin creds
│   └── routes/
│       ├── auth.py          # Login, signup, logout, admin login
│       ├── market.py        # Marketplace browse, search, filters, pagination
│       ├── seller.py        # Seller dashboard, create/edit/delete listing
│       ├── lost.py          # Lost & found report/claim
│       └── admin.py         # Admin dashboard, user management, item moderation
├── templates/
│   ├── base.html            # Layout with nav + footer
│   ├── auth.html            # Login / Signup combined
│   ├── index.html           # Home page
│   ├── market.html          # Marketplace listings grid
│   ├── listing_detail.html  # Individual listing page
│   ├── seller_dash.html     # Seller dashboard & management
│   ├── seller_profile.html  # Public seller profile
│   ├── seller_onboarding.html  # Become a seller form
│   ├── pending_approval.html   # Waiting for admin verification
│   ├── list_item.html       # Seller: add new listing
│   ├── lost.html            # Lost & found board
│   ├── error.html           # 404/403/500 error page
│   └── admin/
│       ├── dashboard.html   # Admin verification & claim requests
│       ├── users.html       # View all users & their statuses
│       └── manage_items.html   # Delete market items
├── static/
│   └── style.css            # Tailwind + custom styling
└── tests/
    └── test_app.py          # 11 integration tests (health, pages, auth, security)
```

## License

MIT
