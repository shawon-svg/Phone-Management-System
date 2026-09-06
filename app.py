import customtkinter as ctk
import os
import subprocess
import sys
from datetime import datetime
from tkinter import filedialog, ttk, messagebox

from database import Database

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

# --------------------------------------------------------------------- #
# Palette & Typography
# --------------------------------------------------------------------- #
COLOR_BG = "#141417"
COLOR_SIDEBAR = "#0f0f12"
COLOR_CARD = "#1c1c22"
COLOR_CARD_ALT = "#24242c"
COLOR_ACCENT = "#6366f1"
COLOR_ACCENT_HOVER = "#4f46e5"
COLOR_ACCENT_SOFT = "#312e81"
COLOR_TEXT = "#e5e7eb"
COLOR_TEXT_MUTED = "#9ca3af"
COLOR_GREEN = "#22c55e"
COLOR_GREEN_SOFT = "#14532d"
COLOR_RED = "#ef4444"
COLOR_RED_SOFT = "#450a0a"
COLOR_AMBER = "#f59e0b"
COLOR_AMBER_SOFT = "#451a03"
COLOR_BLUE = "#3b82f6"
COLOR_BORDER = "#2b2b33"
COLOR_ROW_ALT = "#1f1f26"

RAM_OPTIONS = ["4GB", "6GB", "8GB", "12GB", "16GB"]
STORAGE_OPTIONS = ["64GB", "128GB", "256GB", "512GB", "1TB"]

FONT_TITLE = ("Segoe UI", 20, "bold")
FONT_SUBTITLE = ("Segoe UI", 11)
FONT_LABEL = ("Segoe UI", 11)
FONT_LABEL_BOLD = ("Segoe UI", 11, "bold")
FONT_BUTTON = ("Segoe UI", 12, "bold")
FONT_KPI_VALUE = ("Segoe UI", 22, "bold")
FONT_KPI_LABEL = ("Segoe UI", 11)


def format_price(value):
    return f"{value:,.2f}"


def wrap_tree_text(value, max_chars=18):
    """Break long label text into multiple lines so it fits in a narrow Treeview cell."""
    text = str(value or "")
    if len(text) <= max_chars:
        return text

    words = text.split()
    if not words:
        return text

    lines = []
    current = ""
    for word in words:
        candidate = f"{current} {word}".strip()
        if len(candidate) <= max_chars:
            current = candidate
        else:
            if current:
                lines.append(current)
            if len(word) > max_chars:
                while len(word) > max_chars:
                    lines.append(word[:max_chars])
                    word = word[max_chars:]
                current = word
            else:
                current = word
    if current:
        lines.append(current)
    return "\n".join(lines)


def configure_treeview_style():
    """Makes ttk.Treeview match the dark, minimalist CustomTkinter theme."""
    style = ttk.Style()
    style.theme_use("clam")

    style.configure(
        "Custom.Treeview",
        background=COLOR_CARD,
        fieldbackground=COLOR_CARD,
        foreground=COLOR_TEXT,
        rowheight=34,
        borderwidth=0,
        font=FONT_LABEL,
    )
    style.map(
        "Custom.Treeview",
        background=[("selected", COLOR_ACCENT)],
        foreground=[("selected", "#ffffff")],
    )
    style.configure(
        "Custom.Treeview.Heading",
        background=COLOR_SIDEBAR,
        foreground=COLOR_TEXT,
        font=FONT_LABEL_BOLD,
        borderwidth=0,
        relief="flat",
    )
    style.map("Custom.Treeview.Heading", background=[
              ("active", "#17171c")])
    style.layout("Custom.Treeview", [
                 ("Custom.Treeview.treearea", {"sticky": "nswe"})])


def center_toplevel(win, master, width, height):
    """Centers a CTkToplevel over its parent window instead of the screen corner."""
    win.update_idletasks()
    px = master.winfo_rootx()
    py = master.winfo_rooty()
    pw = master.winfo_width()
    ph = master.winfo_height()
    x = px + (pw - width) // 2
    y = py + (ph - height) // 2
    win.geometry(f"{width}x{height}+{max(x, 0)}+{max(y, 0)}")


class SortableTreeview(ttk.Treeview):
    """A ttk.Treeview that sorts itself when a column header is clicked,
    and shows a ▲ / ▼ arrow on the active sort column."""

    def __init__(self, master, columns, headers, numeric_cols=(), **kwargs):
        super().__init__(master, columns=columns, show="headings", **kwargs)
        self._headers = headers
        self._numeric_cols = set(numeric_cols)
        self._sort_col = None
        self._sort_reverse = False

        for col, (label, width) in headers.items():
            self.heading(col, text=label, command=lambda c=col: self._sort_by(c))
            anchor = "center" if col in ("qty", "ram") else "w"
            self.column(col, width=width, anchor=anchor)

    def _sort_by(self, col):
        if self._sort_col == col:
            self._sort_reverse = not self._sort_reverse
        else:
            self._sort_col = col
            self._sort_reverse = False

        items = [(self.set(k, col), k) for k in self.get_children("")]

        def key(pair):
            raw = pair[0].replace(",", "").split("\n")[0]
            if col in self._numeric_cols:
                try:
                    return float(raw)
                except ValueError:
                    return 0.0
            return raw.lower()

        items.sort(key=key, reverse=self._sort_reverse)
        for index, (_, k) in enumerate(items):
            self.move(k, "", index)

        for col_id, (label, _width) in self._headers.items():
            arrow = ""
            if col_id == self._sort_col:
                arrow = " ▼" if self._sort_reverse else " ▲"
            self.heading(col_id, text=f"{label}{arrow}")


class ToastManager:
    """Small, non-blocking notification banners that slide in bottom-right
    and auto-dismiss, so routine confirmations don't interrupt the flow
    with a modal messagebox."""

    def __init__(self, root):
        self.root = root
        self._toasts = []

    def show(self, message, kind="success"):
        colors = {
            "success": (COLOR_GREEN_SOFT, COLOR_GREEN, "✓"),
            "error": (COLOR_RED_SOFT, COLOR_RED, "✕"),
            "info": (COLOR_ACCENT_SOFT, COLOR_ACCENT, "ℹ"),
        }
        bg, fg, icon = colors.get(kind, colors["success"])

        toast = ctk.CTkFrame(self.root, fg_color=bg, corner_radius=10,
                              border_width=1, border_color=fg)
        label = ctk.CTkLabel(
            toast, text=f"{icon}  {message}", font=FONT_LABEL_BOLD,
            text_color=fg, wraplength=300, justify="left",
        )
        label.pack(padx=16, pady=12)

        self.root.update_idletasks()
        self._reposition(toast)
        self._toasts.append(toast)
        self.root.after(2600, lambda: self._dismiss(toast))

    def _reposition(self, new_toast):
        base_y = self.root.winfo_height() - 30
        for toast in reversed(self._toasts):
            if not toast.winfo_exists():
                continue
            base_y -= toast.winfo_reqheight() + 10
        new_toast.place(
            in_=self.root,
            relx=1.0, x=-24, y=base_y, anchor="sw",
        )

    def _dismiss(self, toast):
        if toast.winfo_exists():
            toast.destroy()
        self._toasts = [t for t in self._toasts if t.winfo_exists()]
        for t in self._toasts:
            pass


def page_header(parent, title, subtitle, row=0):
    """Consistent, properly-aligned title block used at the top of every
    page: bold title flush left, muted subtitle flush left directly under
    it. Returns the header frame so callers can grid extra widgets
    (e.g. a search box or action buttons) into its right side."""
    header = ctk.CTkFrame(parent, fg_color="transparent")
    header.grid(row=row, column=0, sticky="ew", pady=(0, 18))
    header.grid_columnconfigure(0, weight=1)

    text_col = ctk.CTkFrame(header, fg_color="transparent")
    text_col.grid(row=0, column=0, sticky="w")
    ctk.CTkLabel(text_col, text=title, font=FONT_TITLE, anchor="w",
                 justify="left").pack(anchor="w")
    if subtitle:
        ctk.CTkLabel(text_col, text=subtitle, font=FONT_SUBTITLE,
                     text_color=COLOR_TEXT_MUTED, anchor="w",
                     justify="left").pack(anchor="w", pady=(2, 0))

    return header


def kpi_card(parent, icon, label, value, color=COLOR_TEXT, bg=COLOR_CARD):
    card = ctk.CTkFrame(parent, fg_color=bg, corner_radius=14,
                         border_width=1, border_color=COLOR_BORDER)
    inner = ctk.CTkFrame(card, fg_color="transparent")
    inner.pack(fill="both", expand=True, padx=18, pady=16)

    top = ctk.CTkFrame(inner, fg_color="transparent")
    top.pack(fill="x")
    ctk.CTkLabel(top, text=icon, font=("Segoe UI", 16)).pack(side="left")
    ctk.CTkLabel(top, text=label, font=FONT_KPI_LABEL,
                 text_color=COLOR_TEXT_MUTED).pack(side="left", padx=(8, 0))

    value_label = ctk.CTkLabel(inner, text=value, font=FONT_KPI_VALUE, text_color=color)
    value_label.pack(anchor="w", pady=(10, 0))
    card.value_label = value_label
    return card


# --------------------------------------------------------------------- #
# Dashboard (Overview) Frame
# --------------------------------------------------------------------- #
class DashboardFrame(ctk.CTkFrame):
    def __init__(self, master, db: Database, on_navigate=None):
        super().__init__(master, fg_color="transparent")
        self.db = db
        self.on_navigate = on_navigate
        self._build()
        self.refresh()

    def _build(self):
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(2, weight=1)

        page_header(self, "Overview", "Today's snapshot of your shop", row=0)

        kpi_row = ctk.CTkFrame(self, fg_color="transparent")
        kpi_row.grid(row=1, column=0, sticky="ew", pady=(0, 18))
        for i in range(4):
            kpi_row.grid_columnconfigure(i, weight=1, uniform="kpi")

        self.card_units = kpi_card(kpi_row, "📦", "Units in Stock", "0")
        self.card_units.grid(row=0, column=0, sticky="nsew", padx=(0, 10))
        self.card_value = kpi_card(kpi_row, "💰", "Stock Value", "0.00")
        self.card_value.grid(row=0, column=1, sticky="nsew", padx=10)
        self.card_today_units = kpi_card(kpi_row, "🧾", "Sold Today", "0")
        self.card_today_units.grid(row=0, column=2, sticky="nsew", padx=10)
        self.card_today_profit = kpi_card(kpi_row, "📈", "Profit Today", "0.00",
                                           color=COLOR_GREEN)
        self.card_today_profit.grid(row=0, column=3, sticky="nsew", padx=(10, 0))

        bottom = ctk.CTkFrame(self, fg_color="transparent")
        bottom.grid(row=2, column=0, sticky="nsew")
        bottom.grid_columnconfigure(0, weight=1)
        bottom.grid_columnconfigure(1, weight=1)
        bottom.grid_rowconfigure(0, weight=1)

        # Low stock panel
        low_card = ctk.CTkFrame(bottom, fg_color=COLOR_CARD, corner_radius=14,
                                 border_width=1, border_color=COLOR_BORDER)
        low_card.grid(row=0, column=0, sticky="nsew", padx=(0, 10))
        low_card.grid_columnconfigure(0, weight=1)
        low_card.grid_rowconfigure(1, weight=1)

        low_header = ctk.CTkFrame(low_card, fg_color="transparent")
        low_header.grid(row=0, column=0, sticky="ew", padx=18, pady=(16, 6))
        low_header.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(low_header, text="⚠  Low Stock (≤ 2 units)",
                     font=FONT_LABEL_BOLD).grid(row=0, column=0, sticky="w")
        ctk.CTkButton(low_header, text="Restock →", width=90, height=28,
                      fg_color="transparent", border_width=1, border_color=COLOR_AMBER,
                      text_color=COLOR_AMBER, hover_color=COLOR_AMBER_SOFT,
                      command=lambda: self.on_navigate and self.on_navigate("inventory"),
                      ).grid(row=0, column=1, sticky="e")

        self.low_stock_list = ctk.CTkScrollableFrame(low_card, fg_color="transparent")
        self.low_stock_list.grid(row=1, column=0, sticky="nsew", padx=10, pady=(0, 14))
        self.low_stock_list.grid_columnconfigure(0, weight=1)

        # Recent sales panel
        recent_card = ctk.CTkFrame(bottom, fg_color=COLOR_CARD, corner_radius=14,
                                    border_width=1, border_color=COLOR_BORDER)
        recent_card.grid(row=0, column=1, sticky="nsew", padx=(10, 0))
        recent_card.grid_columnconfigure(0, weight=1)
        recent_card.grid_rowconfigure(1, weight=1)

        recent_header = ctk.CTkFrame(recent_card, fg_color="transparent")
        recent_header.grid(row=0, column=0, sticky="ew", padx=18, pady=(16, 6))
        recent_header.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(recent_header, text="🕒  Recent Sales",
                     font=FONT_LABEL_BOLD).grid(row=0, column=0, sticky="w")
        ctk.CTkButton(recent_header, text="View All →", width=90, height=28,
                      fg_color="transparent", border_width=1, border_color=COLOR_ACCENT,
                      text_color=COLOR_ACCENT, hover_color=COLOR_ACCENT_SOFT,
                      command=lambda: self.on_navigate and self.on_navigate("history"),
                      ).grid(row=0, column=1, sticky="e")

        self.recent_sales_list = ctk.CTkScrollableFrame(recent_card, fg_color="transparent")
        self.recent_sales_list.grid(row=1, column=0, sticky="nsew", padx=10, pady=(0, 14))
        self.recent_sales_list.grid_columnconfigure(0, weight=1)

    def _clear(self, container):
        for child in container.winfo_children():
            child.destroy()

    def refresh(self):
        stats = self.db.get_dashboard_stats()

        self.card_units.value_label.configure(text=str(stats["total_units"]))
        self.card_value.value_label.configure(text=format_price(stats["stock_value"]))
        self.card_today_units.value_label.configure(text=str(stats["today_units_sold"]))
        profit = stats["today_profit"]
        self.card_today_profit.value_label.configure(
            text=format_price(profit),
            text_color=COLOR_GREEN if profit >= 0 else COLOR_RED,
        )

        self._clear(self.low_stock_list)
        if not stats["low_stock"]:
            ctk.CTkLabel(self.low_stock_list, text="All stock levels look healthy 🎉",
                         font=FONT_LABEL, text_color=COLOR_TEXT_MUTED).grid(
                row=0, column=0, sticky="w", pady=10)
        else:
            for i, (item_id, model, chipset, ram, storage, color, qty) in enumerate(stats["low_stock"]):
                row = ctk.CTkFrame(self.low_stock_list, fg_color=COLOR_CARD_ALT, corner_radius=8)
                row.grid(row=i, column=0, sticky="ew", pady=4)
                row.grid_columnconfigure(0, weight=1)
                ctk.CTkLabel(row, text=f"{model}", font=FONT_LABEL_BOLD).grid(
                    row=0, column=0, sticky="w", padx=12, pady=(8, 0))
                ctk.CTkLabel(row, text=f"{ram} · {storage} · {color}", font=("Segoe UI", 10),
                             text_color=COLOR_TEXT_MUTED).grid(row=1, column=0, sticky="w", padx=12, pady=(0, 8))
                badge_color = COLOR_RED if qty == 0 else COLOR_AMBER
                ctk.CTkLabel(row, text=f"{qty} left", font=FONT_LABEL_BOLD,
                             text_color=badge_color).grid(row=0, column=1, rowspan=2, padx=12)

        self._clear(self.recent_sales_list)
        recent = self.db.get_sales(limit=6)
        if not recent:
            ctk.CTkLabel(self.recent_sales_list, text="No sales recorded yet.",
                         font=FONT_LABEL, text_color=COLOR_TEXT_MUTED).grid(
                row=0, column=0, sticky="w", pady=10)
        else:
            for i, sale in enumerate(recent):
                (_id, _item_id, sl_no, imei, model, chipset, ram, storage,
                 color, qty, cost, sell, profit, sold_at) = sale
                row = ctk.CTkFrame(self.recent_sales_list, fg_color=COLOR_CARD_ALT, corner_radius=8)
                row.grid(row=i, column=0, sticky="ew", pady=4)
                row.grid_columnconfigure(0, weight=1)
                ctk.CTkLabel(row, text=f"{model}  ×{qty}", font=FONT_LABEL_BOLD).grid(
                    row=0, column=0, sticky="w", padx=12, pady=(8, 0))
                ctk.CTkLabel(row, text=sold_at, font=("Segoe UI", 10),
                             text_color=COLOR_TEXT_MUTED).grid(row=1, column=0, sticky="w", padx=12, pady=(0, 8))
                profit_color = COLOR_GREEN if profit >= 0 else COLOR_RED
                ctk.CTkLabel(row, text=f"+{format_price(profit)}", font=FONT_LABEL_BOLD,
                             text_color=profit_color).grid(row=0, column=1, rowspan=2, padx=12)


# --------------------------------------------------------------------- #
# Inventory (Stocking) Frame
# --------------------------------------------------------------------- #
class InventoryFrame(ctk.CTkFrame):
    def __init__(self, master, db: Database, on_change=None, toast=None):
        super().__init__(master, fg_color="transparent")
        self.db = db
        self.on_change = on_change
        self.toast = toast
        self._search_job = None
        self._build()
        self.refresh()

    def _build(self):
        self.grid_columnconfigure(0, weight=2)
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(1, weight=1)

        page_header(self, "Stock Management", "Add new phones and manage what's on the shelf", row=0)

        form = ctk.CTkScrollableFrame(
            self,
            fg_color=COLOR_CARD,
            corner_radius=14,
            border_width=1,
            border_color=COLOR_BORDER,
            width=340,
        )
        form.grid(row=1, column=1, sticky="nsew", padx=(0, 18))
        form.grid_columnconfigure(0, weight=1, minsize=300)

        ctk.CTkLabel(form, text="Add New Stock", font=FONT_LABEL_BOLD).grid(
            row=0, column=0, sticky="w", padx=20, pady=(20, 2)
        )
        ctk.CTkLabel(
            form, text="Register a new phone variant", font=FONT_SUBTITLE, text_color=COLOR_TEXT_MUTED
        ).grid(row=1, column=0, sticky="w", padx=20, pady=(0, 16))

        self.sl_no_entry = self._labeled_entry(
            form, "SL No.", 2, placeholder="e.g. SL-1001")
        self.imei_entry = self._labeled_entry(
            form, "IMEI Number", 4, placeholder="e.g. 123456789012345")
        self.model_entry = self._labeled_entry(
            form, "Brand / Model", 6, placeholder="e.g. Samsung Galaxy S24")
        self.chipset_entry = self._labeled_entry(
            form, "Chipset", 8, placeholder="e.g. Snapdragon 8 Gen 3")
        self.ram_combo = self._labeled_combo(
            form, "RAM Configuration", 10, RAM_OPTIONS)
        self.storage_combo = self._labeled_combo(
            form, "Storage Configuration", 12, STORAGE_OPTIONS)
        self.color_entry = self._labeled_entry(
            form, "Color Variant", 14, placeholder="e.g. Midnight Black")
        self.qty_entry = self._labeled_entry(
            form, "Quantity", 16, placeholder="e.g. 10")
        self.qty_entry.insert(0, "1")
        self.cost_entry = self._labeled_entry(
            form, "Retail / Cost Price", 18, placeholder="0.00")
        self.cost_entry.insert(0, "0.00")
        self.sell_entry = self._labeled_entry(
            form, "Selling Price", 20, placeholder="0.00")
        self.sell_entry.insert(0, "0.00")

        self.cost_entry.bind("<KeyRelease>", self._update_profit_preview)
        self.sell_entry.bind("<KeyRelease>", self._update_profit_preview)

        # Enter-to-advance so a user can Tab through the whole form with
        # just the keyboard and hit Enter on the last field to submit.
        form_fields = [
            self.sl_no_entry, self.imei_entry, self.model_entry, self.chipset_entry,
            self.color_entry, self.qty_entry, self.cost_entry, self.sell_entry,
        ]
        for i, field in enumerate(form_fields):
            if i + 1 < len(form_fields):
                nxt = form_fields[i + 1]
                field.bind("<Return>", lambda e, n=nxt: (n.focus_set(), "break"))
            else:
                field.bind("<Return>", lambda e: (self._add_item(), "break"))

        profit_card = ctk.CTkFrame(
            form, fg_color=COLOR_CARD_ALT, corner_radius=10)
        profit_card.grid(row=22, column=0, sticky="ew", padx=20, pady=(4, 16))
        ctk.CTkLabel(
            profit_card, text="Projected Profit / Unit", font=FONT_LABEL, text_color=COLOR_TEXT_MUTED
        ).pack(anchor="w", padx=14, pady=(10, 0))
        self.profit_label = ctk.CTkLabel(
            profit_card, text="0.00", font=("Segoe UI", 20, "bold"), text_color=COLOR_GREEN
        )
        self.profit_label.pack(anchor="w", padx=14, pady=(0, 10))

        self.add_button = ctk.CTkButton(
            form,
            text="+  Add to Inventory",
            font=FONT_BUTTON,
            height=42,
            fg_color=COLOR_ACCENT,
            hover_color=COLOR_ACCENT_HOVER,
            corner_radius=10,
            command=self._add_item,
        )
        self.add_button.grid(row=23, column=0, sticky="ew", padx=20, pady=(0, 20))

        table_card = ctk.CTkFrame(
            self,
            fg_color=COLOR_CARD,
            corner_radius=14,
            border_width=1,
            border_color=COLOR_BORDER,
        )
        table_card.grid(row=1, column=0, sticky="nsew")
        table_card.grid_columnconfigure(0, weight=1)
        table_card.grid_rowconfigure(1, weight=1)

        header = ctk.CTkFrame(table_card, fg_color="transparent")
        header.grid(row=0, column=0, columnspan=2,
                    sticky="ew", padx=20, pady=(20, 10))
        header.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(header, text="Current Stock", font=FONT_LABEL_BOLD).grid(
            row=0, column=0, sticky="w")

        search_wrap = ctk.CTkFrame(header, fg_color=COLOR_CARD_ALT, corner_radius=8)
        search_wrap.grid(row=0, column=1, padx=12)
        self.search_entry = ctk.CTkEntry(
            search_wrap, placeholder_text="🔍  Search model, chipset, RAM, storage, SL, IMEI...",
            width=260, height=34, fg_color="transparent", border_width=0,
        )
        self.search_entry.pack(side="left", padx=(10, 0), pady=2)
        ctk.CTkButton(
            search_wrap, text="✕", width=28, height=28, fg_color="transparent",
            hover_color=COLOR_BORDER, text_color=COLOR_TEXT_MUTED,
            command=self._clear_search,
        ).pack(side="left", padx=(2, 4))
        self.search_entry.bind("<KeyRelease>", self._on_search_change)
        self.search_entry.bind("<Control-a>", lambda e: None)

        self.count_label = ctk.CTkLabel(header, text="", font=FONT_LABEL, text_color=COLOR_TEXT_MUTED)
        self.count_label.grid(row=0, column=2, padx=(0, 12))

        btns = ctk.CTkFrame(header, fg_color="transparent")
        btns.grid(row=0, column=3, sticky="e")
        ctk.CTkButton(
            btns, text="⟳  Refresh", width=100, fg_color=COLOR_CARD_ALT, hover_color=COLOR_BORDER,
            command=self.refresh,
        ).pack(side="left", padx=(0, 8))
        self.delete_btn = ctk.CTkButton(
            btns,
            text="🗑  Delete Selected",
            width=150,
            fg_color="transparent",
            border_width=1,
            border_color=COLOR_RED,
            hover_color=COLOR_RED_SOFT,
            text_color=COLOR_RED,
            state="disabled",
            command=self._delete_selected,
        )
        self.delete_btn.pack(side="left", padx=(0, 8))
        ctk.CTkButton(
            btns, text="⚙  Storage", width=100, fg_color=COLOR_CARD_ALT, hover_color=COLOR_BORDER,
            command=self._show_storage,
        ).pack(side="left")

        columns = ("sl_no", "imei", "model", "chipset", "ram", "storage",
                   "color", "qty", "cost", "sell", "profit")
        headers = {
            "sl_no": ("SL No.", 90),
            "imei": ("IMEI", 130),
            "model": ("Model", 145),
            "chipset": ("Chipset", 120),
            "ram": ("RAM", 60),
            "storage": ("Storage", 75),
            "color": ("Color", 110),
            "qty": ("Stock", 60),
            "cost": ("Cost Price", 82),
            "sell": ("Selling Price", 90),
            "profit": ("Profit/Unit", 90),
        }
        self.tree = SortableTreeview(
            table_card, columns, headers,
            numeric_cols=("qty", "cost", "sell", "profit"),
            style="Custom.Treeview",
        )
        self.tree.tag_configure("oddrow", background=COLOR_CARD)
        self.tree.tag_configure("evenrow", background=COLOR_ROW_ALT)
        self.tree.tag_configure("lowstock", foreground=COLOR_AMBER)
        self.tree.tag_configure("outofstock", foreground=COLOR_RED)
        self.tree.grid(row=1, column=0, sticky="nsew",
                       padx=(20, 0), pady=(0, 20))
        self.tree.bind("<<TreeviewSelect>>", self._on_tree_select)
        self.tree.bind("<Double-1>", lambda e: self._delete_selected() if self.tree.selection() else None)
        self.tree.bind("<Delete>", lambda e: self._delete_selected())

        scrollbar = ttk.Scrollbar(
            table_card, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)
        scrollbar.grid(row=1, column=1, sticky="ns",
                       padx=(0, 20), pady=(0, 20))
        horizontal = ttk.Scrollbar(
            table_card, orient="horizontal", command=self.tree.xview)
        self.tree.configure(xscrollcommand=horizontal.set)
        horizontal.grid(row=2, column=0, sticky="ew",
                        padx=(20, 0), pady=(0, 12))

    def _labeled_entry(self, parent, label, row, placeholder=""):
        ctk.CTkLabel(parent, text=label, font=FONT_LABEL, text_color=COLOR_TEXT_MUTED).grid(
            row=row, column=0, sticky="w", padx=20, pady=(0, 4)
        )
        entry = ctk.CTkEntry(
            parent, placeholder_text=placeholder, height=36, corner_radius=8,
            fg_color=COLOR_CARD_ALT, border_color=COLOR_BORDER, border_width=1,
        )
        entry.grid(row=row + 1, column=0, sticky="ew", padx=20, pady=(0, 8))
        return entry

    def _labeled_combo(self, parent, label, row, values):
        ctk.CTkLabel(parent, text=label, font=FONT_LABEL, text_color=COLOR_TEXT_MUTED).grid(
            row=row, column=0, sticky="w", padx=20, pady=(0, 4)
        )
        combo = ctk.CTkComboBox(
            parent, values=values, height=36, corner_radius=8,
            fg_color=COLOR_CARD_ALT, border_color=COLOR_BORDER,
            button_color=COLOR_ACCENT, button_hover_color=COLOR_ACCENT_HOVER,
        )
        combo.set(values[0])
        combo.grid(row=row + 1, column=0, sticky="ew", padx=20, pady=(0, 8))
        return combo

    def _flash_invalid(self, entry):
        entry.configure(border_color=COLOR_RED)
        self.after(1200, lambda: entry.configure(border_color=COLOR_BORDER))

    def _update_profit_preview(self, event=None):
        cost = self._safe_float(self.cost_entry.get())
        sell = self._safe_float(self.sell_entry.get())
        profit = sell - cost
        self.profit_label.configure(
            text=format_price(profit), text_color=COLOR_GREEN if profit >= 0 else COLOR_RED
        )

    @staticmethod
    def _safe_float(value):
        try:
            return float(value)
        except (ValueError, TypeError):
            return 0.0

    def _add_item(self):
        sl_no = self.sl_no_entry.get().strip()
        imei = self.imei_entry.get().strip()
        model = self.model_entry.get().strip()
        chipset = self.chipset_entry.get().strip()
        ram = self.ram_combo.get().strip()
        storage = self.storage_combo.get().strip()
        color = self.color_entry.get().strip()
        qty_raw = (self.qty_entry.get().strip() or "1")
        cost_raw = (self.cost_entry.get().strip() or "0.00")
        sell_raw = (self.sell_entry.get().strip() or "0.00")

        required = [
            (sl_no, self.sl_no_entry), (imei, self.imei_entry), (model, self.model_entry),
            (chipset, self.chipset_entry), (ram, self.ram_combo), (storage, self.storage_combo),
            (color, self.color_entry),
        ]
        missing = [entry for value, entry in required if not value]
        if missing:
            for entry in missing:
                self._flash_invalid(entry)
            if self.toast:
                self.toast.show("Please fill in all required fields.", "error")
            else:
                messagebox.showwarning(
                    "Missing Info", "Please fill in SL No., IMEI Number, Brand / Model, Chipset, RAM, Storage, and Color.")
            return

        if self.db.sl_no_exists(sl_no):
            self._flash_invalid(self.sl_no_entry)
            if self.toast:
                self.toast.show(f"SL No. '{sl_no}' already exists.", "error")
            else:
                messagebox.showwarning("Duplicate SL No.", f"'{sl_no}' is already in use.")
            return

        try:
            qty = int(qty_raw)
            cost = float(cost_raw)
            sell = float(sell_raw)
            if qty <= 0 or cost < 0 or sell < 0:
                raise ValueError
        except ValueError:
            if self.toast:
                self.toast.show("Quantity must be whole; prices must be valid numbers.", "error")
            else:
                messagebox.showwarning(
                    "Invalid Input", "Quantity must be a whole number and prices must be valid numbers."
                )
            return

        self.db.add_item(model, chipset, ram, storage,
                         color, sl_no, imei, qty, cost, sell)
        for entry in (self.sl_no_entry, self.imei_entry, self.model_entry, self.chipset_entry, self.color_entry, self.qty_entry, self.cost_entry, self.sell_entry):
            entry.delete(0, "end")
        self.qty_entry.insert(0, "1")
        self.cost_entry.insert(0, "0.00")
        self.sell_entry.insert(0, "0.00")
        self._update_profit_preview()
        self.refresh()
        self.sl_no_entry.focus_set()
        if self.toast:
            self.toast.show(f"{model} added to inventory.", "success")
        if self.on_change:
            self.on_change()

    def _on_tree_select(self, event=None):
        self.delete_btn.configure(state="normal" if self.tree.selection() else "disabled")

    def _delete_selected(self):
        selected = self.tree.selection()
        if not selected:
            if self.toast:
                self.toast.show("Select an inventory row to delete first.", "info")
            else:
                messagebox.showinfo("No Selection", "Select an inventory row to delete.")
            return
        try:
            item_id = int(selected[0])
        except (TypeError, ValueError):
            messagebox.showerror(
                "Delete Error", "The selected stock row is invalid.")
            return
        if messagebox.askyesno("Confirm Delete", "Remove this item from inventory?"):
            deleted = self.db.delete_item(item_id)
            if not deleted:
                messagebox.showerror(
                    "Delete Error", "This stock item no longer exists.")
                self.refresh()
                return
            if self.toast:
                self.toast.show("Item removed from inventory.", "info")
            if self.on_change:
                self.on_change()
            else:
                self.refresh()

    def _clear_search(self):
        self.search_entry.delete(0, "end")
        self.refresh()

    def _on_search_change(self, event=None):
        if self._search_job is not None:
            self.after_cancel(self._search_job)
        self._search_job = self.after(220, self.refresh)

    def _show_storage(self):
        storage = ctk.CTkToplevel(self)
        storage.title("Storage")
        storage.configure(fg_color=COLOR_BG)
        storage.resizable(False, False)
        storage.transient(self.winfo_toplevel())
        center_toplevel(storage, self.winfo_toplevel(), 520, 340)

        ctk.CTkLabel(storage, text="Storage",
                     font=FONT_TITLE).pack(pady=(24, 8))
        ctk.CTkLabel(
            storage, text=f"Database file:\n{self.db.db_path}",
            font=FONT_LABEL, text_color=COLOR_TEXT_MUTED, justify="left", wraplength=470,
        ).pack(anchor="w", padx=24, pady=(0, 12))
        ctk.CTkLabel(
            storage,
            text=f"Stock records: {len(self.db.get_inventory())}    Sold records: {len(self.db.get_sales())}",
            font=FONT_LABEL,
        ).pack(anchor="w", padx=24, pady=(0, 18))

        def open_folder():
            folder = str(self.db.db_path.parent)
            if sys.platform == "darwin":
                subprocess.run(["open", folder], check=False)
            elif os.name == "nt":
                os.startfile(folder)
            else:
                subprocess.run(["xdg-open", folder], check=False)

        ctk.CTkButton(
            storage, text="Open Storage Folder", fg_color=COLOR_ACCENT,
            hover_color=COLOR_ACCENT_HOVER, command=open_folder,
        ).pack(fill="x", padx=24, pady=(0, 10))

        def choose_folder():
            folder = filedialog.askdirectory(title="Choose Storage Folder")
            if not folder:
                return
            target = os.path.join(folder, "phone_inventory.db")
            if os.path.exists(target) and not messagebox.askyesno(
                    "Replace Database?",
                    "A phone_inventory.db already exists there. Replace it with the current database?"):
                return
            try:
                self.db.switch_storage_folder(folder)
            except OSError as error:
                messagebox.showerror(
                    "Storage Error", f"Could not change storage:\n{error}")
                return
            storage.destroy()
            self._show_storage()
            if self.on_change:
                self.on_change()

        ctk.CTkButton(
            storage, text="Choose Storage Folder", fg_color=COLOR_CARD_ALT,
            hover_color=COLOR_BORDER, command=choose_folder,
        ).pack(fill="x", padx=24, pady=(0, 10))
        ctk.CTkButton(
            storage, text="Close", fg_color=COLOR_CARD_ALT,
            hover_color=COLOR_BORDER, command=storage.destroy,
        ).pack(fill="x", padx=24)

    def refresh(self):
        selected_before = self.tree.selection()
        for row in self.tree.get_children():
            self.tree.delete(row)
        rows = self.db.get_inventory(self.search_entry.get())
        for i, (item_id, sl_no, imei, model, chipset, ram, storage, color, qty, cost, sell) in enumerate(rows):
            profit = sell - cost
            tags = ["evenrow" if i % 2 else "oddrow"]
            if qty == 0:
                tags.append("outofstock")
            elif qty <= 2:
                tags.append("lowstock")
            self.tree.insert(
                "", "end", iid=str(item_id), tags=tuple(tags),
                values=(
                    wrap_tree_text(sl_no or "-"),
                    wrap_tree_text(imei or "-"),
                    wrap_tree_text(model),
                    wrap_tree_text(chipset),
                    ram,
                    storage,
                    color,
                    qty,
                    format_price(cost),
                    format_price(sell),
                    format_price(profit),
                ),
            )
        if selected_before and str(selected_before[0]) in self.tree.get_children():
            self.tree.selection_set(selected_before[0])
        self._on_tree_select()
        self.count_label.configure(text=f"{len(rows)} item(s)")


# --------------------------------------------------------------------- #
# Checkout Frame
# --------------------------------------------------------------------- #
class POSFrame(ctk.CTkFrame):
    def __init__(self, master, db: Database, on_change=None, toast=None):
        super().__init__(master, fg_color="transparent")
        self.db = db
        self.on_change = on_change
        self.toast = toast
        self.selected_item = None
        self._refreshing = False
        self._search_job = None
        self._build()
        self.refresh()

    def _build(self):
        self.grid_columnconfigure(0, weight=2)
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(1, weight=1)

        page_header(self, "Checkout", "Pick an item from stock and complete the sale", row=0)

        table_card = ctk.CTkFrame(
            self, fg_color=COLOR_CARD, corner_radius=14, border_width=1, border_color=COLOR_BORDER
        )
        table_card.grid(row=1, column=0, sticky="nsew", padx=(0, 16))
        table_card.grid_columnconfigure(0, weight=1)
        table_card.grid_rowconfigure(1, weight=1)

        header = ctk.CTkFrame(table_card, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew", padx=20, pady=(20, 10))
        header.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(header, text="Select Stock to Sell", font=FONT_LABEL_BOLD).grid(
            row=0, column=0, sticky="w")

        search_wrap = ctk.CTkFrame(header, fg_color=COLOR_CARD_ALT, corner_radius=8)
        search_wrap.grid(row=0, column=1, sticky="e")
        self.search_entry = ctk.CTkEntry(
            search_wrap, placeholder_text="🔍  Search model, chipset, RAM, or storage",
            height=34, width=260, fg_color="transparent", border_width=0)
        self.search_entry.pack(side="left", padx=(10, 0), pady=2)
        ctk.CTkButton(
            search_wrap, text="✕", width=28, height=28, fg_color="transparent",
            hover_color=COLOR_BORDER, text_color=COLOR_TEXT_MUTED,
            command=self._clear_search,
        ).pack(side="left", padx=(2, 4))
        self.search_entry.bind("<KeyRelease>", self._on_search_change)

        columns = ("sl_no", "imei", "model", "chipset", "ram",
                   "storage", "color", "qty", "sell")
        headers = {
            "sl_no": ("SL No.", 90),
            "imei": ("IMEI", 120),
            "model": ("Model", 170),
            "chipset": ("Chipset", 150),
            "ram": ("RAM", 70),
            "storage": ("Storage", 85),
            "color": ("Color", 130),
            "qty": ("In Stock", 90),
            "sell": ("Selling Price", 110),
        }
        self.tree = SortableTreeview(
            table_card, columns, headers,
            numeric_cols=("qty", "sell"), style="Custom.Treeview",
        )
        self.tree.tag_configure("oddrow", background=COLOR_CARD)
        self.tree.tag_configure("evenrow", background=COLOR_ROW_ALT)
        self.tree.grid(row=1, column=0, sticky="nsew",
                       padx=(20, 0), pady=(0, 20))
        self.tree.bind("<<TreeviewSelect>>", self._on_select)
        self.tree.bind("<Double-1>", lambda e: self.qty_entry.focus_set())

        scrollbar = ttk.Scrollbar(
            table_card, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)
        scrollbar.grid(row=1, column=1, sticky="ns",
                       padx=(0, 20), pady=(0, 20))
        horizontal = ttk.Scrollbar(
            table_card, orient="horizontal", command=self.tree.xview)
        self.tree.configure(xscrollcommand=horizontal.set)
        horizontal.grid(row=2, column=0, sticky="ew",
                        padx=(20, 0), pady=(0, 12))

        checkout = ctk.CTkFrame(
            self, fg_color=COLOR_CARD, corner_radius=14, border_width=1, border_color=COLOR_BORDER
        )
        checkout.grid(row=1, column=1, sticky="nsew")
        checkout.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(checkout, text="Order Summary", font=FONT_LABEL_BOLD).grid(
            row=0, column=0, sticky="w", padx=20, pady=(20, 16)
        )

        info_frame = ctk.CTkFrame(
            checkout, fg_color=COLOR_CARD_ALT, corner_radius=10)
        info_frame.grid(row=1, column=0, sticky="ew", padx=20, pady=(0, 16))
        self.info_label = ctk.CTkLabel(
            info_frame, text="No item selected\n\nClick a row on the left to begin.",
            font=FONT_LABEL, text_color=COLOR_TEXT_MUTED, justify="left"
        )
        self.info_label.pack(anchor="w", padx=14, pady=14)

        ctk.CTkLabel(checkout, text="Quantity to Sell", font=FONT_LABEL, text_color=COLOR_TEXT_MUTED).grid(
            row=2, column=0, sticky="w", padx=20, pady=(0, 4)
        )
        qty_row = ctk.CTkFrame(checkout, fg_color="transparent")
        qty_row.grid(row=3, column=0, sticky="ew", padx=20, pady=(0, 16))
        qty_row.grid_columnconfigure(1, weight=1)

        ctk.CTkButton(qty_row, text="–", width=36, height=36, fg_color=COLOR_CARD_ALT,
                      hover_color=COLOR_BORDER, command=lambda: self._step_qty(-1)
                      ).grid(row=0, column=0, padx=(0, 6))
        self.qty_entry = ctk.CTkEntry(
            qty_row, placeholder_text="1", height=36, corner_radius=8, justify="center",
            fg_color=COLOR_CARD_ALT, border_color=COLOR_BORDER, border_width=1,
        )
        self.qty_entry.grid(row=0, column=1, sticky="ew")
        self.qty_entry.bind("<Return>", lambda e: (self._sell(), "break"))
        ctk.CTkButton(qty_row, text="+", width=36, height=36, fg_color=COLOR_CARD_ALT,
                      hover_color=COLOR_BORDER, command=lambda: self._step_qty(1)
                      ).grid(row=0, column=2, padx=(6, 0))

        self.sell_button = ctk.CTkButton(
            checkout, text="✔  Complete Sale", font=FONT_BUTTON, height=44,
            fg_color=COLOR_GREEN, hover_color="#16a34a", corner_radius=10,
            state="disabled", command=self._sell,
        )
        self.sell_button.grid(row=4, column=0, sticky="ew", padx=20, pady=(0, 8))

        self.feedback_label = ctk.CTkLabel(
            checkout, text="", font=FONT_LABEL, text_color=COLOR_TEXT_MUTED, wraplength=220, justify="left")
        self.feedback_label.grid(
            row=5, column=0, sticky="w", padx=20, pady=(4, 20))

    def _step_qty(self, delta):
        try:
            current = int(self.qty_entry.get().strip() or "1")
        except ValueError:
            current = 1
        new_val = max(1, current + delta)
        self.qty_entry.delete(0, "end")
        self.qty_entry.insert(0, str(new_val))

    def _clear_search(self):
        self.search_entry.delete(0, "end")
        self.refresh()

    def _on_search_change(self, event=None):
        if self._search_job is not None:
            self.after_cancel(self._search_job)
        self._search_job = self.after(220, self.refresh)

    def _on_select(self, event=None):
        if self._refreshing:
            return
        selected = self.tree.selection()
        if not selected:
            self.selected_item = None
            self.info_label.configure(
                text="No item selected\n\nClick a row on the left to begin.", text_color=COLOR_TEXT_MUTED)
            self.sell_button.configure(state="disabled")
            return

        values = self.tree.item(selected[0], "values")
        if not values:
            self.selected_item = None
            self.info_label.configure(
                text="No item selected", text_color=COLOR_TEXT_MUTED)
            self.sell_button.configure(state="disabled")
            return

        self.selected_item = int(selected[0])
        sl_no, imei, model, chipset, ram, storage, color, qty, sell = values
        self.info_label.configure(
            text=(f"SL No.: {sl_no}\nIMEI: {imei}\n{model}\n{chipset}\n"
                  f"{ram} · {storage} · {color}\nIn stock: {qty}\nSelling Price: {sell}"),
            text_color=COLOR_TEXT,
        )
        self.sell_button.configure(state="normal")
        if not (self.qty_entry.get() or "").strip():
            self.qty_entry.insert(0, "1")

    def _sell(self):
        if self.selected_item is None:
            if self.toast:
                self.toast.show("Select an item from the stock list first.", "info")
            else:
                messagebox.showinfo(
                    "No Selection", "Select an item from the stock list first.")
            return
        try:
            qty = int(self.qty_entry.get().strip() or "1")
            if qty <= 0:
                raise ValueError
        except ValueError:
            if self.toast:
                self.toast.show("Enter a valid quantity to sell.", "error")
            else:
                messagebox.showwarning(
                    "Invalid Quantity", "Enter a valid quantity to sell.")
            return

        item = self.db.get_item(self.selected_item)
        if item is None:
            messagebox.showerror("Not Found", "This item no longer exists.")
            self.refresh()
            return

        item_id, sl_no, imei, model, chipset, ram, storage, color, in_stock, cost, sell_price = item
        if qty > in_stock:
            if self.toast:
                self.toast.show(f"Only {in_stock} unit(s) available.", "error")
            else:
                messagebox.showwarning("Insufficient Stock",
                                       f"Only {in_stock} unit(s) available.")
            return

        remaining = in_stock - qty
        if remaining <= 0:
            self.db.delete_item(item_id)
        else:
            self.db.update_quantity(item_id, remaining)

        profit = self.db.record_sale(
            item_id, sl_no, imei, model, chipset, ram, storage, color, qty, cost, sell_price)

        self.feedback_label.configure(
            text=f"Sold {qty} × {model} ({ram}, {color}) — Profit {format_price(profit)}",
            text_color=COLOR_GREEN,
        )
        if self.toast:
            self.toast.show(f"Sold {qty} × {model} for a profit of {format_price(profit)}.", "success")
        self.qty_entry.delete(0, "end")

        # If there's stock left, keep the item selected so staff can sell
        # the same model again right away instead of having to re-find it.
        keep_selected_id = item_id if remaining > 0 else None
        self.refresh()
        if keep_selected_id is not None and str(keep_selected_id) in self.tree.get_children():
            self.tree.selection_set(str(keep_selected_id))
            self._on_select()
            self.qty_entry.insert(0, "1")
            self.qty_entry.focus_set()

        if self.on_change:
            self.on_change()

    def refresh(self):
        self._refreshing = True
        try:
            self.tree.selection_remove(*self.tree.selection())
            for row in self.tree.get_children():
                self.tree.delete(row)
            rows = []
            items = self.db.get_inventory(self.search_entry.get())
            for i, (item_id, sl_no, imei, model, chipset, ram, storage, color, qty, cost, sell) in enumerate(items):
                if qty > 0:
                    rows.append((item_id, sl_no, imei, model, chipset, ram,
                                storage, color, qty, sell))
                    tags = ("evenrow" if i % 2 else "oddrow",)
                    self.tree.insert(
                        "",
                        "end",
                        iid=str(item_id),
                        tags=tags,
                        values=(
                            wrap_tree_text(sl_no or "-"),
                            wrap_tree_text(imei or "-"),
                            wrap_tree_text(model),
                            wrap_tree_text(chipset),
                            ram,
                            storage,
                            color,
                            qty,
                            format_price(sell),
                        ),
                    )

            if len(rows) == 1:
                item_id = str(rows[0][0])
                self.tree.selection_set(item_id)
                self._on_select()
                self.selected_item = rows[0][0]
            else:
                self.selected_item = None
                self.info_label.configure(
                    text="No item selected\n\nClick a row on the left to begin.", text_color=COLOR_TEXT_MUTED)
                self.feedback_label.configure(text="")
                self.qty_entry.delete(0, "end")
                self.sell_button.configure(state="disabled")
        finally:
            self._refreshing = False


# --------------------------------------------------------------------- #
# Sales History & Analytics Frame
# --------------------------------------------------------------------- #
class HistoryFrame(ctk.CTkFrame):
    def __init__(self, master, db: Database):
        super().__init__(master, fg_color="transparent")
        self.db = db
        self._build()
        self.refresh()

    def _build(self):
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        header = page_header(self, "Sales History & Analytics",
                              "Every completed sale, most recent first", row=0)
        header.grid_columnconfigure(1, weight=0)

        btns = ctk.CTkFrame(header, fg_color="transparent")
        btns.grid(row=0, column=1, sticky="e")
        ctk.CTkButton(
            btns, text="⟳  Refresh", width=110, fg_color=COLOR_CARD_ALT, hover_color=COLOR_BORDER,
            command=self.refresh,
        ).pack(side="left", padx=(0, 8))
        ctk.CTkButton(
            btns, text="📊  End of Day Summary", width=190, fg_color=COLOR_ACCENT,
            hover_color=COLOR_ACCENT_HOVER, command=self._show_summary,
        ).pack(side="left")

        table_card = ctk.CTkFrame(
            self, fg_color=COLOR_CARD, corner_radius=14, border_width=1, border_color=COLOR_BORDER
        )
        table_card.grid(row=1, column=0, sticky="nsew")
        table_card.grid_columnconfigure(0, weight=1)
        table_card.grid_rowconfigure(0, weight=1)

        columns = ("time", "model", "specs", "cost", "sell", "qty", "profit")
        headers = {
            "time": ("Date & Time", 160),
            "model": ("Model", 150),
            "specs": ("Specs", 150),
            "cost": ("Retail Price", 100),
            "sell": ("Selling Price", 110),
            "qty": ("Qty", 60),
            "profit": ("Net Profit", 110),
        }
        self.tree = SortableTreeview(
            table_card, columns, headers,
            numeric_cols=("cost", "sell", "qty", "profit"), style="Custom.Treeview",
        )
        self.tree.tag_configure("oddrow", background=COLOR_CARD)
        self.tree.tag_configure("evenrow", background=COLOR_ROW_ALT)
        self.tree.tag_configure("loss", foreground=COLOR_RED)
        self.tree.grid(row=0, column=0, sticky="nsew", padx=(20, 0), pady=20)

        scrollbar = ttk.Scrollbar(
            table_card, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)
        scrollbar.grid(row=0, column=1, sticky="ns", padx=(0, 20), pady=20)

    def refresh(self):
        for row in self.tree.get_children():
            self.tree.delete(row)
        sales = self.db.get_sales()
        for i, sale in enumerate(sales):
            (sale_id, item_id, sl_no, imei, model, chipset, ram, storage,
             color, qty, cost, sell, profit, sold_at) = sale
            specs = f"{chipset} · {ram} · {storage} · {color}"
            tags = ["evenrow" if i % 2 else "oddrow"]
            if profit < 0:
                tags.append("loss")
            self.tree.insert(
                "", "end", tags=tuple(tags),
                values=(
                    sold_at,
                    wrap_tree_text(model),
                    wrap_tree_text(specs),
                    format_price(cost),
                    format_price(sell),
                    qty,
                    format_price(profit),
                ),
            )

    def _show_summary(self):
        summary = self.db.get_today_summary()

        modal = ctk.CTkToplevel(self)
        modal.title("End of Day Summary")
        modal.configure(fg_color=COLOR_BG)
        modal.resizable(False, False)
        modal.transient(self.winfo_toplevel())
        center_toplevel(modal, self.winfo_toplevel(), 380, 400)
        modal.grab_set()

        ctk.CTkLabel(modal, text="End of Day Summary",
                     font=FONT_TITLE).pack(pady=(24, 4))
        ctk.CTkLabel(modal, text=summary["date"], font=FONT_SUBTITLE, text_color=COLOR_TEXT_MUTED).pack(
            pady=(0, 20)
        )

        def stat_row(label, value, color=COLOR_TEXT):
            row = ctk.CTkFrame(modal, fg_color=COLOR_CARD, corner_radius=10)
            row.pack(fill="x", padx=24, pady=6)
            ctk.CTkLabel(row, text=label, font=FONT_LABEL, text_color=COLOR_TEXT_MUTED).pack(
                side="left", padx=16, pady=14
            )
            ctk.CTkLabel(row, text=value, font=("Segoe UI", 15, "bold"), text_color=color).pack(
                side="right", padx=16, pady=14
            )

        stat_row("Units Sold", str(summary["units_sold"]))
        stat_row("Total Revenue", format_price(summary["total_revenue"]))
        stat_row("Total Cost", format_price(summary["total_cost"]))
        stat_row(
            "Total Net Profit",
            format_price(summary["total_profit"]),
            color=COLOR_GREEN if summary["total_profit"] >= 0 else COLOR_RED,
        )

        ctk.CTkButton(
            modal, text="Close", fg_color=COLOR_ACCENT, hover_color=COLOR_ACCENT_HOVER, command=modal.destroy
        ).pack(pady=(20, 10), padx=24, fill="x")


# --------------------------------------------------------------------- #
# Main Application Window
# --------------------------------------------------------------------- #
class App(ctk.CTk):
    NAV_ITEMS = [
        ("dashboard", "🏠", "Overview"),
        ("inventory", "📦", "Stock"),
        ("pos", "🧾", "Checkout"),
        ("history", "📊", "Sales History"),
    ]

    def __init__(self):
        super().__init__()
        self.db = Database()
        configure_treeview_style()
        self.toast = ToastManager(self)

        self.title("Phone Stock & Sales Tracker")
        self.geometry("1500x900")
        self.minsize(1200, 650)
        self.configure(fg_color=COLOR_BG)

        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        self._build_sidebar()
        self._build_content()
        self._bind_shortcuts()
        self._select_tab("dashboard")

    # ------------------------------------------------------------------ #
    def _build_sidebar(self):
        sidebar = ctk.CTkFrame(
            self, width=230, fg_color=COLOR_SIDEBAR, corner_radius=0)
        sidebar.grid(row=0, column=0, sticky="nsw")
        sidebar.grid_propagate(False)

        ctk.CTkLabel(sidebar, text="📱 PhoneTrack", font=("Segoe UI", 20, "bold")).pack(
            anchor="w", padx=24, pady=(28, 4)
        )
        ctk.CTkLabel(
            sidebar, text="Inventory & Sales", font=FONT_SUBTITLE, text_color=COLOR_TEXT_MUTED
        ).pack(anchor="w", padx=24, pady=(0, 32))

        self.nav_buttons = {}
        self.nav_indicators = {}
        for key, icon, label in self.NAV_ITEMS:
            row = ctk.CTkFrame(sidebar, fg_color="transparent")
            row.pack(fill="x", padx=14, pady=4)
            row.grid_columnconfigure(1, weight=1)

            indicator = ctk.CTkFrame(row, width=4, fg_color="transparent", corner_radius=2)
            indicator.grid(row=0, column=0, sticky="ns", padx=(0, 6))
            self.nav_indicators[key] = indicator

            btn = ctk.CTkButton(
                row, text=f"{icon}  {label}", anchor="w", font=FONT_LABEL_BOLD, height=44,
                corner_radius=10, fg_color="transparent", hover_color=COLOR_CARD_ALT,
                text_color="#d1d5db", command=lambda k=key: self._select_tab(k),
            )
            btn.grid(row=0, column=1, sticky="ew")
            self.nav_buttons[key] = btn

        bottom = ctk.CTkFrame(sidebar, fg_color="transparent")
        bottom.pack(side="bottom", fill="x", padx=24, pady=24)
        self.clock_label = ctk.CTkLabel(
            bottom, text="", font=("Segoe UI", 11, "bold"), text_color=COLOR_TEXT_MUTED)
        self.clock_label.pack(anchor="w")
        ctk.CTkLabel(
            bottom, text="v1.1 · Local Storage", font=("Segoe UI", 10), text_color="#5b5b66"
        ).pack(anchor="w", pady=(2, 0))
        self._tick_clock()

    def _tick_clock(self):
        self.clock_label.configure(text=datetime.now().strftime("%A, %d %b · %I:%M %p"))
        self.after(1000, self._tick_clock)

    def _build_content(self):
        container = ctk.CTkFrame(self, fg_color=COLOR_BG, corner_radius=0)
        container.grid(row=0, column=1, sticky="nsew", padx=28, pady=28)
        container.grid_columnconfigure(0, weight=1)
        container.grid_rowconfigure(0, weight=1)

        pages_holder = ctk.CTkFrame(container, fg_color="transparent")
        pages_holder.grid(row=0, column=0, sticky="nsew")
        pages_holder.grid_columnconfigure(0, weight=1)
        pages_holder.grid_rowconfigure(0, weight=1)

        self.frames = {
            "dashboard": DashboardFrame(pages_holder, self.db, on_navigate=self._select_tab),
            "inventory": InventoryFrame(pages_holder, self.db, on_change=self._refresh_all, toast=self.toast),
            "pos": POSFrame(pages_holder, self.db, on_change=self._refresh_all, toast=self.toast),
            "history": HistoryFrame(pages_holder, self.db),
        }
        for frame in self.frames.values():
            frame.grid(row=0, column=0, sticky="nsew")

    def _bind_shortcuts(self):
        keys = ["1", "2", "3", "4"]
        for key, (nav_key, _icon, _label) in zip(keys, self.NAV_ITEMS):
            self.bind(f"<Control-Key-{key}>", lambda e, k=nav_key: self._select_tab(k))
        self.bind("<Control-f>", self._focus_current_search)
        self.bind("<F5>", lambda e: self._refresh_all())

    def _focus_current_search(self, event=None):
        frame = self.frames.get(self.current_tab)
        search = getattr(frame, "search_entry", None)
        if search is not None:
            search.focus_set()

    def _select_tab(self, key):
        self.current_tab = key
        for k, btn in self.nav_buttons.items():
            is_active = k == key
            btn.configure(
                fg_color=COLOR_ACCENT if is_active else "transparent",
                text_color="#ffffff" if is_active else "#d1d5db",
            )
            self.nav_indicators[k].configure(
                fg_color=COLOR_ACCENT if is_active else "transparent")
        self.frames[key].tkraise()
        self.frames[key].refresh()

    def _refresh_all(self):
        for frame in self.frames.values():
            frame.refresh()


if __name__ == "__main__":
    app = App()
    app.mainloop()