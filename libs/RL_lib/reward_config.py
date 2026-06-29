"""
Hệ số reward — nguồn đồng bộ PC (Learn Lab / train) và Robot_embbed.
Chỉnh tại tab State & Reward: bật module, hằng R_*, công thức từng reward element.
"""

from RL_lib.lab_registry import DEFAULT_ELEMENT_FORMULAS, DEFAULT_ENABLED_MODULES, REWARD_ELEMENTS
from RL_lib.reward_formula import safe_eval_formula
from RL_lib.student_formula import default_total_formula, tokens_to_expr, eval_student_formula

# --- Hằng reward (đặt 0 nếu module tắt / không dùng) ---
R_STEP = -1.0
R_COLLISION = -20.0
R_GOAL_CLOSER = 5.0
R_GOAL_FARTHER = 0.0
R_CP_CLOSER = 8.0
R_CP_FARTHER = 0.0
R_CHECKPOINT_FIRST = 30.0
R_GOAL_REACHED = 100.0
R_ROTATE_IN_PLACE = -3.0
R_FACING_CLEAR = 5.0
R_FORWARD_CLEAR = 4.0
R_WASTED_ROTATE = -12.0

MAX_ROTATE_STREAK = 4
MAX_NODE_REVISITS = 5
MAX_PING_PONG_CYCLES = 2
COLLISION_RESET = False
MAX_STEPS_PER_EPISODE = 600

# --- Learn Lab: module bật + công thức từng element ---
ENABLED_MODULES = set(['checkpoint', 'explore_penalty', 'goal', 'heading', 'obstacle', 'rotation', 'step'])
ELEMENT_FORMULAS = dict(DEFAULT_ELEMENT_FORMULAS)
TOTAL_FORMULA_STUDENT = 'Mỗi bước đi +  Va chạm tường +  Tiến lên thành công +  Lại gần đích +  Đến đích +  Lại gần checkpoint +  Chạm checkpoint +  Xoay tại chỗ +  Xoay hướng thông thoáng +  Xoay lãng phí +  Xoay tại chỗ liên tục +  Vào lại ô cũ nhiều lần +  Đi qua đi lại'

REWARD_KEYS = (
    "R_STEP",
    "R_COLLISION",
    "R_GOAL_CLOSER",
    "R_GOAL_FARTHER",
    "R_CP_CLOSER",
    "R_CP_FARTHER",
    "R_CHECKPOINT_FIRST",
    "R_GOAL_REACHED",
    "R_ROTATE_IN_PLACE",
    "R_FACING_CLEAR",
    "R_FORWARD_CLEAR",
    "R_WASTED_ROTATE",
    "MAX_ROTATE_STREAK",
    "MAX_NODE_REVISITS",
    "MAX_PING_PONG_CYCLES",
    "COLLISION_RESET",
    "MAX_STEPS_PER_EPISODE",
)


def get_reward_dict():
    return {k: globals()[k] for k in REWARD_KEYS}


def apply_reward_dict(values):
    for k in REWARD_KEYS:
        if k in values:
            globals()[k] = values[k]


def set_enabled_modules(modules):
    global ENABLED_MODULES
    ENABLED_MODULES = set(modules)


def get_enabled_modules():
    return set(ENABLED_MODULES)


def set_element_formulas(formulas):
    global ELEMENT_FORMULAS
    ELEMENT_FORMULAS = dict(formulas)


def get_element_formulas():
    return dict(ELEMENT_FORMULAS)


def set_total_formula_student(expr):
    global TOTAL_FORMULA_STUDENT
    TOTAL_FORMULA_STUDENT = str(expr).strip()


def get_total_formula_student():
    return TOTAL_FORMULA_STUDENT


def sync_weights_from_elements(element_weights):
    """element_weights: eid -> số — ghi vào R_* tương ứng."""
    from RL_lib.lab_registry import ELEMENT_WEIGHT_KEY

    for eid, val in element_weights.items():
        key = ELEMENT_WEIGHT_KEY.get(eid)
        if key and key in REWARD_KEYS:
            globals()[key] = val


def _build_reward_context(robot, sim_map, result, could_forward_before=False):
    from map import sim_map as sm
    from RL_lib.grid import neighbor_xy

    collision = bool(result.get("collision"))
    moved = bool(result.get("moved"))
    rotated = bool(
        result.get("success") and not result.get("moved") and not result.get("collision")
    )
    streak = robot.get("rotate_streak", 0)
    trend = robot.get("dist_goal_trend", 0)

    node_visits = dict(robot.get("node_visits") or {})
    if moved:
        key = (robot["x"], robot["y"])
        node_visits[key] = node_visits.get(key, 0) + 1
    visits = node_visits.get((robot["x"], robot["y"]), 0)
    ping = robot.get("ping_pong_count", 0)

    cp_closer = False
    cp_farther = False
    at_cp_first = False
    n_cp = sm.n_checkpoints(sim_map) if sim_map else 0
    visited = robot.get("cp_visited")
    if visited is None or not isinstance(visited, list) or len(visited) < n_cp:
        visited = [False] * n_cp
        robot["cp_visited"] = visited

    if moved and sim_map:
        for i in range(n_cp):
            if i < len(visited) and not visited[i]:
                ct = robot.get("dist_cp_trend", [0, 0, 0])[i]
                if ct == 1:
                    cp_closer = True
                elif ct == -1:
                    cp_farther = True
                break
    if sim_map:
        for i in range(n_cp):
            if sm.is_at_checkpoint(sim_map, robot["x"], robot["y"], i):
                if i < len(visited) and not visited[i]:
                    at_cp_first = True
                    visited[i] = True
                break

    facing_clear_on = False
    if rotated and sim_map:
        x, y, d = robot["x"], robot["y"], robot["direct"]
        if sm.can_move(sim_map, x, y, d):
            nx, ny = neighbor_xy(x, y, d)
            visited_cp = robot.get("cp_visited") or []
            cps = sm.n_checkpoints(sim_map)
            for i in range(cps):
                if i < len(visited_cp) and not visited_cp[i]:
                    cur = sm.dist_to_checkpoints(sim_map, x, y)[i]
                    nxt = sm.dist_to_checkpoints(sim_map, nx, ny)[i]
                    if nxt < cur:
                        facing_clear_on = True
                    break
            else:
                if sm.dist_to_goal(sim_map, nx, ny) < sm.dist_to_goal(sim_map, x, y):
                    facing_clear_on = True

    at_goal = bool(sim_map and sm.is_at_goal(sim_map, robot["x"], robot["y"]))

    ctx = dict(get_reward_dict())
    ctx.update(
        {
            "collision": collision,
            "moved": moved,
            "rotated": rotated,
            "could_forward": bool(could_forward_before),
            "goal_trend": trend,
            "goal_closer": moved and trend == 1,
            "goal_farther": moved and trend == -1,
            "cp_closer": cp_closer,
            "cp_farther": cp_farther,
            "at_goal": at_goal,
            "at_cp_first": at_cp_first,
            "facing_clear_on": facing_clear_on,
            "wasted_rotate_on": rotated and could_forward_before,
            "excess_rotate": streak > MAX_ROTATE_STREAK,
            "revisit_penalty": visits > MAX_NODE_REVISITS,
            "ping_pong_penalty": ping > MAX_PING_PONG_CYCLES,
        }
    )
    return ctx


def compute_reward_breakdown(robot, sim_map, result, action_name=None, could_forward_before=False):
    """Trả (tổng, dict element). Element tắt theo ENABLED_MODULES hoặc công thức tùy biến."""
    from RL_lib.lab_registry import REWARD_ELEMENTS

    ctx = _build_reward_context(robot, sim_map, result, could_forward_before)
    parts = {}
    for eid, meta in REWARD_ELEMENTS.items():
        if meta["module"] not in ENABLED_MODULES:
            parts[eid] = 0.0
            continue
        formula = ELEMENT_FORMULAS.get(eid, meta["default_formula"])
        try:
            parts[eid] = safe_eval_formula(formula, ctx)
        except (ValueError, SyntaxError, TypeError, ZeroDivisionError):
            parts[eid] = 0.0
    enabled_eids = [eid for eid, meta in REWARD_ELEMENTS.items() if meta["module"] in ENABLED_MODULES]
    total = eval_student_formula(TOTAL_FORMULA_STUDENT, parts, enabled_eids)
    return total, parts


def compute_reward(robot, sim_map, result, action_name=None, could_forward_before=False):
    total, _ = compute_reward_breakdown(
        robot, sim_map, result, action_name=action_name, could_forward_before=could_forward_before
    )
    return total
