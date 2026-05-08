STATES = ["待接收", "处理中", "已分拣", "运送中", "已签收"]
VALID_TRANSITIONS = {
    "待接收": ["处理中"],
    "处理中": ["已分拣"],
    "已分拣": ["运送中"],
    "运送中": ["已签收"],
    "已签收": [],
}


def next_state(current_state):
    if current_state not in VALID_TRANSITIONS:
        return None
    options = VALID_TRANSITIONS[current_state]
    return options[0] if options else None


def validate_transition(current_state, new_state):
    return new_state in VALID_TRANSITIONS.get(current_state, [])


def mask_name(name):
    if not name:
        return "匿名捐赠"
    name = name.strip()
    if len(name) <= 1:
        return "*"
    return name[0] + "**"


def mask_recipient(recipient_name):
    if not recipient_name:
        return "受赠方"
    if "编号" in recipient_name:
        return recipient_name
    return recipient_name[:2] + "**"


def build_event(tracking_id, item_type, condition, donor_name, photo_hash, status, note=None, receiver=None):
    return {
        "type": "donation",
        "tracking_id": tracking_id,
        "item_type": item_type,
        "condition": condition,
        "donor_name": mask_name(donor_name),
        "photo_hash": photo_hash,
        "status": status,
        "note": note or "",
        "receiver": mask_recipient(receiver) if receiver else "",
    }
