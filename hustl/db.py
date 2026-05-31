import os

from psycopg2 import pool as pypool
from supabase import Client, create_client
from flask import current_app

_pool: pypool.ThreadedConnectionPool | None = None
supabase: Client | None = None


def init_supabase(app) -> None:
    global supabase
    supabase = create_client(app.config["SUPABASE_URL"], app.config["SUPABASE_KEY"])
    app.config["supabase"] = supabase
    app.config["STORAGE_BUCKET"] = app.config.get("STORAGE_BUCKET", "listing-images")


def _get_pool() -> pypool.ThreadedConnectionPool:
    global _pool
    if _pool is None:
        db_url = current_app.config.get("DATABASE_URL") or os.environ.get("DATABASE_URL")
        _pool = pypool.ThreadedConnectionPool(
            2, 10, db_url, connect_timeout=5
        )
    return _pool


def get_db_connection():
    pool = _get_pool()
    return pool.getconn()


def close_db_connection(conn):
    global _pool
    if _pool is None:
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
                CREATE TABLE IF NOT EXISTS users (
                    id SERIAL PRIMARY KEY,
                    username VARCHAR(80) UNIQUE NOT NULL,
                    email VARCHAR(120) UNIQUE NOT NULL,
                    password_hash VARCHAR(256) NOT NULL,
                    is_seller BOOLEAN DEFAULT FALSE,
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
                )
            """
            )
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS market_items (
                    id SERIAL PRIMARY KEY,
                    title VARCHAR(200) NOT NULL,
                    description TEXT,
                    price NUMERIC(10, 2) NOT NULL,
                    category VARCHAR(50),
                    condition VARCHAR(50),
                    image_url VARCHAR(500),
                    seller_id INTEGER REFERENCES users(id),
                    status VARCHAR(20) DEFAULT 'active',
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
                )
            """
            )
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS lost_items (
                    id SERIAL PRIMARY KEY,
                    title VARCHAR(200) NOT NULL,
                    description TEXT,
                    image_url VARCHAR(500),
                    status VARCHAR(20) DEFAULT 'open',
                    submitted_by INTEGER REFERENCES users(id),
                    contact_email VARCHAR(120),
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
                )
            """
            )
            # Migrate existing tables that may lack columns added later
            _add_column_if_not_exists(cur, "market_items", "description", "TEXT")
            _add_column_if_not_exists(cur, "market_items", "seller_id", "INTEGER REFERENCES users(id)")
            _add_column_if_not_exists(cur, "market_items", "image_url", "VARCHAR(500)")
            _add_column_if_not_exists(cur, "market_items", "status", "VARCHAR(20) DEFAULT 'active'")
            _add_column_if_not_exists(cur, "market_items", "created_at", "TIMESTAMP WITH TIME ZONE DEFAULT NOW()")
            _add_column_if_not_exists(cur, "market_items", "category", "VARCHAR(50)")
            _add_column_if_not_exists(cur, "market_items", "condition", "VARCHAR(50)")
            _add_column_if_not_exists(cur, "lost_items", "image_url", "VARCHAR(500)")
            _add_column_if_not_exists(cur, "lost_items", "status", "VARCHAR(20) DEFAULT 'open'")
            _add_column_if_not_exists(cur, "lost_items", "created_at", "TIMESTAMP WITH TIME ZONE DEFAULT NOW()")
            _add_column_if_not_exists(cur, "users", "created_at", "TIMESTAMP WITH TIME ZONE DEFAULT NOW()")
            conn.commit()
    finally:
        close_db_connection(conn)


def _add_column_if_not_exists(cur, table: str, column: str, definition: str) -> None:
    cur.execute(
        """
        SELECT 1 FROM information_schema.columns
        WHERE table_name = %s AND column_name = %s
        """,
        (table, column),
    )
    exists = cur.fetchone()
    if not exists:
        cur.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")
