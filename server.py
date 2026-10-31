import json
import os
import sqlite3
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).parent
DATABASE = Path(os.environ.get("DATABASE_PATH", ROOT / "production.db"))


def database():
    db = sqlite3.connect(DATABASE)
    db.row_factory = sqlite3.Row
    return db


def setup():
    DATABASE.parent.mkdir(parents=True, exist_ok=True)
    with database() as db:
        db.executescript("""
            CREATE TABLE IF NOT EXISTS orders (
                id INTEGER PRIMARY KEY AUTOINCREMENT, order_number TEXT NOT NULL,
                product TEXT NOT NULL, quantity INTEGER NOT NULL, machine TEXT NOT NULL,
                worker TEXT NOT NULL, stage TEXT NOT NULL, due_date TEXT NOT NULL,
                status TEXT NOT NULL, progress INTEGER NOT NULL DEFAULT 0
            );
            CREATE TABLE IF NOT EXISTS materials (
                id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL,
                quantity TEXT NOT NULL, status TEXT NOT NULL
            );
        """)
        test_orders = [
            ("PO-101", "Steel Bottle", 500, "Press 1", "Ravi", "Assembly", "2026-10-20", "On time", 75),
            ("PO-102", "Gear Set", 320, "CNC 2", "Meena", "Machining", "2026-10-21", "Delayed", 45),
            ("PO-103", "Pipe Connector", 700, "Mould 3", "Arjun", "Quality Check", "2026-10-22", "On time", 90),
            ("PO-104", "Aluminium Bracket", 250, "Press 1", "Sara", "Cutting", "2026-10-24", "On time", 30),
            ("PO-105", "Valve Housing", 180, "CNC 2", "Daniel", "Machining", "2026-10-26", "Delayed", 20),
            ("PO-106", "Plastic Cover", 1000, "Mould 3", "Priya", "Assembly", "2026-10-28", "Complete", 100),
        ]
        for order in test_orders:
            db.execute("""INSERT INTO orders
                (order_number, product, quantity, machine, worker, stage, due_date, status, progress)
                SELECT ?, ?, ?, ?, ?, ?, ?, ?, ?
                WHERE NOT EXISTS (SELECT 1 FROM orders WHERE order_number = ?)""", (*order, order[0]))

        test_materials = [
            ("Steel sheets", "240 kg", "Available"),
            ("Gear blanks", "35 pieces", "Low stock"),
            ("Plastic pellets", "90 kg", "Available"),
            ("Aluminium bars", "120 kg", "Available"),
            ("Rubber seals", "18 boxes", "Low stock"),
        ]
        for material in test_materials:
            db.execute("""INSERT INTO materials (name, quantity, status)
                SELECT ?, ?, ?
                WHERE NOT EXISTS (SELECT 1 FROM materials WHERE name = ?)""", (*material, material[0]))


def valid_order(data):
    try:
        quantity, progress = int(data["quantity"]), int(data["progress"])
        required = ("order_number", "product", "machine", "worker", "stage", "due_date")
        if any(not str(data[key]).strip() for key in required) or quantity < 1 or not 0 <= progress <= 100:
            return None
        return (
            *(str(data[key]).strip() for key in required[:5]),
            data["due_date"],
            data.get("status", "On time") if data.get("status") in ("On time", "Delayed", "Complete") else "On time",
            quantity, progress,
        )
    except (KeyError, TypeError, ValueError):
        return None


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(ROOT), **kwargs)

    def log_message(self, *_args):
        pass

    def json_body(self):
        length = int(self.headers.get("Content-Length", 0))
        return json.loads(self.rfile.read(length) or b"{}")

    def reply(self, data, status=200):
        body = json.dumps(data).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        path = urlparse(self.path).path
        if path == "/api/orders":
            with database() as db:
                self.reply([dict(row) for row in db.execute("SELECT * FROM orders ORDER BY id")])
        elif path == "/api/materials":
            with database() as db:
                self.reply([dict(row) for row in db.execute("SELECT * FROM materials ORDER BY id")])
        elif path.startswith("/api/"):
            self.reply({"error": "Not found"}, 404)
        else:
            super().do_GET()

    def do_POST(self):
        if urlparse(self.path).path != "/api/orders":
            self.reply({"error": "Not found"}, 404)
            return
        order = valid_order(self.json_body())
        if not order:
            self.reply({"error": "Invalid order data"}, 400)
            return
        with database() as db:
            cursor = db.execute("""INSERT INTO orders
                (order_number, product, machine, worker, stage, due_date, status, quantity, progress)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""", order)
            self.reply({"id": cursor.lastrowid}, 201)

    def do_PUT(self):
        path = urlparse(self.path).path
        data = self.json_body()
        try:
            item_id = int(path.rsplit("/", 1)[1])
        except (IndexError, ValueError):
            self.reply({"error": "Invalid id"}, 400)
            return
        with database() as db:
            if path.startswith("/api/orders/"):
                order = valid_order(data)
                if not order:
                    self.reply({"error": "Invalid order data"}, 400)
                    return
                db.execute("""UPDATE orders SET order_number=?, product=?, machine=?, worker=?,
                    stage=?, due_date=?, status=?, quantity=?, progress=? WHERE id=?""", (*order, item_id))
            elif path.startswith("/api/materials/"):
                if not data.get("name", "").strip() or not data.get("quantity", "").strip() or data.get("status") not in ("Available", "Low stock"):
                    self.reply({"error": "Invalid material data"}, 400)
                    return
                db.execute("UPDATE materials SET name=?, quantity=?, status=? WHERE id=?",
                           (data["name"].strip(), data["quantity"].strip(), data["status"], item_id))
            else:
                self.reply({"error": "Not found"}, 404)
                return
        self.reply({"updated": True})

    def do_DELETE(self):
        path = urlparse(self.path).path
        if not path.startswith("/api/orders/"):
            self.reply({"error": "Not found"}, 404)
            return
        with database() as db:
            db.execute("DELETE FROM orders WHERE id=?", (int(path.rsplit("/", 1)[1]),))
        self.reply({"deleted": True})


if __name__ == "__main__":
    setup()
    port = int(os.environ.get("PORT", 10000))
    print(f"Production Tracker running on port {port}")
    ThreadingHTTPServer(("0.0.0.0", port), Handler).serve_forever()
