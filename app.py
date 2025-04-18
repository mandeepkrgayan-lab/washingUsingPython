from flask import Flask, render_template, request, redirect
import mysql.connector
from datetime import datetime, timedelta
import os

app = Flask(__name__)

def get_connection():
    return mysql.connector.connect(
        host=os.environ.get("MYSQL_HOST", "localhost"),
        user=os.environ.get("MYSQL_USER", "youruser"),
        password=os.environ.get("MYSQL_PASSWORD", "yourpassword"),
        database=os.environ.get("MYSQL_DB", "yourdbname")
    )

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/check", methods=["POST"])
def check():
    phone = request.form["phone"]
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT expiry FROM subscriptions WHERE phone = %s", (phone,))
    result = cursor.fetchone()

    cursor.execute("SELECT in_use, end_time FROM machine_status WHERE id = 1")
    machine = cursor.fetchone()

    now = datetime.now()

    if machine["in_use"] and machine["end_time"] > now:
        remaining = int((machine["end_time"] - now).total_seconds() / 60)
        return render_template("in_use.html", minutes=remaining)

    if result and result["expiry"] >= now.date():
        return render_template("active.html", phone=phone)
    else:
        return render_template("payment.html", phone=phone)

@app.route("/post_payment", methods=["POST"])
def post_payment():
    phone = request.form["phone"]
    plan = request.form["plan"]
    days = {"daily": 1, "weekly": 7, "monthly": 30}[plan]
    expiry = datetime.today().date() + timedelta(days=days)

    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("INSERT INTO subscriptions (phone, expiry) VALUES (%s, %s) ON DUPLICATE KEY UPDATE expiry = %s",
                   (phone, expiry, expiry))
    conn.commit()
    cursor.close()
    conn.close()
    return render_template("post_payment.html", phone=phone, new_expiry=expiry)

@app.route("/turn_on", methods=["POST"])
def turn_on():
    phone = request.form["phone"]
    end_time = datetime.now() + timedelta(minutes=30)

    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE machine_status SET in_use = TRUE, end_time = %s WHERE id = 1", (end_time,))
    conn.commit()
    cursor.close()
    conn.close()

    import requests
    requests.get("https://www.virtualsmarthome.xyz/url_routine_trigger/activate.php?trigger=d613829d-a350-476b-b520-15e33c3d39f5&token=965a8bd9-75b5-4963-99dc-c2bc65767c17&response=html")

    return render_template("started.html", phone=phone)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
