from flask import Flask, render_template, request, jsonify
import pymysql
from datetime import datetime, timedelta
import threading
import os
import requests

app = Flask(__name__)

# MySQL config from environment
DB_HOST = os.getenv("MYSQLHOST")
DB_USER = os.getenv("MYSQLUSER")
DB_PASSWORD = os.getenv("MYSQLPASSWORD")
DB_NAME = os.getenv("MYSQLDATABASE")

TRIGGER_URL = "https://www.virtualsmarthome.xyz/url_routine_trigger/activate.php?trigger=d613829d-a350-476b-b520-15e33c3d39f5&token=965a8bd9-75b5-4963-99dc-c2bc65767c17&response=html"
FORCE_OFF_URL = "https://www.virtualsmarthome.xyz/url_routine_trigger/activate.php?trigger=f7fdcb3b-c16d-4601-90e6-f0729cc038ac&token=3ac706a2-1e9a-4b07-90ef-116be4142ef7&response=json"

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
        used_at DATETIME
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
    conn = get_connection()
    cur = conn.cursor()

    # Auto reset in_use if any user has crossed 30 minutes
    cur.execute("SELECT phone, used_at FROM users WHERE in_use=TRUE")
    active_user = cur.fetchone()
    if active_user:
        phone_active, used_at = active_user
        elapsed = datetime.now() - used_at
        if elapsed.total_seconds() > 1800:
            cur.execute("UPDATE users SET in_use=FALSE, used_at=NULL WHERE phone=%s", (phone_active,))
            conn.commit()
            active_user = None

    cur.execute("SELECT expiry, in_use, used_at FROM users WHERE phone=%s", (phone,))
    row = cur.fetchone()

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
                elapsed = datetime.now() - used_at
                remaining = 1800 - elapsed.total_seconds()
                if remaining > 0:
                    message = f"Machine is currently ON.<br>Time remaining: {int(remaining // 60)} min"
                else:
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

    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
    INSERT INTO users (phone, expiry) VALUES (%s, %s)
    ON DUPLICATE KEY UPDATE expiry=%s
    """, (phone, expiry, expiry))
    conn.commit()
    cur.close()
    conn.close()
    return "Updated"

@app.route("/turn_on", methods=["POST"])
def turn_on():
    phone = request.json.get("phone")
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("UPDATE users SET in_use=TRUE, used_at=NOW() WHERE phone=%s", (phone,))
    conn.commit()
    cur.close()
    conn.close()

    def turn_off():
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("UPDATE users SET in_use=FALSE, used_at=NULL WHERE phone=%s", (phone,))
        conn.commit()
        cur.close()
        conn.close()

    threading.Timer(1800, turn_off).start()

    try:
        requests.get(TRIGGER_URL)
    except:
        pass

    return "Activated"

@app.route("/force_turn_off", methods=["POST"])
def force_turn_off():
    try:
        requests.get(FORCE_OFF_URL)
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("UPDATE users SET in_use=FALSE, used_at=NULL WHERE in_use=TRUE")
        conn.commit()
        cur.close()
        conn.close()
        return "Force Turned Off"
    except Exception as e:
        return str(e), 500
from flask import session, redirect, url_for

app.secret_key = 'mandeep'  # Required for sessions

@app.route("/admin", methods=["GET", "POST"])
def admin():
    if request.method == "POST":
        user = request.form.get("username")
        pwd = request.form.get("password")
        if user == "admin" and pwd == "admin123":  # Change this for security
            session['admin'] = True
            return redirect("/dashboard")
        else:
            return render_template("admin_login.html", error="Invalid credentials")
    return render_template("admin_login.html")

@app.route("/dashboard")
def dashboard():
    if not session.get('admin'):
        return redirect("/admin")
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT phone, expiry, in_use, used_at FROM users")
    users = cur.fetchall()
    cur.close()
    conn.close()
    return render_template("admin_dashboard.html", users=users)

@app.route("/update_user", methods=["POST"])
def update_user():
    if not session.get('admin'):
        return redirect("/admin")
    phone = request.form.get("phone")
    new_expiry = request.form.get("new_expiry")
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("UPDATE users SET expiry=%s WHERE phone=%s", (new_expiry, phone))
    conn.commit()
    cur.close()
    conn.close()
    return redirect("/dashboard")

@app.route("/emergency", methods=["POST"])
def emergency():
    phone = request.json.get("phone")
    today = datetime.today().date()

    conn = get_connection()
    cur = conn.cursor()

    # Check if user exists and is active
    cur.execute("SELECT expiry, emergency_used_date FROM users WHERE phone=%s", (phone,))
    row = cur.fetchone()
    if not row:
        return "User not found", 404

    expiry, emergency_used_date = row
    if expiry < today:
        return "Subscription expired", 403

    if emergency_used_date == today:
        return "Emergency already used today", 403

    # Mark emergency as used
    cur.execute(
        "UPDATE users SET in_use=TRUE, used_at=NOW(), emergency_used_date=%s WHERE phone=%s",
        (today, phone)
    )
    conn.commit()
    cur.close()
    conn.close()

    try:
        requests.get(TRIGGER_URL)
    except:
        pass

    return "Emergency Activated", 200

@app.route("/add_customer", methods=["POST"])
def add_customer():
    data = request.json
    phone = data.get("phone")
    expiry = data.get("expiry")

    if not phone or not expiry:
        return "Phone and expiry required", 400

    conn = get_connection()
    cur = conn.cursor()

    try:
        cur.execute("""
            INSERT INTO users (phone, expiry, uses_today, last_used, in_use, emergency_used_date)
            VALUES (%s, %s, 0, NULL, FALSE, NULL)
            ON DUPLICATE KEY UPDATE expiry = VALUES(expiry)
        """, (phone, expiry))
        conn.commit()
    except Exception as e:
        conn.rollback()
        return str(e), 500
    finally:
        cur.close()
        conn.close()

    return "Customer added or updated successfully", 200



if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
