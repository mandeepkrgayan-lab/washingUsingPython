from flask import Flask, render_template, request, jsonify
import os
import psycopg2
from datetime import datetime, timedelta
import threading

app = Flask(__name__)

DB_URL = os.getenv('DATABASE_URL')  # Set this in Render
TRIGGER_URL = "https://www.virtualsmarthome.xyz/url_routine_trigger/activate.php?trigger=d613829d-a350-476b-b520-15e33c3d39f5&token=965a8bd9-75b5-4963-99dc-c2bc65767c17&response=html"

def get_db_connection():
    return psycopg2.connect(DB_URL, sslmode='require')

def init_db():
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("""
    CREATE TABLE IF NOT EXISTS users (
        phone TEXT PRIMARY KEY,
        expiry DATE,
        in_use BOOLEAN DEFAULT FALSE,
        used_at TIMESTAMP
    );
    """)
    conn.commit()
    cur.close()
    conn.close()

@app.route("/")
def home():
    return render_template("index.html")

@app.route("/check")
def check():
    phone = request.args.get("phone")
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT expiry, in_use, used_at FROM users WHERE phone=%s", (phone,))
    row = cur.fetchone()

    # Check if someone else is using
    cur.execute("SELECT phone, used_at FROM users WHERE in_use=TRUE")
    active_user = cur.fetchone()

    message = ""
    action = ""
    today = datetime.today().date()

    if row:
        expiry, in_use, used_at = row
        if expiry >= today:
            if active_user and active_user[0] != phone:
                elapsed = datetime.now() - active_user[1]
                remaining = 1800 - elapsed.total_seconds()
                message = f"Another user is using it. Time left: {int(remaining // 60)} min"
            elif in_use:
                message = "Machine is currently ON."
            else:
                message = '<button onclick="turnOn()">Turn On</button>'
        else:
            message = "Subscription expired. Choose a plan."
            action = "pay"
    else:
        message = "No subscription found. Choose a plan."
        action = "pay"

    cur.close()
    conn.close()
    return jsonify({"message": message, "action": action})

@app.route("/update_expiry", methods=["POST"])
def update_expiry():
    data = request.get_json()
    phone = data["phone"]
    days = data["days"]
    expiry = datetime.today().date() + timedelta(days=days)

    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("INSERT INTO users (phone, expiry) VALUES (%s, %s) ON CONFLICT (phone) DO UPDATE SET expiry = EXCLUDED.expiry", (phone, expiry))
    conn.commit()
    cur.close()
    conn.close()
    return "Updated"

@app.route("/turn_on", methods=["POST"])
def turn_on():
    phone = request.json.get("phone")
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("UPDATE users SET in_use=TRUE, used_at=NOW() WHERE phone=%s", (phone,))
    conn.commit()
    cur.close()
    conn.close()

    # Auto-turn-off in 30 mins
    def turn_off():
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("UPDATE users SET in_use=FALSE WHERE phone=%s", (phone,))
        conn.commit()
        cur.close()
        conn.close()

    threading.Timer(1800, turn_off).start()
    try:
        import requests
        requests.get(TRIGGER_URL)
    except:
        pass
    return "Activated"

if __name__ == "__main__":
    init_db()
    app.run(host="0.0.0.0", port=10000)
