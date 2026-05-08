import hashlib
import os
import uuid
from flask import Flask, flash, redirect, render_template, request, url_for
from werkzeug.utils import secure_filename
from config import ALLOWED_EXTENSIONS, DATABASE_PATH, SECRET_KEY, UPLOAD_FOLDER
from blockchain import Blockchain
from contracts import STATES, build_event, next_state, validate_transition
from database import get_donor_by_tracking, get_recipient_by_tracking, init_db, save_donor, save_recipient

os.makedirs(UPLOAD_FOLDER, exist_ok=True)

app = Flask(__name__)
app.config["SECRET_KEY"] = SECRET_KEY
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
app.config["MAX_CONTENT_LENGTH"] = 5 * 1024 * 1024

chain = Blockchain()
init_db()


def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


def compute_hash(path):
    hasher = hashlib.sha256()
    with open(path, "rb") as file:
        while True:
            chunk = file.read(8192)
            if not chunk:
                break
            hasher.update(chunk)
    return hasher.hexdigest()


def mask_name(name):
    if not name:
        return "匿名捐赠"
    return name[0] + "**" if len(name.strip()) > 1 else "*"


def summarize_trackings():
    summary = {}
    for block in chain.chain:
        data = block.data
        tracking_id = data.get("tracking_id")
        if tracking_id:
            summary[tracking_id] = block
    return summary


def get_latest_event(tracking_id):
    return chain.get_latest_item(tracking_id)


def build_photo_url(donor):
    if donor and donor.get("photo_filename"):
        return url_for("static", filename=f"uploads/{donor['photo_filename']}")
    return None


@app.route("/")
def index():
    summary = summarize_trackings()
    total_items = len(summary)
    status_count = {state: 0 for state in STATES}
    for block in summary.values():
        status = block.data.get("status")
        if status in status_count:
            status_count[status] += 1
    recent_events = chain.get_all_events()[-5:][::-1]
    last_event = recent_events[0] if recent_events else None
    return render_template(
        "index.html",
        block_height=len(chain.chain) - 1,
        total_items=total_items,
        last_event=last_event,
        status_count=status_count,
        valid_chain=chain.is_valid_chain(),
        recent_events=recent_events,
    )


@app.route("/donate", methods=["GET", "POST"])
def donate():
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

        tracking_id = str(uuid.uuid4()).replace("-", "")[:10].upper()
        filename = f"{tracking_id}_{secure_filename(file.filename)}"
        save_path = os.path.join(app.config["UPLOAD_FOLDER"], filename)
        file.save(save_path)
        photo_hash = compute_hash(save_path)

        save_donor(tracking_id, donor_name, phone, item_type, condition, photo_hash, filename)

        event = build_event(
            tracking_id=tracking_id,
            item_type=item_type,
            condition=condition,
            donor_name=donor_name,
            photo_hash=photo_hash,
            status="待接收",
            note="捐赠发起，等待机构验收",
        )
        chain.add_block(event)

        flash(f"捐赠提交成功，溯源码：{tracking_id}", "success")
        return redirect(url_for("donate"))

    return render_template("donate.html")


@app.route("/admin", methods=["GET", "POST"])
def admin():
    if request.method == "POST":
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
            note=f"机构操作：状态更新为 {next_step}",
        )
        chain.add_block(event)
        flash(f"物品 {tracking_id} 状态已更新为：{next_step}", "success")
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
    return render_template("admin.html", items=items, states=STATES, query=query, filter_status=filter_status)


@app.route("/receive", methods=["GET", "POST"])
def receive():
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

        save_recipient(tracking_id, recipient_name, recipient_code, address)
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
        chain.add_block(event)
        flash(f"物品 {tracking_id} 已完成签收闭环。", "success")
        return redirect(url_for("receive", tracking_id=tracking_id))

    return render_template(
        "receive.html",
        item=item,
        recipient=recipient,
        photo_url=photo_url,
        tracking_id=tracking_id,
    )


@app.route("/track", methods=["GET", "POST"])
def track():
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
    app.run(host="0.0.0.0", port=5000, debug=True)
