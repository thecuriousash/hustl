import os

from psycopg2 import pool as pypool
from supabase import Client, create_client
from flask import current_app

_pool: pypool.ThreadedConnectionPool | None = None
supabase: Client | None = None


def init_supabase(app) -> None:
    global supabase
    url = app.config.get("SUPABASE_URL")
    key = app.config.get("SUPABASE_KEY")
    if not url or not key:
        app.logger.warning("SUPABASE_URL or SUPABASE_KEY not set — storage disabled")
        app.config["supabase"] = None
        return
    try:
        supabase = create_client(url, key)
        app.config["supabase"] = supabase
    except Exception as exc:
        app.logger.error("Failed to init Supabase client: %s", exc)
        app.config["supabase"] = None
    app.config["STORAGE_BUCKET"] = app.config.get("STORAGE_BUCKET", "listing-images")


def _get_pool() -> pypool.ThreadedConnectionPool | None:
    global _pool
    if _pool is None:
        db_url = current_app.config.get("DATABASE_URL") or os.environ.get("DATABASE_URL")
        if not db_url:
            current_app.logger.error("DATABASE_URL not set — cannot create connection pool")
            return None
        _pool = pypool.ThreadedConnectionPool(
            2, 10, db_url, connect_timeout=5
        )
    return _pool


def get_db_connection():
    pool = _get_pool()
    if pool is None:
        raise RuntimeError("Database pool not available (DATABASE_URL not set)")
    return pool.getconn()


def close_db_connection(conn):
    global _pool
    if _pool is None:
        try:
            conn.close()
        except Exception:
            pass
        return
    try:
        _pool.putconn(conn)
    except Exception:
        try:
            conn.close()
        except Exception:
            pass


def init_db() -> None:
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS public.users (
                    id SERIAL PRIMARY KEY,
                    email TEXT UNIQUE NOT NULL,
                    display_name TEXT,
                    password_hash TEXT NOT NULL,
                    user_type TEXT DEFAULT 'buyer',
                    is_verified INTEGER DEFAULT 0,
                    whatsapp TEXT,
                    legal_name TEXT,
                    reg_number TEXT,
                    role TEXT DEFAULT 'user',
                    id_proof_link TEXT,
                    social_link TEXT
                )
            """
            )
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS market_items (
                    id SERIAL PRIMARY KEY,
                    title TEXT NOT NULL,
                    description TEXT,
                    price TEXT NOT NULL,
                    category VARCHAR(50),
                    condition VARCHAR(50),
                    brand TEXT,
                    whatsapp TEXT,
                    image TEXT,
                    is_sold INTEGER DEFAULT 0,
                    user_id INTEGER REFERENCES public.users(id),
                    seller_brand TEXT,
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
                )
            """
            )
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS lost_items (
                    id SERIAL PRIMARY KEY,
                    title TEXT NOT NULL,
                    description TEXT,
                    location TEXT,
                    custody TEXT,
                    image TEXT,
                    is_recovered INTEGER DEFAULT 0,
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
                )
            """
            )
            # Migration helpers for columns that may exist in some versions
            _add_column_if_not_exists(cur, "market_items", "image", "TEXT")
            _add_column_if_not_exists(cur, "market_items", "image_url", "VARCHAR(500)")
            _add_column_if_not_exists(cur, "market_items", "status", "VARCHAR(20) DEFAULT 'active'")
            _add_column_if_not_exists(cur, "market_items", "created_at", "TIMESTAMP WITH TIME ZONE DEFAULT NOW()")
            _add_column_if_not_exists(cur, "market_items", "seller_id", "INTEGER REFERENCES public.users(id)")
            _add_column_if_not_exists(cur, "market_items", "brand", "TEXT")
            _add_column_if_not_exists(cur, "lost_items", "image", "TEXT")
            _add_column_if_not_exists(cur, "lost_items", "image_url", "VARCHAR(500)")
            _add_column_if_not_exists(cur, "lost_items", "status", "VARCHAR(20) DEFAULT 'open'")
            _add_column_if_not_exists(cur, "lost_items", "is_recovered", "INTEGER DEFAULT 0")
            _add_column_if_not_exists(cur, "lost_items", "location", "TEXT")
            _add_column_if_not_exists(cur, "lost_items", "custody", "TEXT")
            _add_column_if_not_exists(cur, "lost_items", "created_at", "TIMESTAMP WITH TIME ZONE DEFAULT NOW()")
            _add_column_if_not_exists(cur, "lost_items", "submitted_by", "INTEGER REFERENCES public.users(id)")
            _add_column_if_not_exists(cur, "lost_items", "contact_email", "TEXT")
            conn.commit()
    finally:
        close_db_connection(conn)


def _add_column_if_not_exists(cur, table: str, column: str, definition: str) -> None:
    cur.execute(
        """
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'public' AND table_name = %s AND column_name = %s
        """,
        (table, column),
    )
    exists = cur.fetchone()
    if not exists:
        cur.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")
