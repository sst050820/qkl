# 定义捐赠物品的状态列表，从捐赠到签收的各个阶段
STATES = ["待接收", "处理中", "已分拣", "运送中", "已签收"]

# 定义状态转换规则，每个状态可以转换到哪些后续状态
VALID_TRANSITIONS = {
    "待接收": ["处理中"],  # 待接收只能转为处理中
    "处理中": ["已分拣"],  # 处理中只能转为已分拣
    "已分拣": ["运送中"],  # 已分拣只能转为运送中
    "运送中": ["已签收"],  # 运送中只能转为已签收
    "已签收": [],  # 已签收是最终状态，无后续状态
}


def next_state(current_state):
    """根据当前状态获取下一个状态。

    返回当前状态允许的第一个后续状态，如果没有则返回 None。
    """
    if current_state not in VALID_TRANSITIONS:
        return None
    options = VALID_TRANSITIONS[current_state]
    return options[0] if options else None


def validate_transition(current_state, new_state):
    """验证状态转换是否合法。

    检查 new_state 是否在 current_state 的允许转换列表中。
    """
    return new_state in VALID_TRANSITIONS.get(current_state, [])


def mask_name(name):
    """对捐赠者姓名进行脱敏处理。

    保留第一个字符，其余用 * 替换，保护隐私。
    """
    if not name:
        return "匿名捐赠"
    name = name.strip()
    if len(name) <= 1:
        return "*"
    return name[0] + "**"


def mask_recipient(recipient_name):
    """对受赠者姓名进行脱敏处理。

    如果包含编号则保持原样，否则保留前两个字符，其余用 * 替换。
    """
    if not recipient_name:
        return "受赠方"
    if "编号" in recipient_name:
        return recipient_name
    return recipient_name[:2] + "**"


def build_event(tracking_id, item_type, condition, donor_name, photo_hash, status, note=None, receiver=None):
    """构建区块链事件数据结构。

    用于创建捐赠物品的区块链记录，包含所有必要信息。
    """
    return {
        "type": "donation",  # 事件类型
        "tracking_id": tracking_id,  # 跟踪 ID
        "item_type": item_type,  # 物品类型
        "condition": condition,  # 物品状况
        "donor_name": mask_name(donor_name),  # 脱敏后的捐赠者姓名
        "photo_hash": photo_hash,  # 照片哈希
        "status": status,  # 当前状态
        "note": note or "",  # 备注信息
        "receiver": mask_recipient(receiver) if receiver else "",  # 脱敏后的受赠者姓名
    }
