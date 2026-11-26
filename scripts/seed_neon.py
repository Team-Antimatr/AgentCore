"""Seed Neon PostgreSQL (neondb) with ~1,700 realistic Online-Shopping & telemetry rows."""

import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend.db import ensure_tables, fetch_db_summary, get_conn

FIRST_NAMES = [
    "Aarav", "Vivaan", "Aditya", "Vihaan", "Arjun", "Sai", "Reyansh", "Ayaan", "Krishna", "Ishaan",
    "Ananya", "Diya", "Saanvi", "Aadhya", "Kiara", "Myra", "Pari", "Riya", "Sneha", "Pooja",
]
LAST_NAMES = [
    "Sharma", "Verma", "Patel", "Reddy", "Nair", "Mehta", "Gupta", "Joshi", "Singh", "Kulkarni",
]
CITIES = ["Mumbai", "Delhi", "Bengaluru", "Pune", "Hyderabad", "Chennai", "Kolkata", "Ahmedabad", "Jaipur", "Indore"]
CATEGORIES = {
    "Electronics": ["Noise Cancelling Headphones", "Smartwatch Pro", "4K Action Camera", "USB-C Hub 8-in-1", "Mechanical Keyboard"],
    "Mobiles": ["5G Smartphone 128GB", "Fast GaN Charger 65W", "MagSafe Power Bank", "Tempered Glass Kit", "TWS Earbuds"],
    "Home & Kitchen": ["Air Fryer 4.5L", "Electric Kettle 1.5L", "Robot Vacuum", "LED Desk Lamp", "Coffee Grinder"],
    "Fashion": ["Running Sneakers", "Cotton Polo Tee", "Polarized Sunglasses", "Laptop Backpack 28L", "Leather Wallet"],
    "Fresh": ["Organic Green Tea", "Cold-Pressed Olive Oil", "Roasted Almonds 500g", "Artisan Dark Chocolate", "Filter Coffee 250g"],
}
ORDER_STATUSES = ["delivered", "delivered", "delivered", "shipped", "processing", "cancelled"]
PAYMENTS = ["UPI", "Credit Card", "Debit Card", "NetBanking", "Pay on Delivery"]
PAGES = ["index.html", "checkout.html", "order_confirmation.html", "order_history.html", "sign_in.html"]


def seed() -> None:
    """Create tables and insert 300 users, 100 products, 1,000 orders, and 300 telemetry rows."""
    random.seed(42)
    ensure_tables()

    with get_conn() as conn:
        if conn is None:
            raise RuntimeError("DATABASE_URL is not configured in .env")

        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM shop_users")
            if cur.fetchone()[0] >= 300:
                print("Database already seeded:", fetch_db_summary())
                return

            # 1. Seed 300 Users
            user_rows = []
            for i in range(1, 301):
                name = f"{random.choice(FIRST_NAMES)} {random.choice(LAST_NAMES)}"
                email = f"customer{i}@bharatshop.in"
                phone = f"+91 98{random.randint(10000000, 99999999)}"
                city = random.choice(CITIES)
                user_rows.append((name, email, phone, city))
            cur.executemany(
                "INSERT INTO shop_users (name, email, phone, city) VALUES (%s, %s, %s, %s) ON CONFLICT DO NOTHING",
                user_rows,
            )

            # 2. Seed 100 Products
            product_rows = []
            idx = 1
            for cat, titles in CATEGORIES.items():
                for base_title in titles:
                    for variant in ("Standard", "Pro", "Lite", "Edition"):
                        sku = f"BHR-{idx:04d}"
                        title = f"{base_title} ({variant})"
                        price = round(random.uniform(299.0, 24999.0), 2)
                        stock = random.randint(10, 500)
                        product_rows.append((sku, title, cat, price, stock))
                        idx += 1
            cur.executemany(
                "INSERT INTO shop_products (sku, title, category, price_inr, stock) VALUES (%s, %s, %s, %s, %s) ON CONFLICT DO NOTHING",
                product_rows,
            )

            cur.execute("SELECT id FROM shop_users ORDER BY id")
            user_ids = [r[0] for r in cur.fetchall()]
            cur.execute("SELECT id, price_inr FROM shop_products ORDER BY id")
            products = cur.fetchall()

            # 3. Seed 1,000 Orders
            order_rows = []
            for i in range(1, 1001):
                uid = random.choice(user_ids)
                pid, unit_price = random.choice(products)
                qty = random.randint(1, 3)
                total = round(float(unit_price) * qty, 2)
                order_rows.append(
                    (
                        f"ORD-2026-{10000 + i}",
                        uid,
                        pid,
                        qty,
                        total,
                        random.choice(ORDER_STATUSES),
                        random.choice(PAYMENTS),
                    )
                )
            cur.executemany(
                """
                INSERT INTO shop_orders (order_code, user_id, product_id, quantity, total_inr, status, payment_method)
                VALUES (%s, %s, %s, %s, %s, %s, %s) ON CONFLICT DO NOTHING
                """,
                order_rows,
            )

            # 4. Seed 300 Cloud Telemetry rows
            telemetry_rows = []
            for _ in range(300):
                page = random.choice(PAGES)
                srv = "prod-checkout-api-01" if "checkout" in page else "staging-api-server-01"
                cpu = round(random.uniform(28.0, 82.0), 2)
                telemetry_rows.append((srv, page, "pageview", cpu))
            cur.executemany(
                "INSERT INTO cloud_telemetry (server_name, page, action, cpu_percent) VALUES (%s, %s, %s, %s)",
                telemetry_rows,
            )

        conn.commit()
    print("Seed complete:", fetch_db_summary())


if __name__ == "__main__":
    seed()
