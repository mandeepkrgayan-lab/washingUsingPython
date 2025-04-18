from flask import Flask, render_template, request, redirect, url_for
import sqlite3
from datetime import datetime, timedelta
import requests
import os

app = Flask(__name__)
DATABASE = 'db.sqlite'
MACHINE_URL = 'https://www.virtualsmarthome.xyz/url_routine_trigger/activate.php?trigger=d613829d-a350-476b-b520-15e33c3d39f5&token=965a8bd9-75b5-4963-99dc-c2bc65767c17&response=html'

def init_db():
    conn = sqlite3.connect(DATABASE)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS subscriptions (
        phone TEXT PRIMARY KEY,
        expiry TEXT
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS status (
        in_use TEXT,
        start_time TEXT
    )''')
    c.execute("INSERT OR IGNORE INTO status (rowid, in_use, start_time) VALUES (1, 'false', '')")
    conn.commit()
    conn.close()

def get_status():
    conn = sqlite3.connect(DATABASE)
    c = conn.cursor()
    c.execute("SELECT in_use, start_time FROM status WHERE rowid = 1")
    row = c.fetchone()
    conn.close()
    return row[0], row[1]

def update_status(in_use, start_time=""):
    conn = sqlite3.connect(DATABASE)
    c = conn.cursor()
    c.execute("UPDATE status SET in_use = ?, start_time = ? WHERE rowid = 1", (in_use, start_time))
    conn.commit()
    conn.close()

@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        phone = request.form['phone']
        now = datetime.now()
        in_use, start_time = get_status()
        if in_use == "true":
            remaining = 30 - (now - datetime.fromisoformat(start_time)).seconds // 60
            if remaining > 0:
                return render_template("in_use.html", minutes=remaining)
            else:
                update_status("false")

        conn = sqlite3.connect(DATABASE)
        c = conn.cursor()
        c.execute("SELECT expiry FROM subscriptions WHERE phone = ?", (phone,))
        row = c.fetchone()
        conn.close()

        if row:
            expiry_date = datetime.strptime(row[0], "%Y-%m-%d")
            if expiry_date >= now:
                return render_template("active.html", phone=phone)
            else:
                return render_template("payment.html", phone=phone)
        else:
            return render_template("payment.html", phone=phone)
    return render_template("index.html")

@app.route('/activate', methods=['POST'])
def activate():
    phone = request.form['phone']
    requests.get(MACHINE_URL)
    update_status("true", datetime.now().isoformat())
    return f"Washing machine activated for 30 minutes for {phone}."

@app.route('/subscribe', methods=['POST'])
def subscribe():
    plan = request.form['plan']
    phone = request.form['phone']
    if plan == "daily":
        amount = 79
        days = 1
    elif plan == "weekly":
        amount = 119
        days = 7
    else:
        amount = 199
        days = 30

    return render_template("post_payment.html", phone=phone, days=days)

@app.route('/update', methods=['POST'])
def update():
    phone = request.form['phone']
    days = int(request.form['days'])
    new_expiry = (datetime.now() + timedelta(days=days)).strftime("%Y-%m-%d")
    conn = sqlite3.connect(DATABASE)
    c = conn.cursor()
    c.execute("INSERT OR REPLACE INTO subscriptions (phone, expiry) VALUES (?, ?)", (phone, new_expiry))
    conn.commit()
    conn.close()
    return render_template("active.html", phone=phone)

if __name__ == '__main__':
    init_db()
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
