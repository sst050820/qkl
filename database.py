import os
import sqlite3
from datetime import datetime
from werkzeug.security import generate_password_hash
from config import DATABASE_PATH


def get_connection():
    """获取数据库连接。

    确保数据库目录存在，并返回一个配置了行工厂的 SQLite 连接。
    """
    os.makedirs(os.path.dirname(DATABASE_PATH), exist_ok=True)
    conn = sqlite3.connect(DATABASE_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """初始化数据库，创建必要的表并插入默认用户。"""
    conn = get_connection()
    cursor = conn.cursor()
    # 创建捐赠者表，用于存储捐赠物品信息
    cursor.execute(
        "CREATE TABLE IF NOT EXISTS donors ("
        "id INTEGER PRIMARY KEY AUTOINCREMENT, "
        "tracking_id TEXT UNIQUE, "  # 唯一跟踪 ID
        "donor_name TEXT, "  # 捐赠者姓名
        "phone TEXT, "  # 联系电话
        "item_type TEXT, "  # 物品类型
        "condition TEXT, "  # 物品状况
        "photo_hash TEXT, "  # 照片哈希值，用于验证照片完整性
        "photo_filename TEXT, "  # 照片文件名
        "created_at TEXT"  # 创建时间
        ")"
    )
    # 创建受赠者表，用于存储签收信息
    cursor.execute(
        "CREATE TABLE IF NOT EXISTS recipients ("
        "id INTEGER PRIMARY KEY AUTOINCREMENT, "
        "tracking_id TEXT, "  # 关联的跟踪 ID
        "recipient_name TEXT, "  # 受赠者姓名
        "recipient_code TEXT, "  # 受赠者编号
        "address TEXT, "  # 地址
        "confirmed_at TEXT"  # 确认签收时间
        ")"
    )
    # 创建用户表，用于存储系统用户
    cursor.execute(
        "CREATE TABLE IF NOT EXISTS users ("
        "id INTEGER PRIMARY KEY AUTOINCREMENT, "
        "username TEXT UNIQUE, "  # 唯一用户名
        "password_hash TEXT, "  # 密码哈希
        "role TEXT, "  # 用户角色：admin, donor, recipient
        "created_at TEXT"  # 创建时间
        ")"
    )
    now = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
    # 插入默认管理员用户
    cursor.execute(
        "INSERT OR IGNORE INTO users (username, password_hash, role, created_at) VALUES (?, ?, ?, ?)",
        ("admin", generate_password_hash("admin123"), "admin", now),
    )
    # 插入默认捐赠者用户
    cursor.execute(
        "INSERT OR IGNORE INTO users (username, password_hash, role, created_at) VALUES (?, ?, ?, ?)",
        ("donor", generate_password_hash("donor123"), "donor", now),
    )
    # 插入默认受赠者用户
    cursor.execute(
        "INSERT OR IGNORE INTO users (username, password_hash, role, created_at) VALUES (?, ?, ?, ?)",
        ("recipient", generate_password_hash("recipient123"), "recipient", now),
    )
    conn.commit()
    conn.close()


def save_user(username, password_hash, role):
    """保存新用户到数据库。"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO users (username, password_hash, role, created_at) VALUES (?, ?, ?, ?)",
        (username, password_hash, role, datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")),
    )
    conn.commit()
    conn.close()


def get_user_by_username(username):
    """根据用户名查询用户。"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE username = ?", (username,))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None


def save_donor(tracking_id, donor_name, phone, item_type, condition, photo_hash, photo_filename):
    """保存捐赠者信息到数据库。"""
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
    """根据跟踪 ID 查询捐赠者信息。"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM donors WHERE tracking_id = ?", (tracking_id,))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None


def save_recipient(tracking_id, recipient_name, recipient_code, address):
    """保存受赠者签收信息到数据库。"""
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
    """根据跟踪 ID 查询受赠者信息，返回最新的记录。"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM recipients WHERE tracking_id = ? ORDER BY id DESC", (tracking_id,))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None
