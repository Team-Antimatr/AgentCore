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


_CITY_REGION = {
    "Delhi": "North", "Jaipur": "North",
    "Mumbai": "West", "Pune": "West", "Ahmedabad": "West", "Indore": "Central",
    "Bengaluru": "South", "Hyderabad": "South", "Chennai": "South",
    "Kolkata": "East",
}


def fetch_shop_analytics(
    group_by: str = "summary",
    name_starts_with: str | None = None,
    name_ends_with: str | None = None,
) -> dict:
    """Return safe, aggregated, non-PII Bharat.in analytics from Neon PostgreSQL."""
    with get_conn() as conn:
        if conn is None:
            return {"connected": False, "error": "DATABASE_URL not configured"}
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM shop_users")
            total_users = cur.fetchone()[0]
            cur.execute("SELECT COUNT(*) FROM shop_orders")
            total_orders = cur.fetchone()[0]
            cur.execute("SELECT COUNT(*) FROM shop_products")
            total_products = cur.fetchone()[0]

            result: dict = {
                "connected": True,
                "total_users": total_users,
                "total_orders": total_orders,
                "total_products": total_products,
            }

            if group_by == "city":
                cur.execute("SELECT city, COUNT(*) FROM shop_users GROUP BY city ORDER BY COUNT(*) DESC")
                result["users_by_city"] = {row[0]: row[1] for row in cur.fetchall()}
                cur.execute(
                    "SELECT u.city, COUNT(*) FROM shop_orders o JOIN shop_users u ON o.user_id = u.id "
                    "GROUP BY u.city ORDER BY COUNT(*) DESC"
                )
                result["orders_by_city"] = {row[0]: row[1] for row in cur.fetchall()}

            elif group_by == "region":
                cur.execute("SELECT city, COUNT(*) FROM shop_users GROUP BY city")
                reg_users: dict[str, int] = {}
                for city, cnt in cur.fetchall():
                    reg = _CITY_REGION.get(city, "Other")
                    reg_users[reg] = reg_users.get(reg, 0) + cnt
                result["users_by_region"] = reg_users

                cur.execute(
                    "SELECT u.city, COUNT(*) FROM shop_orders o JOIN shop_users u ON o.user_id = u.id GROUP BY u.city"
                )
                reg_orders: dict[str, int] = {}
                for city, cnt in cur.fetchall():
                    reg = _CITY_REGION.get(city, "Other")
                    reg_orders[reg] = reg_orders.get(reg, 0) + cnt
                result["orders_by_region"] = reg_orders

            if name_starts_with or name_ends_with:
                prefix = f"{name_starts_with or ''}%"
                suffix = f"%{name_ends_with or ''}"
                pattern = f"{name_starts_with or ''}%{name_ends_with or ''}"
                cur.execute(
                    "SELECT COUNT(DISTINCT u.id), COUNT(o.id) FROM shop_users u "
                    "LEFT JOIN shop_orders o ON o.user_id = u.id WHERE u.name ILIKE %s",
                    (pattern,),
                )
                matched_users, matched_orders = cur.fetchone()
                result["name_filter"] = {
                    "pattern": pattern,
                    "matched_user_count": matched_users,
                    "matched_order_count": matched_orders,
                }

            return result


def fetch_live_telemetry(limit: int = 10) -> dict:
    """Return real cloud_telemetry stats and recent hits from Neon PostgreSQL."""
    with get_conn() as conn:
        if conn is None:
            return {"connected": False}
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*), COALESCE(AVG(cpu_percent), 0) FROM cloud_telemetry")
            total_hits, avg_cpu = cur.fetchone()
            cur.execute(
                "SELECT server_name, COUNT(*), ROUND(AVG(cpu_percent), 2) "
                "FROM cloud_telemetry GROUP BY server_name ORDER BY COUNT(*) DESC"
            )
            by_server = [
                {"server": r[0], "hits": r[1], "avg_cpu": float(r[2])} for r in cur.fetchall()
            ]
            cur.execute(
                "SELECT server_name, page, action, cpu_percent, created_at "
                "FROM cloud_telemetry ORDER BY id DESC LIMIT %s",
                (limit,),
            )
            recent = [
                {
                    "server": r[0],
                    "page": r[1],
                    "action": r[2],
                    "cpu": float(r[3]),
                    "at": r[4].isoformat() if r[4] else "",
                }
                for r in cur.fetchall()
            ]
            return {
                "connected": True,
                "total_hits": total_hits,
                "avg_cpu": round(float(avg_cpu), 2),
                "by_server": by_server,
                "recent": recent,
            }


def query_or_update_product(sku: str, action: str = "inspect", amount: int = 0) -> dict:
    """Inspect or restock a real product in Neon shop_products (no price/delete tampering)."""
    with get_conn() as conn:
        if conn is None:
            return {"connected": False}
        with conn.cursor() as cur:
            cur.execute(
                "SELECT sku, title, category, price_inr, stock FROM shop_products WHERE UPPER(sku) = UPPER(%s)",
                (sku.strip(),),
            )
            row = cur.fetchone()
            if not row:
                return {"connected": True, "found": False}
            if action == "restock":
                cur.execute(
                    "UPDATE shop_products SET stock = stock + %s WHERE UPPER(sku) = UPPER(%s) "
                    "RETURNING sku, title, category, price_inr, stock",
                    (amount, sku.strip()),
                )
                row = cur.fetchone()
                conn.commit()
            return {
                "connected": True,
                "found": True,
                "sku": row[0],
                "title": row[1],
                "category": row[2],
                "price_inr": float(row[3]),
                "stock": row[4],
            }


def query_or_update_order(order_code: str, action: str = "inspect", new_status: str = "") -> dict:
    """Inspect or update a single real order in Neon shop_orders (zero PII returned)."""
    with get_conn() as conn:
        if conn is None:
            return {"connected": False}
        with conn.cursor() as cur:
            cur.execute(
                "SELECT order_code, quantity, total_inr, status, payment_method, created_at "
                "FROM shop_orders WHERE UPPER(order_code) = UPPER(%s)",
                (order_code.strip(),),
            )
            row = cur.fetchone()
            if not row:
                return {"connected": True, "found": False}
            if action == "update_status" and new_status:
                cur.execute(
                    "UPDATE shop_orders SET status = %s WHERE UPPER(order_code) = UPPER(%s) "
                    "RETURNING order_code, quantity, total_inr, status, payment_method, created_at",
                    (new_status.strip().lower(), order_code.strip()),
                )
                row = cur.fetchone()
                conn.commit()
            return {
                "connected": True,
                "found": True,
                "order_code": row[0],
                "quantity": row[1],
                "total_inr": float(row[2]),
                "status": row[3],
                "payment_method": row[4],
                "created_at": row[5].isoformat() if row[5] else "",
            }


def fetch_recent_audit_logs(limit: int = 10) -> dict:
    """Return recent security/action audit logs from Neon PostgreSQL."""
    with get_conn() as conn:
        if conn is None:
            return {"connected": False}
        with conn.cursor() as cur:
            cur.execute(
                "SELECT prompt, guardrail_category, tool_used, status, created_at "
                "FROM agent_audit_logs ORDER BY id DESC LIMIT %s",
                (limit,),
            )
            rows = [
                {
                    "prompt": r[0],
                    "category": r[1],
                    "tool": r[2],
                    "status": r[3],
                    "at": r[4].isoformat() if r[4] else "",
                }
                for r in cur.fetchall()
            ]
            return {"connected": True, "logs": rows}
