import os

from flask import Flask, jsonify, render_template, request

from database import Database


app = Flask(__name__)
db = Database()


def item_dict(row):
    keys = ("id", "sl_no", "imei", "model", "chipset", "ram", "storage",
            "color", "quantity", "cost_price", "sell_price")
    return dict(zip(keys, row))


def sale_dict(row):
    keys = ("id", "item_id", "sl_no", "imei", "model", "chipset", "ram",
            "storage", "color", "quantity", "cost_price", "sell_price",
            "profit", "sold_at")
    return dict(zip(keys, row))


@app.get("/")
def index():
    return render_template("index.html")


@app.get("/manifest.json")
def manifest():
    return jsonify({
        "name": "PhoneTrack",
        "short_name": "PhoneTrack",
        "start_url": "/",
        "display": "standalone",
        "background_color": "#111318",
        "theme_color": "#111318",
        "icons": [],
    })


@app.get("/api/inventory")
def inventory():
    return jsonify([item_dict(row) for row in db.get_inventory(request.args.get("q", ""))])


@app.post("/api/inventory")
def add_inventory():
    data = request.get_json() or {}
    required = ("sl_no", "imei", "model", "chipset", "ram", "storage", "color")
    if any(not str(data.get(field, "")).strip() for field in required):
        return jsonify(error="Fill in all required fields."), 400
    try:
        quantity = int(data.get("quantity", 0))
        cost = float(data.get("cost_price", 0))
        sell = float(data.get("sell_price", 0))
        if quantity <= 0 or cost < 0 or sell < 0:
            raise ValueError
    except (TypeError, ValueError):
        return jsonify(error="Quantity and prices must be valid numbers."), 400
    if db.sl_no_exists(data["sl_no"].strip()):
        return jsonify(error="That SL No. already exists."), 409
    item_id = db.add_item(
        data["model"].strip(), data["chipset"].strip(), data["ram"].strip(),
        data["storage"].strip(), data["color"].strip(), data["sl_no"].strip(),
        data["imei"].strip(), quantity, cost, sell,
    )
    return jsonify(id=item_id), 201


@app.post("/api/sales")
def sell():
    data = request.get_json() or {}
    try:
        item_id = int(data.get("item_id"))
        quantity = int(data.get("quantity", 1))
    except (TypeError, ValueError):
        return jsonify(error="Choose an item and enter a valid quantity."), 400
    if quantity <= 0:
        return jsonify(error="Quantity must be greater than zero."), 400
    item = db.get_item(item_id)
    if item is None:
        return jsonify(error="That inventory item no longer exists."), 404
    item_id, sl_no, imei, model, chipset, ram, storage, color, in_stock, cost, sell_price = item
    if quantity > in_stock:
        return jsonify(error=f"Only {in_stock} unit(s) available."), 400
    if in_stock == quantity:
        db.delete_item(item_id)
    else:
        db.update_quantity(item_id, in_stock - quantity)
    profit = db.record_sale(item_id, sl_no, imei, model, chipset, ram, storage,
                            color, quantity, cost, sell_price)
    return jsonify(profit=profit), 201


@app.get("/api/sales")
def sales():
    return jsonify([sale_dict(row) for row in db.get_sales()])


@app.get("/api/summary")
def summary():
    return jsonify(db.get_today_summary())


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("WEB_PORT", "5000")))
