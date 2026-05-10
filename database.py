import os
import sqlite3
from datetime import datetime
from werkzeug.security import generate_password_hash
from config import DATABASE_PATH


def get_connection():
    os.makedirs(os.path.dirname(DATABASE_PATH), exist_ok=True)
    conn = sqlite3.connect(DATABASE_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "CREATE TABLE IF NOT EXISTS donors ("
        "id INTEGER PRIMARY KEY AUTOINCREMENT, "
        "tracking_id TEXT UNIQUE, "
        "donor_name TEXT, "
        "phone TEXT, "
        "item_type TEXT, "
        "condition TEXT, "
        "photo_hash TEXT, "
        "photo_filename TEXT, "
        "created_at TEXT"
        ")"
    )
    cursor.execute(
        "CREATE TABLE IF NOT EXISTS recipients ("
        "id INTEGER PRIMARY KEY AUTOINCREMENT, "
        "tracking_id TEXT, "
        "recipient_name TEXT, "
        "recipient_code TEXT, "
        "address TEXT, "
        "confirmed_at TEXT"
        ")"
    )
    cursor.execute(
        "CREATE TABLE IF NOT EXISTS users ("
        "id INTEGER PRIMARY KEY AUTOINCREMENT, "
        "username TEXT UNIQUE, "
        "password_hash TEXT, "
        "role TEXT, "
        "created_at TEXT"
        ")"
    )
    now = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
    cursor.execute(
        "INSERT OR IGNORE INTO users (username, password_hash, role, created_at) VALUES (?, ?, ?, ?)",
        ("admin", generate_password_hash("admin123"), "admin", now),
    )
    cursor.execute(
        "INSERT OR IGNORE INTO users (username, password_hash, role, created_at) VALUES (?, ?, ?, ?)",
        ("donor", generate_password_hash("donor123"), "donor", now),
    )
    cursor.execute(
        "INSERT OR IGNORE INTO users (username, password_hash, role, created_at) VALUES (?, ?, ?, ?)",
        ("recipient", generate_password_hash("recipient123"), "recipient", now),
    )
    conn.commit()
    conn.close()


def save_user(username, password_hash, role):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO users (username, password_hash, role, created_at) VALUES (?, ?, ?, ?)",
        (username, password_hash, role, datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")),
    )
    conn.commit()
    conn.close()


def get_user_by_username(username):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE username = ?", (username,))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None


def save_donor(tracking_id, donor_name, phone, item_type, condition, photo_hash, photo_filename):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT OR IGNORE INTO donors (tracking_id, donor_name, phone, item_type, condition, photo_hash, photo_filename, created_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?)"
        , (tracking_id, donor_name, phone, item_type, condition, photo_hash, photo_filename, datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"))
    )
    conn.commit()
    conn.close()


def get_donor_by_tracking(tracking_id):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM donors WHERE tracking_id = ?", (tracking_id,))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None


def save_recipient(tracking_id, recipient_name, recipient_code, address):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO recipients (tracking_id, recipient_name, recipient_code, address, confirmed_at) "
        "VALUES (?, ?, ?, ?, ?)"
        , (tracking_id, recipient_name, recipient_code, address, datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"))
    )
    conn.commit()
    conn.close()


def get_recipient_by_tracking(tracking_id):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM recipients WHERE tracking_id = ? ORDER BY id DESC", (tracking_id,))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None
