from flask import Flask, render_template, request
from datetime import datetime, timedelta
import sqlite3
import threading
import requests

app = Flask(__name__)
DB = 'db.sqlite'
IN_USE_FLAG = {"in_use": False, "start_time": None}


def init_db():
    with sqlite3.connect(DB) as con:
        cur = con.cursor()
        cur.execute('''
            CREATE TABLE IF NOT EXISTS subscriptions (
                phone TEXT PRIMARY KEY,
                expiry_date TEXT
            )
        ''')
        con.commit()


def check_expiry(phone):
    with sqlite3.connect(DB) as con:
        cur = con.cursor()
        cur.execute("SELECT expiry_date FROM subscriptions WHERE phone = ?", (phone,))
        row = cur.fetchone()
        if row:
            expiry = datetime.strptime(row[0], "%Y-%m-%d").date()
            return expiry
        return None


def update_expiry(phone, days):
    new_expiry = (datetime.now().date() + timedelta(days=days)).strftime("%Y-%m-%d")
    with sqlite3.connect(DB) as con:
        cur = con.cursor()
        cur.execute("INSERT OR REPLACE INTO subscriptions (phone, expiry_date) VALUES (?, ?)", (phone, new_expiry))
        con.commit()


def reset_usage():
    IN_USE_FLAG["in_use"] = False
    IN_USE_FLAG["start_time"] = None


def start_usage_timer():
    threading.Timer(1800, reset_usage).start()


@app.route("/", methods=["GET", "POST"])
def index():
    if request.method == "POST":
        phone = request.form["phone"]
        today = datetime.now().date()
        expiry = check_expiry(phone)
        if IN_USE_FLAG["in_use"]:
            elapsed = (datetime.now() - IN_USE_FLAG["start_time"]).seconds
            remaining = 1800 - elapsed
            return render_template("in_use.html", remaining=remaining)

        if expiry and expiry >= today:
            return render_template("active.html", phone=phone)
        return render_template("payment.html", phone=phone)
    return render_template("index.html")


@app.route("/turn_on/<phone>")
def turn_on(phone):
    if not IN_USE_FLAG["in_use"]:
        IN_USE_FLAG["in_use"] = True
        IN_USE_FLAG["start_time"] = datetime.now()
        start_usage_timer()
        requests.get("https://www.virtualsmarthome.xyz/url_routine_trigger/activate.php?trigger=d613829d-a350-476b-b520-15e33c3d39f5&token=965a8bd9-75b5-4963-99dc-c2bc65767c17&response=html")
        return "Machine turned on for 30 minutes."
    else:
        return "Machine already in use."


@app.route("/post_payment", methods=["GET", "POST"])
def post_payment():
    if request.method == "POST":
        phone = request.form["phone"]
        plan = request.form["plan"]
        days = {"daily": 1, "weekly": 7, "monthly": 30}.get(plan, 1)
        update_expiry(phone, days)
        return render_template("active.html", phone=phone)
    return render_template("post_payment.html")


if __name__ == "__main__":
    init_db()
    app.run(debug=True)