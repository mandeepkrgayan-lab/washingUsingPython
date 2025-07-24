from flask import Flask, render_template, request, jsonify
import pymysql
from datetime import datetime, timedelta
import threading
import os
import requests

app = Flask(__name__)

# Constants
OWNER_PHONE = "7664000017"
TRIGGER_URL = "https://www.virtualsmarthome.xyz/url_routine_trigger/activate.php?trigger=d613829d-a350-476b-b520-15e33c3d39f5&token=965a8bd9-75b5-4963-99dc-c2bc65767c17&response=html"
FORCE_OFF_URL = "https://www.virtualsmarthome.xyz/url_routine_trigger/activate.php?trigger=f7fdcb3b-c16d-4601-90e6-f0729cc038ac&token=3ac706a2-1e9a-4b07-90ef-116be4142ef7&response=json"

# DB Config
DB_HOST = os.getenv("MYSQLHOST")
DB_USER = os.getenv("MYSQLUSER")
DB_PASSWORD = os.getenv("MYSQLPASSWORD")
DB_NAME = os.getenv("MYSQLDATABASE")

def get_connection():
    return pymysql.connect(host=DB_HOST, user=DB_USER, password=DB_PASSWORD, database=DB_NAME)

def init_db():
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
    CREATE TABLE IF NOT EXISTS users (
        phone VARCHAR(20) PRIMARY KEY,
        expiry DATE,
        in_use BOOLEAN DEFAULT FALSE,
        used_at DATETIME,
        emergency_used DATE
    );
    """)
    conn.commit()
    cur.close()
    conn.close()

@app.route("/admin")
def admin():
    phone = request.args.get("phone")
    if phone != OWNER_PHONE:
        return "Unauthorized", 403

    conn = get_connection()
    cur = conn.cursor()
    today = datetime.today().date()

    cur.execute("SELECT phone, expiry FROM users")
    users = cur.fetchall()
    expired = [u for u in users if u[1] < today]
    active = [u for u in users if u[1] >= today]

    categorized = {"daily": [], "weekly": [], "monthly": [], "six_month": []}
    for phone, expiry in active:
        days_left = (expiry - today).days
        if days_left <= 1:
            categorized["daily"].append(phone)
        elif days_left <= 7:
            categorized["weekly"].append(phone)
        elif days_left <= 31:
            categorized["monthly"].append(phone)
        else:
            categorized["six_month"].append(phone)

    cur.close()
    conn.close()
    return render_template("admin.html", users=users, expired=expired, categorized=categorized)

@app.route('/check', methods=['POST'])
def check():
    phone = request.form['phone']

    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT expiry FROM users WHERE phone = %s", (phone,))
    result = cur.fetchone()
    today = datetime.today().date()

    if phone == OWNER_PHONE:
        return admin()

    if result:
        expiry = result[0]
        if expiry >= today:
            # Valid subscription
            return render_template('active.html', phone=phone, expiry=expiry)
        else:
            # Expired subscription
            return render_template('expired.html', phone=phone)
    else:
        # New customer
        return render_template('new_customer.html', phone=phone)

@app.route('/emergency', methods=['POST'])
def emergency():
    phone = request.form['phone']
    today = datetime.today().date()

    conn = get_connection()
    cur = conn.cursor()

    cur.execute("SELECT expiry, emergency_used FROM users WHERE phone = %s", (phone,))
    user = cur.fetchone()
    if not user:
        return "No such user", 404

    expiry, emergency_used = user
    if expiry < today:
        return "Subscription expired", 403

    if emergency_used == today:
        return "Already used emergency today", 403

    # Update emergency_used and trigger machine
    cur.execute("UPDATE users SET emergency_used = %s WHERE phone = %s", (today, phone))
    conn.commit()
    cur.close()
    conn.close()

    # Call virtual trigger
    try:
        requests.get(TRIGGER_URL)
    except:
        pass

    return "Emergency session activated for 45 mins"
