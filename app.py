from flask import Flask, render_template, request, jsonify
from datetime import datetime, timedelta
import psycopg2
import threading
import time
import os

app = Flask(__name__)

# PostgreSQL DB config from Render Environment Variables
DB_URL = os.environ.get("DATABASE_URL")

def get_db_connection():
    return psycopg2.connect(DB_URL, sslmode='require')

# Initialize DB
def init_db():
    conn = get_db_connection()
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS subscriptions (
            phone TEXT PRIMARY KEY,
            expiry DATE
        )
    ''')
    c.execute('''
        CREATE TABLE IF NOT EXISTS usage (
            id SERIAL PRIMARY KEY,
            inUse TEXT DEFAULT 'false',
            startTime TIMESTAMP
        )
    ''')
    c.execute("SELECT COUNT(*) FROM usage")
    if c.fetchone()[0] == 0:
        c.execute("INSERT INTO usage (inUse, startTime) VALUES ('false', NULL)")
    conn.commit()
    conn.close()

init_db()

@app.route('/check', methods=['POST'])
def check_subscription():
    phone = request.form['phone']
    today = datetime.today().date()

    conn = get_db_connection()
    c = conn.cursor()
    c.execute("SELECT expiry FROM subscriptions WHERE phone = %s", (phone,))
    result = c.fetchone()

    c.execute("SELECT inUse, startTime FROM usage LIMIT 1")
    usage = c.fetchone()
    conn.close()

    if usage[0] == "true":
        elapsed = (datetime.now() - usage[1]).seconds
        remaining = 1800 - elapsed
        return jsonify({"status": "inUse", "remaining": remaining // 60})

    if result:
        expiry = result[0]
        if expiry >= today:
            return jsonify({"status": "active"})
        else:
            return jsonify({"status": "expired"})
    else:
        return jsonify({"status": "new"})

@app.route('/update', methods=['POST'])
def update_subscription():
    phone = request.form['phone']
    days = int(request.form['days'])
    expiry = (datetime.today() + timedelta(days=days)).date()

    conn = get_db_connection()
    c = conn.cursor()
    c.execute("""
        INSERT INTO subscriptions (phone, expiry) 
        VALUES (%s, %s)
        ON CONFLICT (phone) DO UPDATE SET expiry = EXCLUDED.expiry
    """, (phone, expiry))
    conn.commit()
    conn.close()

    return jsonify({"status": "updated"})

@app.route('/turnon', methods=['POST'])
def turn_on():
    threading.Thread(target=auto_reset_inuse).start()
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("UPDATE usage SET inUse = 'true', startTime = %s WHERE id = 1", (datetime.now(),))
    conn.commit()
    conn.close()
    return jsonify({"url": "https://www.virtualsmarthome.xyz/url_routine_trigger/activate.php?trigger=d613829d-a350-476b-b520-15e33c3d39f5&token=965a8bd9-75b5-4963-99dc-c2bc65767c17&response=html"})

def auto_reset_inuse():
    time.sleep(1800)
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("UPDATE usage SET inUse = 'false', startTime = NULL WHERE id = 1")
    conn.commit()
    conn.close()

if __name__ == '__main__':
    app.run(debug=True)
