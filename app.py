import hashlib
import os
import uuid
from functools import wraps
from flask import Flask, flash, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash
from werkzeug.utils import secure_filename
from config import (
    ALLOWED_EXTENSIONS,
    DATABASE_PATH,
    FABRIC_ENABLED,
    SECRET_KEY,
    UPLOAD_FOLDER,
)
from blockchain import Blockchain
from contracts import STATES, build_event, next_state, validate_transition
from database import (
    get_donor_by_tracking,
    get_recipient_by_tracking,
    get_user_by_username,
    get_users_by_role,
    get_all_users,
    delete_user,
    restore_user,
    purge_user,
    init_db,
    save_donor,
    save_recipient,
    save_user,
    get_institutions,
    assign_donor_to_org,
    get_donors_by_org,
    assign_donor_to_courier,
    assign_donor_to_warehouse,
    assign_donor_to_recipient,
    clear_donor_assignment,
    get_donors_by_courier,
    get_donors_by_warehouse,
    get_donors_by_recipient,
)
from fabric_client import FabricClient

# 确保上传目录存在
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# 创建 Flask 应用实例
app = Flask(__name__)
app.config["SECRET_KEY"] = SECRET_KEY
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
app.config["MAX_CONTENT_LENGTH"] = 5 * 1024 * 1024  # 限制上传文件大小为 5MB

# 默认用户账户，用于向后兼容
USER_ACCOUNTS = {
    "admin": {"password": "admin123", "role": "admin"},
    "donor": {"password": "donor123", "role": "donor"},
    "recipient": {"password": "recipient123", "role": "recipient"},
    "staff": {"password": "staff123", "role": "institution"},
    "warehouse": {"password": "warehouse123", "role": "warehouse"},
    "courier": {"password": "courier123", "role": "courier"},
}

INSTITUTION_ROLE = "institution"
WAREHOUSE_ROLE = "warehouse"
COURIER_ROLE = "courier"
ORG_INSTITUTION = "机构员工"
ORG_WAREHOUSE = "仓库"
ORG_COURIER = "快递站"
ROLE_LABELS = {
    "donor": "捐赠方",
    "recipient": "受赠方",
    "institution": "机构员工",
    "warehouse": "中转仓库",
    "courier": "快递站",
    "admin": "管理员",
}

# 初始化数据库
init_db()

# 初始化 Fabric 客户端和运行时链实例
fabric_client = FabricClient() if FABRIC_ENABLED else None
fabric_ready = fabric_client.is_ready() if fabric_client else False
if fabric_client and fabric_ready:
    chain = fabric_client
else:
    chain = Blockchain()
    if fabric_client and not fabric_ready:
        app.logger.warning("Fabric client not ready; falling back to local Blockchain.")


def allowed_file(filename):
    """检查文件扩展名是否在允许列表中。"""
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


def compute_hash(path):
    """计算文件的 SHA-256 哈希值，用于验证文件完整性。"""
    hasher = hashlib.sha256()
    with open(path, "rb") as file:
        while True:
            chunk = file.read(8192)  # 分块读取，提高效率
            if not chunk:
                break
            hasher.update(chunk)
    return hasher.hexdigest()


def mask_name(name):
    """对捐赠者姓名进行脱敏处理（简化版，用于前端显示）。"""
    if not name:
        return "匿名捐赠"
    return name[0] + "**" if len(name.strip()) > 1 else "*"


def summarize_trackings():
    """汇总所有跟踪 ID 的最新区块信息。"""
    summary = {}
    for block in chain.chain:
        data = block.data
        tracking_id = data.get("tracking_id")
        if tracking_id:
            summary[tracking_id] = block  # 保留最新的区块（遍历顺序）
    return summary


def get_latest_event(tracking_id):
    """获取指定跟踪 ID 的最新事件。"""
    return chain.get_latest_item(tracking_id)


def donor_status(tracking_id):
    """返回链上指定跟踪 ID 的最新状态字符串（若无则返回 None）。"""
    latest = get_latest_event(tracking_id)
    if not latest:
        return None
    # Fabric proxy 与本地区块返回结构可能不同，尽量兼容
    if isinstance(latest, dict):
        # 本地链：item dict 包含 'event' 键
        if latest.get("event") and isinstance(latest.get("event"), dict):
            return latest["event"].get("status")
        # Fabric proxy 可能直接返回字段
        return latest.get("status") or latest.get("event", {}).get("status")
    return None


def build_photo_url(donor):
    """根据捐赠者信息构建照片 URL。"""
    if donor and donor.get("photo_filename"):
        return url_for("static", filename=f"uploads/{donor['photo_filename']}")
    return None


def get_chain_mode():
    """返回当前链运行模式标签。"""
    return "Fabric 链码" if isinstance(chain, FabricClient) else "本地模拟链"


def get_chain_status():
    """返回当前链模式和运行状态描述。"""
    if not FABRIC_ENABLED:
        return "Fabric 功能未启用，使用本地模拟链。"
    if fabric_client and fabric_ready:
        return f"Fabric 已启用，当前运行模式：{get_chain_mode()}。"
    if fabric_client and not fabric_ready:
        return "Fabric 已启用，但当前环境未就绪，已回退到本地模拟链。"
    return "Fabric 配置异常，使用本地模拟链。"


def format_chain_success(action: str) -> str:
    """格式化成功提示信息。"""
    return f"{action} 已成功写入 {get_chain_mode()}。"


def format_chain_failure(action: str, reason: str) -> str:
    """格式化失败提示信息。"""
    return f"{action} 写入 {get_chain_mode()} 失败：{reason}"


def commit_chain_event(event):
    """执行链写入操作，支持 FabricClient 和本地 Blockchain。"""
    result = chain.add_block(event)
    if isinstance(result, tuple) and len(result) == 2 and isinstance(result[0], bool):
        return result
    return True, f"{get_chain_mode()} 写入成功"


def get_chain_height():
    """返回当前链或账本的区块高度。"""
    if hasattr(chain, "get_block_height"):
        try:
            return chain.get_block_height()
        except Exception:
            pass
    try:
        return len(chain.chain) - 1
    except Exception:
        return None


def get_chain_valid():
    """返回当前链完整性校验状态。"""
    if hasattr(chain, "is_valid_chain"):
        try:
            return chain.is_valid_chain()
        except Exception:
            return False
    return False


def is_fabric_enabled():
    """判断当前链实例是否为 FabricClient。"""
    return isinstance(chain, FabricClient)


def authenticate_user(username, password):
    """验证用户登录，支持数据库用户和默认用户。"""
    # 首先尝试从数据库查找用户
    user = get_user_by_username(username)
    if user:
        if check_password_hash(user["password_hash"], password):
            return {"username": user["username"], "role": user["role"], "approved": int(user.get("approved", 1)), "org_name": user.get("org_name")}
        return None

    # 如果数据库中没有，尝试默认账户
    account = USER_ACCOUNTS.get(username)
    if not account:
        return None
    if password == account["password"]:
        return {"username": username, "role": account["role"]}
    return None


def login_required(required_role=None):
    """装饰器：要求用户登录，并可选检查角色权限。"""
    def decorator(view):
        @wraps(view)
        def wrapped_view(*args, **kwargs):
            if not session.get("logged_in"):
                flash("请先登录。", "warning")
                return redirect(url_for("login", next=request.path))
            if required_role:
                user_role = session.get("role")
                # 支持传入字符串或可迭代的角色集合
                if isinstance(required_role, (list, tuple, set)):
                    if user_role not in required_role:
                        flash("当前账号无权访问该页面。", "danger")
                        return redirect(url_for("index"))
                else:
                    if user_role != required_role:
                        flash("当前账号无权访问该页面。", "danger")
                        return redirect(url_for("index"))
            return view(*args, **kwargs)
        return wrapped_view
    return decorator


@app.context_processor
def inject_user():
    """Flask 上下文处理器：在所有模板中注入当前用户和链状态信息。"""
    return {
        "current_user": session.get("username"),
        "current_role": session.get("role"),
        "chain_mode": get_chain_mode(),
        "chain_status": get_chain_status(),
        "fabric_enabled": FABRIC_ENABLED,
        "fabric_ready": fabric_ready,
        "chain_height": get_chain_height(),
        "chain_valid": get_chain_valid(),
    }


def safe_redirect_target(target):
    """安全重定向目标验证，确保只重定向到内部路径。"""
    if target and target.startswith("/"):
        return target
    return url_for("index")


@app.route("/register", methods=["GET", "POST"])
def register():
    """用户注册路由。"""
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "").strip()
        confirm_password = request.form.get("confirm_password", "").strip()
        role = request.form.get("role", "donor").strip()
        if not username or not password or not confirm_password:
            flash("请填写完整注册信息。", "warning")
            return redirect(url_for("register"))
        if password != confirm_password:
            flash("两次输入的密码不一致。", "warning")
            return redirect(url_for("register"))
        if role not in ["donor", "recipient", INSTITUTION_ROLE, WAREHOUSE_ROLE, COURIER_ROLE]:
            role = "donor"
        if get_user_by_username(username) or username in USER_ACCOUNTS:
            flash("用户名已存在，请更换用户名。", "warning")
            return redirect(url_for("register"))
        password_hash = generate_password_hash(password)

        org_name = None
        if role == INSTITUTION_ROLE:
            org_name = ORG_INSTITUTION
        elif role == WAREHOUSE_ROLE:
            org_name = ORG_WAREHOUSE
        elif role == COURIER_ROLE:
            org_name = ORG_COURIER

        save_user(username, password_hash, role, org_name=org_name)
        session["logged_in"] = True
        session["username"] = username
        session["role"] = role
        session["org_name"] = org_name
        flash("注册成功，已自动登录。", "success")
        return redirect(url_for("user_portal"))

    return render_template("register.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    """用户登录路由，支持重定向到之前的页面。"""
    next_target = request.args.get("next", "")
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "").strip()
        next_target = request.form.get("next", "")
        user = authenticate_user(username, password)
        if user:
            session["logged_in"] = True
            session["username"] = user["username"]
            session["role"] = user["role"]
            # 如果数据库用户包含机构名称，保存到 session 以便在机构门户显示
            if user.get("org_name"):
                session["org_name"] = user.get("org_name")
            flash("登录成功。", "success")
            return redirect(safe_redirect_target(next_target))
        flash("用户名或密码错误。", "danger")
    return render_template("login.html", next=next_target)


@app.route("/logout")
def logout():
    """用户登出路由。"""
    session.clear()
    flash("已退出登录。", "info")
    return redirect(url_for("index"))


@app.route("/")
def index():
    """首页路由，显示捐赠物品概览和统计信息。"""
    summary = summarize_trackings()
    total_items = len(summary)
    status_count = {state: 0 for state in STATES}
    items = []
    for track_id, block in summary.items():
        data = block.data
        status = data.get("status")
        if status in status_count:
            status_count[status] += 1
        donor = get_donor_by_tracking(track_id)
        recipient = get_recipient_by_tracking(track_id)
        items.append(
            {
                "tracking_id": track_id,
                "status": status,
                "item_type": data.get("item_type", "未知"),
                "condition": data.get("condition", "未知"),
                "donor_name": data.get("donor_name", "匿名"),
                "updated_at": block.timestamp,
                "note": data.get("note", ""),
                "history": chain.get_item_history(track_id),
                "recipient": recipient,
                "photo_url": build_photo_url(donor),
            }
        )
    items.sort(key=lambda x: x["updated_at"], reverse=True)
    return render_template(
        "index.html",
        block_height=len(chain.chain) - 1,
        total_items=total_items,
        status_count=status_count,
        valid_chain=chain.is_valid_chain(),
        items=items,
    )


@app.route("/user-portal")
@app.route("/user")
@login_required()
def user_portal():
    """用户门户页面，根据角色显示不同内容。"""
    return render_template("user_portal.html")


@app.route("/donor")
def donor():
    """捐赠者重定向到捐赠页面。"""
    return redirect(url_for("donate"))


@app.route("/recipient")
def recipient():
    """受赠者重定向到签收页面。"""
    return redirect(url_for("receive"))


@app.route("/institution", methods=["GET", "POST"])
@login_required("institution")
def institution_portal():
    """机构门户：机构接收捐赠并派发给快递员。"""
    org_name = session.get("org_name")
    if not org_name:
        flash("机构账号未关联机构信息。", "danger")
        return redirect(url_for("user_portal"))

    # 列出分配给本机构的物品（未签收）
    records = summarize_trackings()
    items = []
    for track_id, block in records.items():
        data = block.data
        status = data.get("status")
        if status not in ["待接收", "处理中"]:
            continue
        donor = get_donor_by_tracking(track_id)
        if not donor or donor.get("assigned_org") != org_name:
            continue
        items.append(
            {
                "tracking_id": track_id,
                "status": status,
                "item_type": data.get("item_type", "未知"),
                "condition": data.get("condition", "未知"),
                "donor_name": data.get("donor_name", "匿名"),
                "updated_at": block.timestamp,
                "next_state": "已接收" if status == "待接收" else None,
            }
        )

    if request.method == "POST":
        tracking_id = request.form.get("tracking_id")
        action = request.form.get("action")
        if not tracking_id or not action:
            flash("缺少操作信息。", "warning")
            return redirect(url_for("institution_portal"))
        donor = get_donor_by_tracking(tracking_id)
        if not donor or donor.get("assigned_org") != org_name:
            flash("无权操作该物品或物品未分配给本机构。", "danger")
            return redirect(url_for("institution_portal"))

        # 接收物品
        if action == "accept":
            if not validate_transition(donor_status(tracking_id), "处理中"):
                flash("状态更新不合法。", "danger")
                return redirect(url_for("institution_portal"))
            event = build_event(
                tracking_id=tracking_id,
                item_type=donor["item_type"],
                condition=donor["condition"],
                donor_name=donor["donor_name"],
                photo_hash=donor.get("photo_hash", ""),
                status="处理中",
                note=f"机构 {org_name} 已接收并开始处理物品",
            )
            success, result = commit_chain_event(event)
            if not success:
                flash(format_chain_failure("接收", result), "danger")
                return redirect(url_for("institution_portal"))
            flash(f"物品 {tracking_id} 已进入处理中。", "success")
            return redirect(url_for("institution_portal"))

        # 指派快递员并转交到仓库
        if action == "assign_courier":
            courier = request.form.get("courier")
            if not courier:
                flash("请选择快递员。", "warning")
                return redirect(url_for("institution_portal"))
            current_status = donor_status(tracking_id)
            if current_status != "处理中":
                flash("物品必须先由机构员工接收并进入处理中后才能指派快递员。", "warning")
                return redirect(url_for("institution_portal"))

            if not validate_transition(current_status, "运送中"):
                flash("状态更新不合法。", "danger")
                return redirect(url_for("institution_portal"))
            ship_event = build_event(
                tracking_id=tracking_id,
                item_type=donor["item_type"],
                condition=donor["condition"],
                donor_name=donor["donor_name"],
                photo_hash=donor.get("photo_hash", ""),
                status="运送中",
                note=f"机构 {org_name} 已将物品 {tracking_id} 交给快递员 {courier} 运输到仓库",
            )
            success, result = commit_chain_event(ship_event)
            if not success:
                flash(format_chain_failure("发送快递员", result), "danger")
                return redirect(url_for("institution_portal"))

            assign_donor_to_courier(tracking_id, courier)
            flash(f"已指派快递员 {courier}，物品 {tracking_id} 已进入运送中。", "success")
            return redirect(url_for("institution_portal"))

    items.sort(key=lambda x: x["updated_at"], reverse=True)
    couriers = get_users_by_role(COURIER_ROLE)
    return render_template("institution_portal.html", items=items, org_name=org_name, couriers=couriers)


@app.route("/courier", methods=["GET", "POST"])
@login_required(COURIER_ROLE)
def courier_portal():
    """快递员门户：查看分配给自己的物品并执行运送相关动作。"""
    username = session.get("username")
    items = []
    records = summarize_trackings()
    for track_id, block in records.items():
        donor = get_donor_by_tracking(track_id)
        if donor and donor.get("assigned_courier") == username:
            items.append(
                {
                    "tracking_id": track_id,
                    "status": block.data.get("status"),
                    "item_type": block.data.get("item_type", "未知"),
                    "condition": block.data.get("condition", "未知"),
                    "donor_name": block.data.get("donor_name", "匿名"),
                    "created_at": donor.get("created_at"),
                    "updated_at": block.timestamp,
                }
            )

    if request.method == "POST":
        tracking_id = request.form.get("tracking_id")
        action = request.form.get("action")
        if not tracking_id or not action:
            flash("缺少操作信息。", "warning")
            return redirect(url_for("courier_portal"))
        donor = get_donor_by_tracking(tracking_id)
        if not donor or donor.get("assigned_courier") != username:
            flash("无权操作该物品或物品未分配给您。", "danger")
            return redirect(url_for("courier_portal"))

        # 交付到仓库（仅分配仓库，不直接改变链上状态）
        if action == "deliver_to_warehouse":
            assign_donor_to_warehouse(tracking_id, ORG_WAREHOUSE)
            flash(f"已将物品 {tracking_id} 交付至仓库。等待仓库分拣。", "success")
            return redirect(url_for("courier_portal"))

        # 从仓库运送到受赠者（需状态为 已分拣）
        if action == "deliver_to_recipient":
            recipient_username = request.form.get("recipient_username", "").strip()
            if not recipient_username:
                flash("请选择要送达的受赠者。", "warning")
                return redirect(url_for("courier_portal"))

            selected_recipient = get_user_by_username(recipient_username)
            if not selected_recipient or selected_recipient.get("role") != "recipient":
                flash("请选择有效的受赠者。", "warning")
                return redirect(url_for("courier_portal"))

            current = donor_status(tracking_id)
            if not validate_transition(current, "运送中"):
                flash("当前状态无法发起送达，请确认物品已分拣。", "warning")
                return redirect(url_for("courier_portal"))

            event = build_event(
                tracking_id=tracking_id,
                item_type=donor["item_type"],
                condition=donor["condition"],
                donor_name=donor["donor_name"],
                photo_hash=donor.get("photo_hash", ""),
                status="运送中",
                note=f"快递员 {username} 运送至受赠者 {recipient_username}",
            )
            success, result = commit_chain_event(event)
            if not success:
                flash(format_chain_failure("运送发起", result), "danger")
                return redirect(url_for("courier_portal"))
            assign_donor_to_recipient(tracking_id, recipient_username)
            flash(f"物品 {tracking_id} 已指派给受赠者 {recipient_username}，等待签收。", "success")
            return redirect(url_for("courier_portal"))

    recipient_users = get_users_by_role("recipient")
    items.sort(key=lambda x: x.get("created_at", ""), reverse=True)
    return render_template("courier_portal.html", items=items, username=username, recipients=recipient_users)


@app.route("/warehouse", methods=["GET", "POST"])
@login_required(WAREHOUSE_ROLE)
def warehouse_portal():
    """仓库门户：查看分配到仓库的物品并进行分拣，分拣完成后指派快递员。"""
    org_name = ORG_WAREHOUSE
    items = []
    records = summarize_trackings()
    for track_id, block in records.items():
        donor = get_donor_by_tracking(track_id)
        if donor and donor.get("assigned_warehouse") == org_name:
            items.append(
                {
                    "tracking_id": track_id,
                    "status": block.data.get("status"),
                    "item_type": block.data.get("item_type", "未知"),
                    "condition": block.data.get("condition", "未知"),
                    "donor_name": block.data.get("donor_name", "匿名"),
                    "created_at": donor.get("created_at"),
                    "updated_at": block.timestamp,
                }
            )

    if request.method == "POST":
        tracking_id = request.form.get("tracking_id")
        action = request.form.get("action")
        if not tracking_id or not action:
            flash("缺少操作信息。", "warning")
            return redirect(url_for("warehouse_portal"))
        donor = get_donor_by_tracking(tracking_id)
        if not donor or donor.get("assigned_warehouse") != org_name:
            flash("无权操作该物品或物品未分配到本仓库。", "danger")
            return redirect(url_for("warehouse_portal"))

        # 分拣完成 -> 更新链上状态为 已分拣，并可指派快递员取件
        if action == "sort_and_assign":
            courier = request.form.get("courier")
            if not courier:
                flash("请选择取件快递员。", "warning")
                return redirect(url_for("warehouse_portal"))
            current = donor_status(tracking_id)
            if not validate_transition(current, "已分拣"):
                flash("当前状态无法标记为已分拣。", "danger")
                return redirect(url_for("warehouse_portal"))
            event = build_event(
                tracking_id=tracking_id,
                item_type=donor["item_type"],
                condition=donor["condition"],
                donor_name=donor["donor_name"],
                photo_hash=donor.get("photo_hash", ""),
                status="已分拣",
                note=f"仓库 {org_name} 已完成分拣，指派快递员 {courier}",
            )
            success, result = commit_chain_event(event)
            if not success:
                flash(format_chain_failure("分拣", result), "danger")
                return redirect(url_for("warehouse_portal"))
            assign_donor_to_courier(tracking_id, courier)
            flash(f"物品 {tracking_id} 已分拣并指派快递员 {courier} 取件。", "success")
            return redirect(url_for("warehouse_portal"))

    couriers = get_users_by_role(COURIER_ROLE)
    items.sort(key=lambda x: x.get("created_at", ""), reverse=True)
    return render_template("warehouse_portal.html", items=items, couriers=couriers)


@app.route("/donate", methods=["GET", "POST"])
@login_required("donor")
def donate():
    """捐赠页面：允许捐赠者提交捐赠物品信息和照片。"""
    if request.method == "POST":
        donor_name = request.form.get("donor_name", "匿名").strip()
        phone = request.form.get("phone", "").strip()
        item_type = request.form.get("item_type", "综合捐赠").strip()
        condition = request.form.get("condition", "完好").strip()
        file = request.files.get("photo")

        if not file or file.filename == "":
            flash("请上传物品照片。", "warning")
            return redirect(url_for("donate"))
        if not allowed_file(file.filename):
            flash("仅支持 PNG/JPG/GIF 图片格式。", "warning")
            return redirect(url_for("donate"))

        # 生成唯一跟踪 ID
        tracking_id = str(uuid.uuid4()).replace("-", "")[:10].upper()
        filename = f"{tracking_id}_{secure_filename(file.filename)}"
        save_path = os.path.join(app.config["UPLOAD_FOLDER"], filename)
        file.save(save_path)
        photo_hash = compute_hash(save_path)

        # 创建区块链事件
        event = build_event(
            tracking_id=tracking_id,
            item_type=item_type,
            condition=condition,
            donor_name=donor_name,
            photo_hash=photo_hash,
            status="待接收",
            note="捐赠发起，等待机构验收",
        )
        success, result = commit_chain_event(event)
        if not success:
            if os.path.exists(save_path):
                try:
                    os.remove(save_path)
                except OSError:
                    pass
            flash(format_chain_failure("捐赠记录", result), "danger")
            return redirect(url_for("donate"))

        # 保存到数据库并自动分配给机构员工处理
        save_donor(tracking_id, donor_name, phone, item_type, condition, photo_hash, filename)
        assign_donor_to_org(tracking_id, ORG_INSTITUTION)
        flash(
            f"捐赠提交成功，溯源码：{tracking_id}。{format_chain_success('捐赠记录')}",
            "success",
        )
        return redirect(url_for("donate"))

    return render_template("donate.html")


@app.route("/admin", methods=["GET", "POST"])
@login_required("admin")
def admin():
    """管理员页面：管理捐赠物品状态与机构分配。"""
    if request.method == "POST":
        assign_tracking = request.form.get("assign_tracking")
        assign_org = request.form.get("assign_org")
        if assign_tracking and assign_org:
            current_state = donor_status(assign_tracking)
            if current_state == "已签收":
                flash(f"物品 {assign_tracking} 已签收，无法再次分配。", "warning")
                return redirect(url_for("admin"))
            assign_donor_to_org(assign_tracking, assign_org)
            flash(f"已将物品 {assign_tracking} 分配给机构：{assign_org}", "success")
            return redirect(url_for("admin"))

        delete_username = request.form.get("delete_username")
        if delete_username:
            if delete_username == session.get("username"):
                flash("不能删除当前登录管理员账号。", "warning")
                return redirect(url_for("admin"))
            user = get_user_by_username(delete_username)
            if not user:
                flash(f"用户 {delete_username} 不存在或已被删除。", "warning")
                return redirect(url_for("admin"))
            if user.get("role") == "admin":
                flash("管理员账号不可删除。", "warning")
                return redirect(url_for("admin"))
            delete_user(delete_username, deleted_by=session.get("username"))
            flash(f"已删除用户账号：{delete_username}", "success")
            return redirect(url_for("admin"))

        # 恢复已删除用户
        restore_username = request.form.get("restore_username")
        if restore_username:
            # 允许恢复已软删除的用户
            user = get_user_by_username(restore_username, include_deleted=True)
            if not user or not user.get("deleted_at"):
                flash(f"用户 {restore_username} 不存在或未被删除。", "warning")
                return redirect(url_for("admin"))
            # 禁止恢复管理员账号由非 super-admin 恢复（这里保持简单：允许恢复非 admin）
            restore_user(restore_username)
            flash(f"已恢复用户账号：{restore_username}", "success")
            return redirect(url_for("admin"))

        # 永久删除（物理删除）
        purge_username = request.form.get("purge_username")
        if purge_username:
            if purge_username == session.get("username"):
                flash("不能永久删除当前登录管理员账号。", "warning")
                return redirect(url_for("admin"))
            user = get_user_by_username(purge_username, include_deleted=True)
            if not user:
                flash(f"用户 {purge_username} 不存在。", "warning")
                return redirect(url_for("admin"))
            if user.get("role") == "admin":
                flash("管理员账号不可永久删除。", "warning")
                return redirect(url_for("admin"))
            purge_user(purge_username)
            flash(f"已永久删除用户账号：{purge_username}", "success")
            return redirect(url_for("admin"))

        tracking_id = request.form.get("tracking_id")
        current_state = request.form.get("current_state")
        if not tracking_id or not current_state:
            flash("缺少更新信息。", "warning")
            return redirect(url_for("admin"))
        next_step = next_state(current_state)
        if not next_step:
            flash("当前状态已是最终状态，无法继续更新。", "info")
            return redirect(url_for("admin"))
        if not validate_transition(current_state, next_step):
            flash("状态更新不合法。", "danger")
            return redirect(url_for("admin"))

        donor = get_donor_by_tracking(tracking_id)
        event = build_event(
            tracking_id=tracking_id,
            item_type=donor["item_type"] if donor else "未知",
            condition=donor["condition"] if donor else "未知",
            donor_name=donor["donor_name"] if donor else "匿名",
            photo_hash=donor["photo_hash"] if donor else "",
            status=next_step,
            note=f"管理员操作：状态更新为 {next_step}",
        )
        success, result = commit_chain_event(event)
        if not success:
            flash(format_chain_failure("状态更新", result), "danger")
            return redirect(url_for("admin"))

        flash(
            f"物品 {tracking_id} 状态已更新为：{next_step}。{format_chain_success('状态变更')}",
            "success",
        )
        return redirect(url_for("admin"))

    query = request.args.get("query", "").strip()
    filter_status = request.args.get("status", "")
    records = summarize_trackings()
    items = []
    for track_id, block in records.items():
        latest = block.to_dict()
        latest["event"] = block.data
        if query:
            query_text = query.lower()
            if query_text not in track_id.lower() and query_text not in latest["event"]["item_type"].lower() and query_text not in latest["event"]["donor_name"].lower():
                continue
        if filter_status and latest["event"]["status"] != filter_status:
            continue
        items.append(
            {
                "tracking_id": track_id,
                "status": latest["event"]["status"],
                "donor_name": latest["event"]["donor_name"],
                "item_type": latest["event"]["item_type"],
                "condition": latest["event"]["condition"],
                "updated_at": latest["timestamp"],
                "next_state": next_state(latest["event"]["status"]),
            }
        )
    institutions = get_institutions()
    users = get_all_users()
    # 包含已删除用户以便在管理界面提供恢复/永久删除操作
    all_including_deleted = get_all_users(include_deleted=True)
    deleted_users = [u for u in all_including_deleted if u.get("deleted_at")]
    return render_template(
        "admin.html",
        items=items,
        states=STATES,
        query=query,
        filter_status=filter_status,
        institutions=institutions,
        users=users,
        deleted_users=deleted_users,
    )


@app.route("/ledger")
@login_required("admin")
def ledger():
    """账本查询页面：管理员可查看当前链上的全部捐赠记录。"""
    events = chain.get_all_events()
    source = "fabric" if is_fabric_enabled() else "local"
    return render_template("ledger.html", events=events, source=source)


@app.route("/receive", methods=["GET", "POST"])
@login_required("recipient")
def receive():
    """签收页面：允许受赠者确认物品签收。"""
    tracking_id = request.values.get("tracking_id", "").strip().upper()
    item = None
    donor = None
    recipient = None
    photo_url = None
    if tracking_id:
        item = get_latest_event(tracking_id)
        donor = get_donor_by_tracking(tracking_id)
        recipient = get_recipient_by_tracking(tracking_id)
        photo_url = build_photo_url(donor)
    assigned_items = []
    recipient_username = session.get("username")
    for donor_item in get_donors_by_recipient(recipient_username):
        current_state = donor_status(donor_item["tracking_id"])
        if current_state == "运送中":
            assigned_items.append(
                {
                    "tracking_id": donor_item["tracking_id"],
                    "item_type": donor_item["item_type"],
                    "condition": donor_item["condition"],
                    "donor_name": donor_item["donor_name"],
                    "status": current_state,
                }
            )

    if request.method == "POST":
        tracking_id = request.form.get("tracking_id", "").strip().upper()
        recipient_name = request.form.get("recipient_name", "").strip()
        recipient_code = request.form.get("recipient_code", "").strip()
        address = request.form.get("address", "").strip()
        if not tracking_id or not recipient_code or not recipient_name or not address:
            flash("请填写完整签收信息。", "warning")
            return redirect(url_for("receive", tracking_id=tracking_id))

        history = get_latest_event(tracking_id)
        if not history:
            flash("未找到对应溯源码，请确认后重新输入。", "warning")
            return redirect(url_for("receive"))
        current_state = history["event"]["status"]
        if current_state != "运送中":
            flash("当前物品尚未进入运送阶段，请先由机构端更新状态。", "warning")
            return redirect(url_for("receive", tracking_id=tracking_id))

        donor = get_donor_by_tracking(tracking_id)
        event = build_event(
            tracking_id=tracking_id,
            item_type=donor["item_type"] if donor else "未知",
            condition=donor["condition"] if donor else "未知",
            donor_name=donor["donor_name"] if donor else "匿名",
            photo_hash=donor["photo_hash"] if donor else "",
            status="已签收",
            note=f"受赠方签收确认：{recipient_name} / {recipient_code}",
            receiver=recipient_name,
        )
        success, result = commit_chain_event(event)
        if not success:
            flash(format_chain_failure("签收记录", result), "danger")
            return redirect(url_for("receive", tracking_id=tracking_id))

        # 保存签收信息到数据库
        save_recipient(tracking_id, recipient_name, recipient_code, address)
        flash(
            f"物品 {tracking_id} 已完成签收闭环。{format_chain_success('签收记录')}",
            "success",
        )
        return redirect(url_for("receive", tracking_id=tracking_id))

    return render_template(
        "receive.html",
        item=item,
        recipient=recipient,
        photo_url=photo_url,
        tracking_id=tracking_id,
        assigned_items=assigned_items,
    )


@app.route("/track", methods=["GET", "POST"])
def track():
    """追踪页面：公开查询捐赠物品的完整历史记录。"""
    tracking_id = request.values.get("tracking_id", "").strip().upper()
    history = []
    valid = True
    donor = None
    recipient = None
    photo_url = None
    if tracking_id:
        history = chain.get_item_history(tracking_id)
        valid = chain.is_valid_chain()
        donor = get_donor_by_tracking(tracking_id)
        recipient = get_recipient_by_tracking(tracking_id)
        photo_url = build_photo_url(donor)
    return render_template(
        "track.html",
        tracking_id=tracking_id,
        history=history,
        valid=valid,
        donor=donor,
        recipient=recipient,
        photo_url=photo_url,
    )


if __name__ == "__main__":
    # 启动 Flask 开发服务器
    app.run(host="0.0.0.0", port=5000, debug=True)
