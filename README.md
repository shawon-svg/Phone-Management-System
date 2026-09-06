# Phone Inventory & Sales Tracker

A clean, dark-mode desktop app for tracking phone stock and sales, built with **Python** and **CustomTkinter**.

## Setup

```bash
python3 -m pip install -r requirements.txt
python3 app.py
```

Requires Python 3.9+. Data is stored locally in `phone_inventory.db` (SQLite),
created automatically next to `app.py` on first run.

## Use on iPhone

The desktop app cannot run directly on iOS. A mobile-friendly web version is
included in `web_app.py` and can be opened in Safari or added to the iPhone
Home Screen.

```bash
source .venv/bin/activate
python3 web_app.py
```

To use it from an iPhone, keep the Mac and iPhone on the same Wi-Fi network,
open `http://YOUR-MAC-IP:5000` on the iPhone, then choose Safari's **Add to
Home Screen** option. The Mac must keep the web server running.

## Files

- `app.py` — GUI (sidebar navigation + Stock / Chekout / Sales History screens)
- `database.py` — SQLite persistence layer (all read/write logic lives here)
- `phone_inventory.db` — created automatically; safe to delete to reset all data

## Features

**Stock tab**
- Add stock with Brand / Model, Chipset, RAM, Storage, Color, Quantity, Cost Price, Selling Price
- Profit-per-unit preview updates live as you type prices
- Search stock by model, chipset, RAM, storage, or color; matching rows include selling price
- Vertical and horizontal scrolling keeps the stock table usable in smaller windows
- Select a row and click "Delete Selected" to remove it

**Chekout tab**
- Pick an in-stock item, set quantity, click **Sell**
- Search by model, chipset, RAM, storage, or color before selecting an item
- Stock is reduced automatically and a sale record is logged
- Warns on insufficient stock or invalid quantity

**Sales History tab**
- Full sold-items log: date/time, specs, cost price, selling price, quantity, net profit
- **End of Day Summary** button opens a modal with today's total units sold,
  revenue, cost, and net profit

## Notes

- RAM field is a combo box with common presets (4GB–16GB) but is also editable,
  so you can type a custom value.
- Prices are displayed as plain numbers without a currency symbol. Entering a
  number in a stock search, such as `30000`, shows phones priced below that amount.

## GitHub and sharing

GitHub stores and shares the source code, but this CustomTkinter desktop app does
not run in a browser or directly on Android. To let everyone use it from a link,
the GUI must be converted to a web UI (for example, Streamlit) and deployed on
Render, Railway, or another Python web host. A GitHub link alone is only a code
link; users can run the desktop version locally with Python.

To publish the current desktop version:

```bash
git init
git add app.py database.py README.md requirements.txt
git commit -m "Add phone stock search and chipset tracking"
git branch -M main
git remote add origin https://github.com/YOUR-USERNAME/YOUR-REPOSITORY.git
git push -u origin main
```

Create a new empty repository on GitHub first, then replace the URL above. Do not
commit `phone_inventory.db` if it contains private customer or sales data.
