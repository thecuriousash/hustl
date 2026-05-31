# Hustl. — Campus Mini-Economy

A Flask-based campus marketplace for students to **buy/sell items** and report **lost & found** assets, with admin-mediated identity verification and item approval.

## Features

- **Buyer / Seller roles** — signup defaults to buyer; seller registration collects legal name, phone, ID proof, and social link
- **Item approval workflow** — new sellers' items start pending; admin must approve before they go live
- **Market Exchange** — browse, search, filter by category, view listings with WhatsApp contact
- **Lost & Found** — report missing items; claimants submit name + proof; admin approves or rejects claims
- **Admin Panel** — verify/unverify sellers, approve/reject items, approve/reject claims, manage all users and listings
- **Seller Dashboard** — manage listings, see status (Pending / Live / Sold), mark items as sold
- **Search & filters** — keyword search, category filter, paginated results
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

**Admin login credentials are read from environment variables** (`ADMIN_USERNAME` / `ADMIN_PASSWORD`). Set them in `.env` or in your Render dashboard. See [Environment Variables](#environment-variables).

## Environment Variables

Copy `.env.example` to `.env` and configure:

| Variable | Required | Default | Description |
|---|---|---|---|
| `DATABASE_URL` | ✅ | — | PostgreSQL connection string (`postgres://user:pass@host/db`) |
| `SUPABASE_URL` | ✅ | — | Supabase project URL |
| `SUPABASE_KEY` | ✅ | — | Supabase API key (anon) |
| `SECRET_KEY` | ✅ | `dev-key-change-in-production` | Flask session secret (change for production) |
| `ADMIN_USERNAME` | ✅ | `admin` | Admin login email/username |
| `ADMIN_PASSWORD` | ✅ | `changeme` | Admin login password |
| `STORAGE_BUCKET` | — | `market-images` | Supabase Storage bucket for uploads |
| `SESSION_LIFETIME_HOURS` | — | `4` | Session duration in hours |
| `MAX_CONTENT_LENGTH` | — | `10485760` (10 MB) | Max upload size |
| `SESSION_COOKIE_SECURE` | — | `True` | Set `True` for HTTPS |
| `SESSION_COOKIE_HTTPONLY` | — | `True` | Set `False` for dev only |
| `SESSION_COOKIE_SAMESITE` | — | `Lax` | CSRF protection (`Strict`, `Lax`, `None`) |

## Deploying to Render

1. Create a **Web Service** on [Render](https://render.com)
2. Set **ALL environment variables** in the Render dashboard (especially `ADMIN_USERNAME`, `ADMIN_PASSWORD`, `DATABASE_URL`, `SUPABASE_URL`, `SUPABASE_KEY`, `SECRET_KEY`)
3. Set `WEB_CONCURRENCY=1` in Render env vars (free tier memory limit)
4. Build command: `pip install -r requirements.txt`
5. Start command: (uses `Procfile` automatically)
   ```
   gunicorn app:app --bind 0.0.0.0:$PORT --workers 1 --threads 4 --timeout 30
   ```
6. Database tables are created automatically on first run via `init_db()`
7. Make sure `STORAGE_BUCKET=market-images` is set in Render env vars

## Database & Storage

- **Database:** PostgreSQL (via Supabase) — required for production
- **Storage:** Supabase Storage bucket (`market-images`) for all file uploads
- **Connection Issues on Render?**
  - Ensure `DATABASE_URL` is set in Render's environment variables
  - Verify the PostgreSQL endpoint is reachable from Render (may require IPv4 enforcement)
  - Check Supabase network rules allow inbound connections

## Registration & Approval Flow

### Signup
- User signs up with display name, email, and password
- Default role: `buyer`, `is_verified = 0`
- Display name falls back to email prefix if not provided

### Become a Seller
- Click **Sell Something** (FAB on home page) → redirected to `/seller-dash`
- If not a seller, redirected to **Seller Onboarding** form
- Onboarding collects: legal name, display name, registration number, WhatsApp, ID proof link, social link
- After submission: `user_type` set to `'seller'`, `is_verified` remains `0`

### List an Item
- From Seller Dashboard, click **New Listing** → product form (title, price, WhatsApp, photo, description, category, condition, brand)
- If seller is unverified (`is_verified = 0`), item created with `is_approved = 0`
- Item appears in seller's dashboard with **Pending** badge, but is NOT visible in the public marketplace

### Admin Approval (two steps required)

| Step | Admin Action | Location | Effect |
|---|---|---|---|
| 1. Verify seller | Click **Verify** | Admin → Pending Sellers | `is_verified = 1` |
| 2. Approve item | Click **Approve** | Admin → Pending Items | `is_approved = 1` |

After both: item appears in marketplace for all users (logged in or not).

### Rejection
- **Reject seller**: Admin clicks **Reject** in Pending Sellers → user and their data are removed
- **Reject item**: Admin clicks **Reject** in Pending Items → item is deleted

### Lost & Found Claims
- Anyone can report a lost item
- Claimants fill name + proof of ownership → stored with `claim_status = 'pending'`
- Admin reviews claim proof in the **Claim Requests** panel
- **Approve claim** → `is_recovered = 1`, `claim_status = 'approved'` (item shown as recovered)
- **Reject claim** → `claim_status = 'rejected'` (item stays lost, new claims can be submitted)

## Project Structure

```
├── app.py                   # Entry point: create_app() → gunicorn
├── Procfile                 # Render start command
├── .env.example             # Environment variable template
├── hustl/
│   ├── __init__.py          # create_app() factory, CSRF, limiter, blueprints
│   ├── config.py            # Config class + validate_env()
│   ├── db.py                # Supabase client, psycopg2 connection pool, init_db()
│   ├── auth.py              # login_required decorator
│   ├── helpers.py           # get_image_url(), allowed_file(), admin creds from env
│   └── routes/
│       ├── auth.py          # Login, signup, logout, admin login
│       ├── market.py        # Marketplace browse, search, filters, pagination
│       ├── seller.py        # Seller dashboard, onboarding, create listing
│       ├── lost.py          # Lost & found report/claim
│       └── admin.py         # Admin dashboard, user/item/claim moderation
├── templates/
│   ├── base.html            # Layout with nav, footer, FAB, product/lost modals
│   ├── auth.html            # Login / Signup combined
│   ├── index.html           # Home page
│   ├── market.html          # Marketplace listings grid
│   ├── listing_detail.html  # Individual listing page
│   ├── seller_dash.html     # Seller dashboard & management
│   ├── seller_profile.html  # Public seller profile
│   ├── seller_onboarding.html  # Become a seller form
│   ├── pending_approval.html   # Waiting for admin verification page
│   ├── list_item.html       # Standalone add-listing form
│   ├── lost.html            # Lost & found board
│   ├── error.html           # 404/403/500 error page
│   └── admin/
│       ├── dashboard.html   # Admin: verify sellers, approve/reject items, review claims
│       ├── users.html       # View all users & their verification status
│       └── manage_items.html   # Delete market items
├── static/
│   └── style.css            # Tailwind + custom styling
└── tests/
    └── test_app.py          # 26 integration tests (health, pages, auth, admin E2E)
```

## License

MIT
