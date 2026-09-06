"""
database.py
SQLite data layer for the Phone Stock & Sales Tracker.

Kept fully independent of the UI so it can be tested on its own with
plain `python -c` / pytest, and so the storage location can be swapped
at runtime (see `switch_storage_folder`) without touching any UI code.
"""

import json
import shutil
import sqlite3
from datetime import date, datetime
from pathlib import Path

CONFIG_PATH = Path.home() / ".phonetrack_config.json"
DEFAULT_DB_DIR = Path.home() / "PhoneTrackerData"
DB_FILENAME = "phone_inventory.db"


def _load_configured_folder() -> Path:
    """Returns the last folder the user chose via `switch_storage_folder`,
    or the default app-data folder if none was ever chosen."""
    if CONFIG_PATH.exists():
        try:
            data = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
            folder = data.get("storage_folder")
            if folder and Path(folder).is_dir():
                return Path(folder)
        except (json.JSONDecodeError, OSError):
            pass
    return DEFAULT_DB_DIR


def _save_configured_folder(folder: Path) -> None:
    try:
        CONFIG_PATH.write_text(json.dumps({"storage_folder": str(folder)}), encoding="utf-8")
    except OSError:
        pass


class Database:
    def __init__(self, db_path: Path = None):
        if db_path is not None:
            self.db_path = Path(db_path)
        else:
            folder = _load_configured_folder()
            folder.mkdir(parents=True, exist_ok=True)
            self.db_path = folder / DB_FILENAME

        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    # ------------------------------------------------------------------ #
    # Connection / schema
    # ------------------------------------------------------------------ #

    def _connect(self):
        conn = sqlite3.connect(self.db_path)
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    def _init_db(self):
        with self._connect() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS inventory (
                    id          INTEGER PRIMARY KEY AUTOINCREMENT,
                    sl_no       TEXT UNIQUE,
                    imei        TEXT,
                    model       TEXT NOT NULL,
                    chipset     TEXT,
                    ram         TEXT,
                    storage     TEXT,
                    color       TEXT,
                    quantity    INTEGER NOT NULL DEFAULT 0,
                    cost_price  REAL NOT NULL DEFAULT 0,
                    sell_price  REAL NOT NULL DEFAULT 0,
                    created_at  TEXT
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS sales (
                    id          INTEGER PRIMARY KEY AUTOINCREMENT,
                    item_id     INTEGER,
                    sl_no       TEXT,
                    imei        TEXT,
                    model       TEXT,
                    chipset     TEXT,
                    ram         TEXT,
                    storage     TEXT,
                    color       TEXT,
                    quantity    INTEGER NOT NULL,
                    cost_price  REAL NOT NULL,
                    sell_price  REAL NOT NULL,
                    profit      REAL NOT NULL,
                    sold_at     TEXT NOT NULL
                )
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_inventory_search ON inventory(model, chipset, ram, storage)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_sales_sold_at ON sales(sold_at)")

    # ------------------------------------------------------------------ #
    # Inventory
    # ------------------------------------------------------------------ #

    def add_item(self, model, chipset, ram, storage, color, sl_no, imei, qty, cost, sell):
        created_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with self._connect() as conn:
            conn.execute("""
                INSERT INTO inventory
                    (sl_no, imei, model, chipset, ram, storage, color, quantity, cost_price, sell_price, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (sl_no, imei, model, chipset, ram, storage, color, qty, cost, sell, created_at))
            return conn.execute("SELECT last_insert_rowid()").fetchone()[0]

    def get_inventory(self, search: str = ""):
        query = "SELECT id, sl_no, imei, model, chipset, ram, storage, color, quantity, cost_price, sell_price FROM inventory"
        params = []
        search = (search or "").strip()
        if search:
            query += """ WHERE model LIKE ? OR chipset LIKE ? OR ram LIKE ? OR storage LIKE ?
                         OR sl_no LIKE ? OR imei LIKE ? OR color LIKE ?"""
            like = f"%{search}%"
            params = [like] * 7
        query += " ORDER BY id DESC"
        with self._connect() as conn:
            return conn.execute(query, params).fetchall()

    def get_item(self, item_id: int):
        with self._connect() as conn:
            row = conn.execute("""
                SELECT id, sl_no, imei, model, chipset, ram, storage, color, quantity, cost_price, sell_price
                FROM inventory WHERE id = ?
            """, (item_id,)).fetchone()
            return row

    def update_quantity(self, item_id: int, quantity: int):
        with self._connect() as conn:
            conn.execute("UPDATE inventory SET quantity = ? WHERE id = ?", (quantity, item_id))

    def delete_item(self, item_id: int) -> bool:
        with self._connect() as conn:
            cur = conn.execute("DELETE FROM inventory WHERE id = ?", (item_id,))
            return cur.rowcount > 0

    def sl_no_exists(self, sl_no: str) -> bool:
        if not sl_no:
            return False
        with self._connect() as conn:
            row = conn.execute("SELECT 1 FROM inventory WHERE sl_no = ?", (sl_no,)).fetchone()
            return row is not None

    # ------------------------------------------------------------------ #
    # Sales
    # ------------------------------------------------------------------ #

    def record_sale(self, item_id, sl_no, imei, model, chipset, ram, storage, color, qty, cost, sell) -> float:
        profit = (sell - cost) * qty
        sold_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with self._connect() as conn:
            conn.execute("""
                INSERT INTO sales
                    (item_id, sl_no, imei, model, chipset, ram, storage, color, quantity, cost_price, sell_price, profit, sold_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (item_id, sl_no, imei, model, chipset, ram, storage, color, qty, cost, sell, profit, sold_at))
        return profit

    def get_sales(self, limit: int = None):
        query = """
            SELECT id, item_id, sl_no, imei, model, chipset, ram, storage, color,
                   quantity, cost_price, sell_price, profit, sold_at
            FROM sales ORDER BY id DESC
        """
        params = []
        if limit:
            query += " LIMIT ?"
            params.append(limit)
        with self._connect() as conn:
            return conn.execute(query, params).fetchall()

    def get_today_summary(self):
        today = date.today().strftime("%Y-%m-%d")
        with self._connect() as conn:
            row = conn.execute("""
                SELECT
                    COALESCE(SUM(quantity), 0)                    AS units_sold,
                    COALESCE(SUM(sell_price * quantity), 0)       AS total_revenue,
                    COALESCE(SUM(cost_price * quantity), 0)       AS total_cost,
                    COALESCE(SUM(profit), 0)                      AS total_profit
                FROM sales WHERE sold_at LIKE ?
            """, (f"{today}%",)).fetchone()
        return {
            "date": date.today().strftime("%A, %d %B %Y"),
            "units_sold": row[0],
            "total_revenue": row[1],
            "total_cost": row[2],
            "total_profit": row[3],
        }

    def get_dashboard_stats(self):
        """Aggregate numbers used by the Dashboard KPI cards."""
        with self._connect() as conn:
            inv_row = conn.execute("""
                SELECT COALESCE(SUM(quantity), 0) AS total_units,
                       COALESCE(SUM(quantity * cost_price), 0) AS stock_value,
                       COUNT(*) AS distinct_models
                FROM inventory
            """).fetchone()
            low_stock = conn.execute("""
                SELECT id, model, chipset, ram, storage, color, quantity
                FROM inventory WHERE quantity <= 2 ORDER BY quantity ASC LIMIT 8
            """).fetchall()
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

    # ------------------------------------------------------------------ #
    # Storage location management
    # ------------------------------------------------------------------ #

    def switch_storage_folder(self, folder: str):
        new_folder = Path(folder)
        new_folder.mkdir(parents=True, exist_ok=True)
        new_path = new_folder / DB_FILENAME

        if new_path.resolve() != self.db_path.resolve():
            shutil.copyfile(self.db_path, new_path)

        self.db_path = new_path
        _save_configured_folder(new_folder)
        return self.db_path