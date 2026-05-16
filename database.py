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
        "role TEXT, "  # 用户角色：admin, donor, recipient, institution, warehouse, courier
        "org_name TEXT, "  # 机构名称（仅当 role 是 institution/warehouse/courier 时使用）
        "approved INTEGER DEFAULT 1, "  # 账号是否启用（兼容旧 institution 审批字段）
        "created_at TEXT"  # 创建时间
        ")"
    )
    now = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
    # 兼容旧数据库：确保 users 表包含 org_name 与 approved 列
    cursor.execute("PRAGMA table_info(users)")
    cols = [r[1] for r in cursor.fetchall()]
    if "org_name" not in cols:
        try:
            cursor.execute("ALTER TABLE users ADD COLUMN org_name TEXT")
        except Exception:
            pass
    if "approved" not in cols:
        try:
            cursor.execute("ALTER TABLE users ADD COLUMN approved INTEGER DEFAULT 1")
        except Exception:
            pass
    conn.commit()

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
    # 插入默认机构员工用户
    cursor.execute(
        "INSERT OR IGNORE INTO users (username, password_hash, role, org_name, created_at) VALUES (?, ?, ?, ?, ?)",
        ("staff", generate_password_hash("staff123"), "institution", "机构员工", now),
    )
    # 插入默认中转仓库用户
    cursor.execute(
        "INSERT OR IGNORE INTO users (username, password_hash, role, org_name, created_at) VALUES (?, ?, ?, ?, ?)",
        ("warehouse", generate_password_hash("warehouse123"), "warehouse", "仓库", now),
    )
    # 插入默认快递站用户
    cursor.execute(
        "INSERT OR IGNORE INTO users (username, password_hash, role, org_name, created_at) VALUES (?, ?, ?, ?, ?)",
        ("courier", generate_password_hash("courier123"), "courier", "快递站", now),
    )
    conn.commit()
    conn.close()

    # 创建机构表（用于登记运输中转机构）并兼容旧库
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "CREATE TABLE IF NOT EXISTS institutions ("
        "id INTEGER PRIMARY KEY AUTOINCREMENT, "
        "name TEXT UNIQUE, "
        "code TEXT, "
        "description TEXT, "
        "active INTEGER DEFAULT 1, "
        "created_at TEXT"
        ")"
    )
    conn.commit()
    # 默认节点：仓库与快递站
    add_institution("仓库", "warehouse", "中转仓库")
    add_institution("快递站", "courier", "配送快递站")
    # 兼容旧 donors 表：确保包含 assigned_org 列（存储机构名称）
    cursor.execute("PRAGMA table_info(donors)")
    cols = [r[1] for r in cursor.fetchall()]
    if "assigned_org" not in cols:
        try:
            cursor.execute("ALTER TABLE donors ADD COLUMN assigned_org TEXT")
        except Exception:
            pass
    # 新增兼容列：assigned_courier, assigned_warehouse, assigned_recipient
    if "assigned_courier" not in cols:
        try:
            cursor.execute("ALTER TABLE donors ADD COLUMN assigned_courier TEXT")
        except Exception:
            pass
    if "assigned_warehouse" not in cols:
        try:
            cursor.execute("ALTER TABLE donors ADD COLUMN assigned_warehouse TEXT")
        except Exception:
            pass
    if "assigned_recipient" not in cols:
        try:
            cursor.execute("ALTER TABLE donors ADD COLUMN assigned_recipient TEXT")
        except Exception:
            pass
    conn.commit()
    conn.close()


def save_user(username, password_hash, role, org_name=None, approved=1):
    """保存新用户到数据库。支持机构账号的 org_name 与审批标志。"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO users (username, password_hash, role, org_name, approved, created_at) VALUES (?, ?, ?, ?, ?, ?)",
        (
            username,
            password_hash,
            role,
            org_name,
            approved,
            datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"),
        ),
    )
    conn.commit()
    conn.close()


def get_pending_institutions():
    """返回待审批的机构账号列表（approved=0）。"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE role = 'institution' AND approved = 0 ORDER BY created_at ASC")
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_institutions():
    """返回已注册并启用的机构列表，用于注册时下拉选择。"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM institutions WHERE active = 1 ORDER BY name ASC")
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]


def add_institution(name, code=None, description=None):
    """管理员添加机构到机构表。"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT OR IGNORE INTO institutions (name, code, description, created_at) VALUES (?, ?, ?, ?)",
        (name, code, description, datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")),
    )
    conn.commit()
    conn.close()


def approve_institution(username):
    """管理员将机构账号设置为已审批通过（approved=1）。"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET approved = 1 WHERE username = ? AND role = 'institution'", (username,))
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


def delete_user(username):
    """删除指定用户名的用户账号。"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM users WHERE username = ?", (username,))
    cursor.execute(
        "UPDATE donors SET assigned_courier = NULL WHERE assigned_courier = ?",
        (username,),
    )
    cursor.execute(
        "UPDATE donors SET assigned_warehouse = NULL WHERE assigned_warehouse = ?",
        (username,),
    )
    cursor.execute(
        "UPDATE donors SET assigned_recipient = NULL WHERE assigned_recipient = ?",
        (username,),
    )
    conn.commit()
    conn.close()


def get_users_by_role(role):
    """返回指定角色的用户列表。"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE role = ? ORDER BY created_at ASC", (role,))
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_all_users():
    """返回系统中所有用户（按创建时间排序）。"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users ORDER BY created_at ASC")
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]


def save_donor(tracking_id, donor_name, phone, item_type, condition, photo_hash, photo_filename):
    """保存捐赠者信息到数据库。"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT OR IGNORE INTO donors (tracking_id, donor_name, phone, item_type, condition, photo_hash, photo_filename, created_at, assigned_org, assigned_courier, assigned_warehouse, assigned_recipient) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)"
        , (tracking_id, donor_name, phone, item_type, condition, photo_hash, photo_filename, datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"), None, None, None, None)
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


def assign_donor_to_org(tracking_id, org_name):
    """将指定跟踪 ID 的捐赠记录分配给机构（存储机构名称）。"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE donors SET assigned_org = ? WHERE tracking_id = ?", (org_name, tracking_id))
    conn.commit()
    conn.close()


def assign_donor_to_courier(tracking_id, courier_username):
    """将指定跟踪 ID 的捐赠记录分配给快递员（用户名），并清除仓库/受赠方分配。"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "UPDATE donors SET assigned_courier = ?, assigned_warehouse = NULL, assigned_recipient = NULL WHERE tracking_id = ?",
        (courier_username, tracking_id),
    )
    conn.commit()
    conn.close()


def assign_donor_to_recipient(tracking_id, recipient_username):
    """将指定跟踪 ID 的捐赠记录分配给受赠者，并清除快递员/仓库分配。"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "UPDATE donors SET assigned_recipient = ?, assigned_courier = NULL, assigned_warehouse = NULL WHERE tracking_id = ?",
        (recipient_username, tracking_id),
    )
    conn.commit()
    conn.close()


def clear_donor_assignment(tracking_id):
    """清除指定跟踪 ID 的快递员/仓库/受赠方分配，使物品从门户视图中消失。"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "UPDATE donors SET assigned_courier = NULL, assigned_warehouse = NULL, assigned_recipient = NULL WHERE tracking_id = ?",
        (tracking_id,),
    )
    conn.commit()
    conn.close()


def assign_donor_to_warehouse(tracking_id, warehouse_name):
    """将指定跟踪 ID 的捐赠记录分配给仓库，并清除快递员分配。"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "UPDATE donors SET assigned_warehouse = ?, assigned_courier = NULL WHERE tracking_id = ?",
        (warehouse_name, tracking_id),
    )
    conn.commit()
    conn.close()


def get_donors_by_courier(courier_username):
    """返回分配给指定快递员的捐赠记录列表。"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM donors WHERE assigned_courier = ? ORDER BY created_at DESC", (courier_username,))
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_donors_by_warehouse(warehouse_name):
    """返回分配给指定仓库的捐赠记录列表。"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM donors WHERE assigned_warehouse = ? ORDER BY created_at DESC", (warehouse_name,))
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_donors_by_recipient(recipient_username):
    """返回分配给指定受赠者的捐赠记录列表。"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM donors WHERE assigned_recipient = ? ORDER BY created_at DESC", (recipient_username,))
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_donors_by_org(org_name):
    """返回分配给指定机构的捐赠记录列表。"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM donors WHERE assigned_org = ? ORDER BY created_at DESC", (org_name,))
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]


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
