"""Neon PostgreSQL helper for Online-Shopping data, telemetry, and agent audit logs."""

import os
from contextlib import contextmanager

from agent_core.config import load_dotenv


def get_database_url() -> str | None:
    """Return DATABASE_URL from environment if configured."""
    load_dotenv()
    return os.getenv("DATABASE_URL")


@contextmanager
def get_conn():
    """Yield a psycopg connection when DATABASE_URL is configured, else None."""
    url = get_database_url()
    if not url:
        yield None
        return
    import psycopg

    with psycopg.connect(url) as conn:
        yield conn


def ensure_tables() -> None:
    """Create required Online-Shopping & Cloud Guard tables if they do not exist."""
    with get_conn() as conn:
        if conn is None:
            return
        with conn.cursor() as cur:
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS shop_users (
                    id SERIAL PRIMARY KEY,
                    name TEXT NOT NULL,
                    email TEXT UNIQUE NOT NULL,
                    phone TEXT NOT NULL,
                    city TEXT NOT NULL,
                    created_at TIMESTAMPTZ DEFAULT NOW()
                );
                CREATE TABLE IF NOT EXISTS shop_products (
                    id SERIAL PRIMARY KEY,
                    sku TEXT UNIQUE NOT NULL,
                    title TEXT NOT NULL,
                    category TEXT NOT NULL,
                    price_inr NUMERIC(10, 2) NOT NULL,
                    stock INT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS shop_orders (
                    id SERIAL PRIMARY KEY,
                    order_code TEXT UNIQUE NOT NULL,
                    user_id INT REFERENCES shop_users(id),
                    product_id INT REFERENCES shop_products(id),
                    quantity INT NOT NULL,
                    total_inr NUMERIC(10, 2) NOT NULL,
                    status TEXT NOT NULL,
                    payment_method TEXT NOT NULL,
                    created_at TIMESTAMPTZ DEFAULT NOW()
                );
                CREATE TABLE IF NOT EXISTS cloud_telemetry (
                    id SERIAL PRIMARY KEY,
                    server_name TEXT NOT NULL,
                    page TEXT NOT NULL,
                    action TEXT NOT NULL,
                    cpu_percent NUMERIC(5, 2) NOT NULL,
                    created_at TIMESTAMPTZ DEFAULT NOW()
                );
                CREATE TABLE IF NOT EXISTS agent_audit_logs (
                    id SERIAL PRIMARY KEY,
                    prompt TEXT NOT NULL,
                    guardrail_category TEXT NOT NULL,
                    tool_used TEXT NOT NULL,
                    status TEXT NOT NULL,
                    summary TEXT NOT NULL,
                    created_at TIMESTAMPTZ DEFAULT NOW()
                );
                """
            )
        conn.commit()


def record_telemetry(server_name: str, page: str, action: str, cpu_percent: float) -> None:
    """Persist a frontend telemetry event to Neon PostgreSQL."""
    with get_conn() as conn:
        if conn is None:
            return
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO cloud_telemetry (server_name, page, action, cpu_percent) VALUES (%s, %s, %s, %s)",
                (server_name, page, action, cpu_percent),
            )
        conn.commit()


def record_audit(prompt: str, category: str, tool_used: str, status: str, summary: str) -> None:
    """Persist an agent audit event to Neon PostgreSQL."""
    with get_conn() as conn:
        if conn is None:
            return
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO agent_audit_logs (prompt, guardrail_category, tool_used, status, summary)
                VALUES (%s, %s, %s, %s, %s)
                """,
                (prompt, category, tool_used, status, summary),
            )
        conn.commit()


def fetch_db_summary() -> dict:
    """Return row counts across all tables for agentic visibility."""
    with get_conn() as conn:
        if conn is None:
            return {"connected": False}
        with conn.cursor() as cur:
            counts = {}
            for table in ("shop_users", "shop_products", "shop_orders", "cloud_telemetry", "agent_audit_logs"):
                cur.execute(f"SELECT COUNT(*) FROM {table}")
                counts[table] = cur.fetchone()[0]
            return {"connected": True, "tables": counts, "total_rows": sum(counts.values())}
