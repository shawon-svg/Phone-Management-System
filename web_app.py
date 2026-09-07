import os
import csv
import io

from flask import Flask, Response, jsonify, render_template, request
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
from xml.sax.saxutils import escape

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


def csv_download(filename, headers, rows):
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(headers)
    writer.writerows(rows)
    return Response(
        output.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


def pdf_download(filename, sales, summary, stock_stats):
    output = io.BytesIO()
    document = SimpleDocTemplate(
        output, pagesize=landscape(A4), rightMargin=12 * mm,
        leftMargin=12 * mm, topMargin=12 * mm, bottomMargin=12 * mm,
    )
    styles = getSampleStyleSheet()
    body = styles["BodyText"]
    body.fontSize = 7
    body.leading = 9
    title = styles["Title"]
    title.fontSize = 18
    story = [Paragraph("PhoneTrack - Complete Sales Report", title)]
    story.append(Paragraph(
        f"Generated {summary['date']} | Current stock: {stock_stats['total_units']} units "
        f"({stock_stats['stock_value']:,.2f})", body,
    ))
    story.append(Spacer(1, 6))
    story.append(Paragraph(
        f"Sold today: {summary['units_sold']} units | Revenue: {summary['total_revenue']:,.2f} | "
        f"Cost: {summary['total_cost']:,.2f} | Profit: {summary['total_profit']:,.2f}", body,
    ))
    story.append(Spacer(1, 10))

    table_rows = [["Date & Time", "Model", "SL No.", "IMEI", "Qty", "Cost",
                   "Selling Price", "Profit"]]
    for sale in sales:
        table_rows.append([
            sale[13], escape(str(sale[4] or "")), escape(str(sale[2] or "")),
            escape(str(sale[3] or "")), str(sale[9]), f"{sale[10]:,.2f}",
            f"{sale[11]:,.2f}", f"{sale[12]:,.2f}",
        ])
    if len(table_rows) == 1:
        table_rows.append(["No sales recorded", "", "", "", "", "", "", ""])
    table = Table(table_rows, repeatRows=1, colWidths=[31 * mm, 45 * mm, 22 * mm,
                                                       38 * mm, 12 * mm, 24 * mm,
                                                       29 * mm, 24 * mm])
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#202832")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 7),
        ("GRID", (0, 0), (-1, -1), 0.3, colors.HexColor("#c8cdd4")),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1),
         [colors.white, colors.HexColor("#f1f3f5")]),
        ("ALIGN", (4, 1), (-1, -1), "RIGHT"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    story.append(table)
    document.build(story)
    return Response(
        output.getvalue(), mimetype="application/pdf",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


def stock_pdf_download(filename, inventory, stock_stats):
    output = io.BytesIO()
    document = SimpleDocTemplate(
        output, pagesize=landscape(A4), rightMargin=12 * mm,
        leftMargin=12 * mm, topMargin=12 * mm, bottomMargin=12 * mm,
    )
    styles = getSampleStyleSheet()
    body = styles["BodyText"]
    body.fontSize = 7
    body.leading = 9
    title = styles["Title"]
    title.fontSize = 18
    story = [Paragraph("PhoneTrack - Current Stock Report", title)]
    story.append(Paragraph(
        f"Current stock: {stock_stats['total_units']} units | "
        f"Stock value: {stock_stats['stock_value']:,.2f}", body,
    ))
    story.append(Spacer(1, 10))
    table_rows = [["SL No.", "IMEI", "Model", "Chipset", "RAM", "Storage",
                   "Color", "Qty", "Cost", "Selling Price"]]
    for item in inventory:
        table_rows.append([
            escape(str(item[1] or "")), escape(str(item[2] or "")),
            escape(str(item[3] or "")), escape(str(item[4] or "")),
            escape(str(item[5] or "")), escape(str(item[6] or "")),
            escape(str(item[7] or "")), str(item[8]), f"{item[9]:,.2f}",
            f"{item[10]:,.2f}",
        ])
    if len(table_rows) == 1:
        table_rows.append(["No stock recorded", "", "",
                          "", "", "", "", "", "", ""])
    table = Table(table_rows, repeatRows=1)
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#202832")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 7),
        ("GRID", (0, 0), (-1, -1), 0.3, colors.HexColor("#c8cdd4")),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1),
         [colors.white, colors.HexColor("#f1f3f5")]),
        ("ALIGN", (7, 1), (-1, -1), "RIGHT"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    story.append(table)
    document.build(story)
    return Response(
        output.getvalue(), mimetype="application/pdf",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


def summary_pdf_download(filename, summary, stock_stats):
    output = io.BytesIO()
    document = SimpleDocTemplate(
        output, pagesize=A4, rightMargin=18 * mm,
        leftMargin=18 * mm, topMargin=18 * mm, bottomMargin=18 * mm,
    )
    styles = getSampleStyleSheet()
    title = styles["Title"]
    title.fontSize = 20
    story = [Paragraph("PhoneTrack - Daily Summary", title), Spacer(1, 12)]
    rows = [
        ["Date", summary["date"]],
        ["Current stock units", str(stock_stats["total_units"])],
        ["Current stock value", f"{stock_stats['stock_value']:,.2f}"],
        ["Units sold today", str(summary["units_sold"])],
        ["Revenue today", f"{summary['total_revenue']:,.2f}"],
        ["Cost today", f"{summary['total_cost']:,.2f}"],
        ["Profit today", f"{summary['total_profit']:,.2f}"],
    ]
    table = Table(rows, colWidths=[75 * mm, 75 * mm])
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#202832")),
        ("TEXTCOLOR", (0, 0), (0, -1), colors.white),
        ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 11),
        ("GRID", (0, 0), (-1, -1), 0.3, colors.HexColor("#c8cdd4")),
        ("ROWBACKGROUNDS", (1, 0), (1, -1),
         [colors.white, colors.HexColor("#f1f3f5")]),
        ("ALIGN", (1, 1), (1, -1), "RIGHT"),
        ("TOPPADDING", (0, 0), (-1, -1), 9),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 9),
    ]))
    story.append(table)
    document.build(story)
    return Response(
        output.getvalue(), mimetype="application/pdf",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


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


@app.get("/export/stock.csv")
def export_stock():
    rows = db.get_inventory()
    return csv_download(
        "phonetrack-stock.csv",
        ("ID", "SL No.", "IMEI", "Model", "Chipset", "RAM", "Storage",
         "Color", "Quantity", "Cost Price", "Selling Price"),
        rows,
    )


@app.get("/export/sales.csv")
def export_sales():
    rows = db.get_sales()
    return csv_download(
        "phonetrack-sales-history.csv",
        ("Sale ID", "Item ID", "SL No.", "IMEI", "Model", "Chipset", "RAM",
         "Storage", "Color", "Quantity", "Cost Price", "Selling Price",
         "Profit", "Sold At"),
        rows,
    )


@app.get("/export/daily-summary.csv")
def export_daily_summary():
    summary = db.get_today_summary()
    stats = db.get_dashboard_stats()
    return csv_download(
        "phonetrack-daily-summary.csv",
        ("Date", "Current Stock Units", "Current Stock Value", "Units Sold Today",
         "Revenue Today", "Cost Today", "Profit Today"),
        [[summary["date"], stats["total_units"], stats["stock_value"],
          summary["units_sold"], summary["total_revenue"], summary["total_cost"],
          summary["total_profit"]]],
    )


@app.get("/export/sales.pdf")
def export_sales_pdf():
    return pdf_download(
        "phonetrack-complete-sales-report.pdf",
        db.get_sales(), db.get_today_summary(), db.get_dashboard_stats(),
    )


@app.get("/export/stock.pdf")
def export_stock_pdf():
    return stock_pdf_download(
        "phonetrack-current-stock-report.pdf",
        db.get_inventory(), db.get_dashboard_stats(),
    )


@app.get("/export/daily-summary.pdf")
def export_daily_summary_pdf():
    return summary_pdf_download(
        "phonetrack-daily-summary.pdf",
        db.get_today_summary(), db.get_dashboard_stats(),
    )


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("WEB_PORT", "5000")))
