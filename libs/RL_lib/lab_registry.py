"""
Catalog State module ↔ Reward element cho Learn Lab.

State module = nhóm tín hiệu trong observation s (hoặc ngữ cảnh hành vi).
Reward element = thành phần điểm; học sinh gán công thức dùng hằng R_* và cờ điều kiện.
"""

# --- State modules (bật/tắt trong Lab) ---
STATE_MODULES = (
    {
        "id": "step",
        "label": "Mỗi bước đi",
        "in_encode": False,
        "encode_fields": [],
        "desc": "Luôn trừ/cộng mỗi action (không nằm trong vector state).",
    },
    {
        "id": "obstacle",
        "label": "Obstacle",
        "in_encode": True,
        "encode_fields": ["obstacle_nwes"],
        "desc": "4 bit tường quanh robot trong state — liên quan va tường / forward.",
    },
    {
        "id": "goal",
        "label": "Goal",
        "in_encode": True,
        "encode_fields": ["dist_goal_trend"],
        "desc": "Trend khoảng cách goal (−1/0/+1) trong state + sự kiện tới goal.",
    },
    {
        "id": "checkpoint",
        "label": "Checkpoint",
        "in_encode": True,
        "encode_fields": ["dist_cp_trends"],
        "desc": "Trend CP1–3 trong s + chạm checkpoint lần đầu.",
    },
    {
        "id": "heading",
        "label": "Heading",
        "in_encode": True,
        "encode_fields": ["heading"],
        "desc": "Hướng (N/W/E/S) trong state (4 giá trị cuối encode).",
    },
    {
        "id": "rotation",
        "label": "Xoay",
        "in_encode": False,
        "encode_fields": [],
        "desc": "Action rotate — sinh reward xoay / xoay lãng phí / facing clear.",
    },
    {
        "id": "explore_penalty",
        "label": "Lặp lại đường đi",
        "in_encode": False,
        "encode_fields": [],
        "desc": "Đi vào ô cũ quá nhiều.",
    },
)

DEFAULT_ENABLED_MODULES = frozenset(m["id"] for m in STATE_MODULES)

# --- Reward elements ---
# constants: hằng R_* / MAX_* dùng trong công thức
# flags: biến bool/int có trong ngữ cảnh eval (xem FORMULA_HELP)
REWARD_ELEMENTS = {
    "R_STEP": {
        "label": "Mỗi bước đi",
        "module": "step",
        "constants": ["R_STEP"],
        "default_formula": "R_STEP",
    },
    "collision": {
        "label": "Va chạm tường",
        "module": "obstacle",
        "constants": ["R_COLLISION"],
        "default_formula": "R_COLLISION if collision else 0",
    },
    "forward_clear": {
        "label": "Tiến lên thành công",
        "module": "obstacle",
        "constants": ["R_FORWARD_CLEAR"],
        "default_formula": "R_FORWARD_CLEAR if moved and not collision else 0",
    },
    "wall_detected": {
        "label": "Phát hiện tường",
        "module": "obstacle",
        "constants": ["R_WALL_DETECT"],
        "default_formula": "R_WALL_DETECT if wall_detected else 0",
    },
    "goal_trend": {
        "label": "Lại gần đích",
        "module": "goal",
        "constants": ["R_GOAL_CLOSER", "R_GOAL_FARTHER"],
        "default_formula": "R_GOAL_CLOSER if goal_closer else (R_GOAL_FARTHER if goal_farther else 0)",
    },
    "goal_reached": {
        "label": "Đến đích",
        "module": "goal",
        "constants": ["R_GOAL_REACHED"],
        "default_formula": "R_GOAL_REACHED if at_goal else 0",
    },
    "cp_trend": {
        "label": "Lại gần checkpoint",
        "module": "checkpoint",
        "constants": ["R_CP_CLOSER", "R_CP_FARTHER"],
        "default_formula": "R_CP_CLOSER if cp_closer else (R_CP_FARTHER if cp_farther else 0)",
    },
    "checkpoint": {
        "label": "Chạm checkpoint",
        "module": "checkpoint",
        "constants": ["R_CHECKPOINT_FIRST"],
        "default_formula": "R_CHECKPOINT_FIRST if at_cp_first else 0",
    },
    "rotate": {
        "label": "Xoay tại chỗ",
        "module": "rotation",
        "constants": ["R_ROTATE_IN_PLACE"],
        "default_formula": "R_ROTATE_IN_PLACE if rotated else 0",
    },
    "facing_clear": {
        "label": "Xoay sang hướng thông thoáng",
        "module": "rotation",
        "constants": ["R_FACING_CLEAR"],
        "default_formula": "R_FACING_CLEAR if facing_clear_on else 0",
    },
    "wasted_rotate": {
        "label": "Xoay khi có thể đi thẳng",
        "module": "rotation",
        "constants": ["R_WASTED_ROTATE"],
        "default_formula": "R_WASTED_ROTATE if wasted_rotate_on else 0",
    },
    "excess_rotate": {
        "label": "Xoay tại chỗ liên tục",
        "module": "rotation",
        "constants": ["R_COLLISION", "MAX_ROTATE_STREAK"],
        "default_formula": "R_COLLISION if excess_rotate else 0",
    },
    "revisit": {
        "label": "Vào lại ô cũ",
        "module": "explore_penalty",
        "constants": ["R_COLLISION", "MAX_NODE_REVISITS"],
        "default_formula": "R_COLLISION if revisit_penalty else 0",
    },
    "ping_pong": {
        "label": "Đi qua đi lại liên tục",
        "module": "explore_penalty",
        "constants": ["R_COLLISION", "MAX_PING_PONG_CYCLES"],
        "default_formula": "R_COLLISION if ping_pong_penalty else 0",
    },
    "straight_streak": {
        "label": "Giữ nguyên hướng đi",
        "module": "heading",
        "constants": ["R_STRAIGHT", "MAX_STRAIGHT_STREAK"],
        "default_formula": "R_STRAIGHT if straight_streak_on else 0",
    },
}

DEFAULT_ELEMENT_FORMULAS = {k: v["default_formula"] for k, v in REWARD_ELEMENTS.items()}

# Mỗi cục reward → hằng R_* (sync weight học sinh → train)
ELEMENT_WEIGHT_KEY = {
    "R_STEP": "R_STEP",
    "collision": "R_COLLISION",
    "forward_clear": "R_FORWARD_CLEAR",
    "goal_trend": "R_GOAL_CLOSER",
    "goal_reached": "R_GOAL_REACHED",
    "cp_trend": "R_CP_CLOSER",
    "checkpoint": "R_CHECKPOINT_FIRST",
    "rotate": "R_ROTATE_IN_PLACE",
    "facing_clear": "R_FACING_CLEAR",
    "wasted_rotate": "R_WASTED_ROTATE",
    "excess_rotate": "R_COLLISION",
    "revisit": "R_COLLISION",
    "ping_pong": "R_COLLISION",
    "straight_streak": "R_STRAIGHT",
    "wall_detected": "R_WALL_DETECT",
}

# Ngưỡng (ẩn tên code trong UI — label riêng)
THRESHOLD_LABELS = {
    "MAX_ROTATE_STREAK": "Ngưỡng xoay liên tiếp",
    "MAX_NODE_REVISITS": "Ngưỡng lặp ô",
    "MAX_PING_PONG_CYCLES": "Ngưỡng lặp",
    "MAX_STRAIGHT_STREAK": "Ngưỡng giữ hướng",
}

FORMULA_HELP = "Ghép reward + phép + − × ÷ ^ ( ). Ví dụ: 2 ^ Mỗi bước đi + Va chạm tường × 2"


def module_by_id(mid):
    for m in STATE_MODULES:
        if m["id"] == mid:
            return m
    return None


def elements_for_module(module_id):
    return [eid for eid, meta in REWARD_ELEMENTS.items() if meta["module"] == module_id]


def constants_for_modules(enabled_modules):
    out = set()
    for eid, meta in REWARD_ELEMENTS.items():
        if meta["module"] in enabled_modules:
            out.update(meta["constants"])
    return sorted(out)


def mapping_rows(enabled_modules=None):
    enabled = enabled_modules or DEFAULT_ENABLED_MODULES
    rows = []
    for mod in STATE_MODULES:
        mid = mod["id"]
        enc = ", ".join(mod["encode_fields"]) if mod["encode_fields"] else "—"
        elems = elements_for_module(mid)
        if not elems:
            rows.append((mid, mod["label"], enc, "—", "—", mid in enabled))
            continue
        for i, eid in enumerate(elems):
            meta = REWARD_ELEMENTS[eid]
            const = ", ".join(meta["constants"])
            rows.append(
                (
                    mid if i == 0 else "",
                    mod["label"] if i == 0 else "",
                    enc if i == 0 else "",
                    eid,
                    const,
                    mid in enabled,
                )
            )
    return rows
