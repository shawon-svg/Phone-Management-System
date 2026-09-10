"""
database.py
Supabase PostgreSQL data layer for the Phone Stock & Sales Tracker.

This app is configured to use a shared Postgres database hosted on Supabase.
The connection string can be supplied directly, via the SUPABASE_DB_URL
environment variable, or from a local .env file in the project root.

Get the connection string from:
  Supabase Dashboard -> Project Settings -> Database -> Connection string (URI tab)
  postgresql://postgres:[YOUR-PASSWORD]@db.xxxxxxxx.supabase.co:5432/postgres
"""

import os
from datetime import date, datetime
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

try:
    import psycopg2
except ImportError as e:
    raise ImportError(
        "psycopg2 is required. Install with: pip install psycopg2-binary"
    ) from e

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass


def _normalize_db_url(db_url: str):
    if not db_url:
        return db_url

    candidate = db_url.strip()
    if "://" not in candidate:
        return candidate

    parsed = urlsplit(candidate)
    if parsed.scheme not in {"postgresql", "postgres"}:
        return candidate

    query = dict(parse_qsl(parsed.query, keep_blank_values=True))
    if "sslmode" not in query:
        query["sslmode"] = "require"

    return urlunsplit(
        (
            parsed.scheme,
            parsed.netloc,
            parsed.path,
            urlencode(query),
            parsed.fragment,
        )
    )


def _resolve_db_url(db_url: str = None):
    if db_url:
        return _normalize_db_url(db_url)

    env_url = os.environ.get("SUPABASE_DB_URL")
    if env_url:
        return _normalize_db_url(env_url)

    root_dir = os.path.dirname(os.path.abspath(__file__))
    env_file = os.path.join(root_dir, ".env")
    if os.path.exists(env_file):
        with open(env_file, "r", encoding="utf-8") as handle:
            for line in handle:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, value = [part.strip() for part in line.split("=", 1)]
                if key == "SUPABASE_DB_URL" and value:
                    return _normalize_db_url(value.strip("\"'"))

    return None


class Database:
    def __init__(self, db_url: str = None):
        self.db_url = _resolve_db_url(db_url)
        if not self.db_url:
            raise ValueError(
                "Supabase PostgreSQL is not configured. Create a .env file with "
                "SUPABASE_DB_URL=postgresql://... or export the environment variable "
                "before running the app."
            )
        self._init_db()

    # ------------------------------------------------------------------ #
    # Connection / schema
    # ------------------------------------------------------------------ #

    def _connect(self):
        return psycopg2.connect(self.db_url)

    def _init_db(self):
        conn = self._connect()
        try:
            with conn, conn.cursor() as cur:
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS inventory (
                        id          SERIAL PRIMARY KEY,
                        sl_no       TEXT UNIQUE,
                        imei        TEXT,
                        model       TEXT NOT NULL,
                        chipset     TEXT,
                        ram         TEXT,
                        storage     TEXT,
                        color       TEXT,
                        quantity    INTEGER NOT NULL DEFAULT 0,
                        cost_price  NUMERIC NOT NULL DEFAULT 0,
                        sell_price  NUMERIC NOT NULL DEFAULT 0,
                        created_at  TEXT
                    )
                """)
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS sales (
                        id          SERIAL PRIMARY KEY,
                        item_id     INTEGER,
                        sl_no       TEXT,
                        imei        TEXT,
                        model       TEXT,
                        chipset     TEXT,
                        ram         TEXT,
                        storage     TEXT,
                        color       TEXT,
                        quantity    INTEGER NOT NULL,
                        cost_price  NUMERIC NOT NULL,
                        sell_price  NUMERIC NOT NULL,
                        profit      NUMERIC NOT NULL,
                        sold_at     TEXT NOT NULL
                    )
                """)
                cur.execute(
                    "CREATE INDEX IF NOT EXISTS idx_inventory_search "
                    "ON inventory(model, chipset, ram, storage)")
                cur.execute(
                    "CREATE INDEX IF NOT EXISTS idx_sales_sold_at "
                    "ON sales(sold_at)")
        finally:
            conn.close()

    # ------------------------------------------------------------------ #
    # Inventory
    # ------------------------------------------------------------------ #

    def add_item(self, model, chipset, ram, storage, color, sl_no, imei, qty, cost, sell):
        created_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        conn = self._connect()
        try:
            with conn, conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO inventory
                        (sl_no, imei, model, chipset, ram, storage, color, quantity, cost_price, sell_price, created_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    RETURNING id
                """, (sl_no, imei, model, chipset, ram, storage, color, qty, cost, sell, created_at))
                return cur.fetchone()[0]
        finally:
            conn.close()

    def get_inventory(self, search: str = ""):
        query = "SELECT id, sl_no, imei, model, chipset, ram, storage, color, quantity, cost_price, sell_price FROM inventory"
        params = []
        search = (search or "").strip()
        if search:
            query += """ WHERE model ILIKE %s OR chipset ILIKE %s OR ram ILIKE %s OR storage ILIKE %s
                         OR sl_no ILIKE %s OR imei ILIKE %s OR color ILIKE %s"""
            like = f"%{search}%"
            params = [like] * 7
        query += " ORDER BY id DESC"
        conn = self._connect()
        try:
            with conn.cursor() as cur:
                cur.execute(query, params)
                return cur.fetchall()
        finally:
            conn.close()

    def get_item(self, item_id: int):
        conn = self._connect()
        try:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT id, sl_no, imei, model, chipset, ram, storage, color, quantity, cost_price, sell_price
                    FROM inventory WHERE id = %s
                """, (item_id,))
                return cur.fetchone()
        finally:
            conn.close()

    def update_quantity(self, item_id: int, quantity: int):
        conn = self._connect()
        try:
            with conn, conn.cursor() as cur:
                cur.execute(
                    "UPDATE inventory SET quantity = %s WHERE id = %s", (quantity, item_id))
        finally:
            conn.close()

    def delete_item(self, item_id: int) -> bool:
        conn = self._connect()
        try:
            with conn, conn.cursor() as cur:
                cur.execute(
                    "DELETE FROM inventory WHERE id = %s", (item_id,))
                return cur.rowcount > 0
        finally:
            conn.close()

    def sl_no_exists(self, sl_no: str) -> bool:
        if not sl_no:
            return False
        conn = self._connect()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT 1 FROM inventory WHERE sl_no = %s", (sl_no,))
                return cur.fetchone() is not None
        finally:
            conn.close()

    # ------------------------------------------------------------------ #
    # Sales
    # ------------------------------------------------------------------ #

    def record_sale(self, item_id, sl_no, imei, model, chipset, ram, storage, color, qty, cost, sell) -> float:
        profit = (sell - cost) * qty
        sold_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        conn = self._connect()
        try:
            with conn, conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO sales
                        (item_id, sl_no, imei, model, chipset, ram, storage, color, quantity, cost_price, sell_price, profit, sold_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """, (item_id, sl_no, imei, model, chipset, ram, storage, color, qty, cost, sell, profit, sold_at))
        finally:
            conn.close()
        return profit

    def get_sales(self, limit: int = None):
        query = """
            SELECT id, item_id, sl_no, imei, model, chipset, ram, storage, color,
                   quantity, cost_price, sell_price, profit, sold_at
            FROM sales ORDER BY id DESC
        """
        params = []
        if limit:
            query += " LIMIT %s"
            params.append(limit)
        conn = self._connect()
        try:
            with conn.cursor() as cur:
                cur.execute(query, params)
                return cur.fetchall()
        finally:
            conn.close()

    def get_today_summary(self):
        today = date.today().strftime("%Y-%m-%d")
        conn = self._connect()
        try:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT
                        COALESCE(SUM(quantity), 0)                    AS units_sold,
                        COALESCE(SUM(sell_price * quantity), 0)       AS total_revenue,
                        COALESCE(SUM(cost_price * quantity), 0)       AS total_cost,
                        COALESCE(SUM(profit), 0)                      AS total_profit
                    FROM sales WHERE sold_at LIKE %s
                """, (f"{today}%",))
                row = cur.fetchone()
        finally:
            conn.close()
        return {
            "date": date.today().strftime("%A, %d %B %Y"),
            "units_sold": row[0],
            "total_revenue": row[1],
            "total_cost": row[2],
            "total_profit": row[3],
        }

    def get_dashboard_stats(self):
        """Aggregate numbers used by the Dashboard KPI cards."""
        conn = self._connect()
        try:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT COALESCE(SUM(quantity), 0) AS total_units,
                           COALESCE(SUM(quantity * cost_price), 0) AS stock_value,
                           COUNT(*) AS distinct_models
                    FROM inventory
                """)
                inv_row = cur.fetchone()
                cur.execute("""
                    SELECT id, model, chipset, ram, storage, color, quantity
                    FROM inventory WHERE quantity <= 2 ORDER BY quantity ASC LIMIT 8
                """)
                low_stock = cur.fetchall()
        finally:
            conn.close()
        today = self.get_today_summary()
        return {
            "total_units": inv_row[0],
            "stock_value": inv_row[1],
            "distinct_models": inv_row[2],
            "low_stock": low_stock,
            "today_units_sold": today["units_sold"],
            "today_revenue": today["total_revenue"],
            "today_profit": today["total_profit"],
        }
