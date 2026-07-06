"""
Hệ số reward — nguồn PC: Learn Lab + Simulation train.
ESP32 infer không import module này; chỉ dùng policy.bin + rl_core.py.
Chỉnh tại tab State & Reward: bật module, hằng R_*, công thức từng reward element.
"""

from RL_lib.lab_registry import DEFAULT_ELEMENT_FORMULAS, DEFAULT_ENABLED_MODULES, REWARD_ELEMENTS
from RL_lib.reward_formula import safe_eval_formula
from RL_lib.student_formula import default_total_formula, tokens_to_expr, eval_student_formula

# --- Hằng reward (đặt 0 nếu module tắt / không dùng) ---
R_STEP = -2.0
R_COLLISION = -80.0
R_EXCESS_ROTATE = 0.0
R_GOAL_CLOSER = 6.0
R_GOAL_FARTHER = -6.0
R_CP_CLOSER = 6.0
R_CP_FARTHER = -6.0
R_CHECKPOINT_FIRST = 80.0
R_GOAL_REACHED = 200.0
R_ROTATE_IN_PLACE = -3.0
R_FACING_CLEAR = 4.0
R_FORWARD_CLEAR = 8.0
R_WASTED_ROTATE = -15.0
R_BLOCKED_ROTATE = 0.0
R_STRAIGHT = 0.0
R_STRAIGHT_REACH = 2.0
R_STRAIGHT_CAP = 2.0
R_WALL_DETECT = 0.0
R_WALL_VISIBLE = 0.0
R_WALL_ON_ENTRY = 0.0
R_VISIT_WINDOW = 0.0
R_VISIT_REPEAT = -25.0
R_PING_PONG = -30.0

MAX_ROTATE_STREAK = 4
MAX_REVISIT_STEPS = 5
MAX_CELL_REPEAT = 3
MAX_PING_PONG_CYCLES = 1
MAX_PING_PONG_SPAN = 5
MAX_STRAIGHT_REACH = 3
MAX_STRAIGHT_CAP = 3
COLLISION_RESET = False
MAX_STEPS_PER_EPISODE = 600

# --- Learn Lab: module bật + công thức từng element ---
FORMULA_NAME = ''
ENABLED_MODULES = set(['checkpoint', 'explore_penalty', 'goal', 'heading', 'obstacle', 'rotation', 'step'])
ELEMENT_FORMULAS = dict(DEFAULT_ELEMENT_FORMULAS)
TOTAL_FORMULA_STUDENT = 'Mỗi bước đi +  Va chạm tường +  Tiến lên thành công +  Lại gần goal +  Đến đích +  Lại gần checkpoint +  Chạm checkpoint +  Xoay sang hướng thông thoáng +  Xoay tại chỗ +  Xoay khi có thể đi thẳng +  Quay lại ô +  Đi qua đi lại liên tục +  Giữ hướng'

REWARD_KEYS = (
    "R_STEP",
    "R_COLLISION",
    "R_EXCESS_ROTATE",
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
    "R_BLOCKED_ROTATE",
    "R_STRAIGHT",
    "R_STRAIGHT_REACH",
    "R_STRAIGHT_CAP",
    "R_WALL_DETECT",
    "R_WALL_VISIBLE",
    "R_WALL_ON_ENTRY",
    "R_VISIT_WINDOW",
    "R_VISIT_REPEAT",
    "R_PING_PONG",
    "MAX_ROTATE_STREAK",
    "MAX_REVISIT_STEPS",
    "MAX_CELL_REPEAT",
    "MAX_PING_PONG_CYCLES",
    "MAX_PING_PONG_SPAN",
    "MAX_STRAIGHT_REACH",
    "MAX_STRAIGHT_CAP",
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


def set_formula_name(name):
    global FORMULA_NAME
    FORMULA_NAME = str(name).strip()


def get_formula_name():
    return FORMULA_NAME


def sync_weights_from_elements(element_weights):
    """element_weights: eid -> số — ghi vào R_* tương ứng."""
    from RL_lib.lab_registry import ELEMENT_WEIGHT_KEY

    for eid, val in element_weights.items():
        key = ELEMENT_WEIGHT_KEY.get(eid)
        if key and key in REWARD_KEYS:
            globals()[key] = val
    # For backward compatibility with old JSON files
    if "goal_trend" in element_weights:
        globals()["R_GOAL_CLOSER"] = element_weights["goal_trend"]
        globals()["R_GOAL_FARTHER"] = -element_weights["goal_trend"]
    if "cp_trend" in element_weights:
        globals()["R_CP_CLOSER"] = element_weights["cp_trend"]
        globals()["R_CP_FARTHER"] = -element_weights["cp_trend"]
    if "straight_streak" in element_weights:
        globals()["R_STRAIGHT_REACH"] = element_weights["straight_streak"]
        globals()["R_STRAIGHT_CAP"] = element_weights["straight_streak"]


def _build_reward_context(robot, sim_map, result, could_forward_before=False):
    from map import sim_map as sm

    collision = bool(result.get("collision"))
    moved = bool(result.get("moved"))
    rotated = bool(
        result.get("success") and not result.get("moved") and not result.get("collision")
    )
    streak = robot.get("rotate_streak", 0)
    straight_streak = robot.get("straight_streak", 0)
    trend = robot.get("dist_goal_trend", 0)

    node_visits = robot.get("node_visits") or {}
    visits = node_visits.get((robot["x"], robot["y"]), 0) if moved else 0
    repeat_visits = max(0, visits - 1)
    ping = 0
    revisit_window = False
    if moved:
        from robot import robot as rb

        rb.bump_ping_pong_count(robot, MAX_PING_PONG_SPAN)
        ping = robot.get("ping_pong_count", 0)
        hist = robot.get("pos_history") or []
        if len(hist) >= 2 and MAX_REVISIT_STEPS > 0:
            key = hist[-1]
            prior = hist[-(MAX_REVISIT_STEPS + 1) : -1]
            revisit_window = key in prior

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

    if "checkpoint_first_visited" in result:
        at_cp_first = (result.get("checkpoint_first_visited") is not None)
    elif sim_map:
        for i in range(n_cp):
            if sm.is_at_checkpoint(sim_map, robot["x"], robot["y"], i):
                if i < len(visited) and not visited[i]:
                    at_cp_first = True
                    visited[i] = True
                break

    facing_clear_on = False
    if rotated and sim_map:
        x, y, d = robot["x"], robot["y"], robot["direct"]
        facing_clear_on = sm.can_move(sim_map, x, y, d)

    at_goal = bool(sim_map and sm.is_at_goal(sim_map, robot["x"], robot["y"]))

    wall_first = bool(robot.get("_reward_wall_first"))
    wall_facing = bool(robot.get("_reward_wall_facing"))
    wall_on_rotate = bool(rotated and wall_facing)
    wall_on_cell_entry = bool(moved and robot.get("_reward_wall_on_cell_entry"))

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
            "blocked_rotate_on": rotated and not could_forward_before,
            "excess_rotate": streak > MAX_ROTATE_STREAK,
            "visit_window_penalty": revisit_window,
            "visit_repeat_penalty": moved and repeat_visits > MAX_CELL_REPEAT,
            "ping_pong_penalty": moved and ping > MAX_PING_PONG_CYCLES,
            "straight_streak_on": straight_streak >= MAX_STRAIGHT_REACH,
            "straight_streak_reach_on": moved and straight_streak >= MAX_STRAIGHT_REACH,
            "straight_streak_cap_on": moved and straight_streak <= MAX_STRAIGHT_CAP,
            "wall_detected": wall_first,
            "wall_visible": wall_on_rotate,
            "wall_first_discover": wall_first,
            "wall_on_rotate": wall_on_rotate,
            "wall_on_cell_entry": wall_on_cell_entry,
        }
    )
    return ctx


_FAST_EVAL = {
    "R_STEP": lambda c: c["R_STEP"],
    "R_COLLISION if collision else 0": lambda c: c["R_COLLISION"] if c["collision"] else 0.0,
    "R_FORWARD_CLEAR if moved and not collision else 0": lambda c: c["R_FORWARD_CLEAR"] if (c["moved"] and not c["collision"]) else 0.0,
    "R_WALL_DETECT if wall_detected else 0": lambda c: c["R_WALL_DETECT"] if c["wall_detected"] else 0.0,
    "R_WALL_VISIBLE if wall_visible else 0": lambda c: c["R_WALL_VISIBLE"] if c["wall_visible"] else 0.0,
    "R_WALL_ON_ENTRY if wall_on_cell_entry else 0": lambda c: c["R_WALL_ON_ENTRY"] if c["wall_on_cell_entry"] else 0.0,
    "R_GOAL_CLOSER if goal_closer else 0": lambda c: c["R_GOAL_CLOSER"] if c["goal_closer"] else 0.0,
    "R_GOAL_FARTHER if goal_farther else 0": lambda c: c["R_GOAL_FARTHER"] if c["goal_farther"] else 0.0,
    "R_GOAL_REACHED if at_goal else 0": lambda c: c["R_GOAL_REACHED"] if c["at_goal"] else 0.0,
    "R_CP_CLOSER if cp_closer else 0": lambda c: c["R_CP_CLOSER"] if c["cp_closer"] else 0.0,
    "R_CP_FARTHER if cp_farther else 0": lambda c: c["R_CP_FARTHER"] if c["cp_farther"] else 0.0,
    "R_CHECKPOINT_FIRST if at_cp_first else 0": lambda c: c["R_CHECKPOINT_FIRST"] if c["at_cp_first"] else 0.0,
    "R_ROTATE_IN_PLACE if rotated else 0": lambda c: c["R_ROTATE_IN_PLACE"] if c["rotated"] else 0.0,
    "R_FACING_CLEAR if facing_clear_on else 0": lambda c: c["R_FACING_CLEAR"] if c["facing_clear_on"] else 0.0,
    "R_WASTED_ROTATE if wasted_rotate_on else 0": lambda c: c["R_WASTED_ROTATE"] if c["wasted_rotate_on"] else 0.0,
    "R_BLOCKED_ROTATE if blocked_rotate_on else 0": lambda c: c["R_BLOCKED_ROTATE"] if c["blocked_rotate_on"] else 0.0,
    "R_EXCESS_ROTATE if excess_rotate else 0": lambda c: c["R_EXCESS_ROTATE"] if c["excess_rotate"] else 0.0,
    "R_VISIT_WINDOW if visit_window_penalty else 0": lambda c: c["R_VISIT_WINDOW"] if c["visit_window_penalty"] else 0.0,
    "R_VISIT_REPEAT if visit_repeat_penalty else 0": lambda c: c["R_VISIT_REPEAT"] if c["visit_repeat_penalty"] else 0.0,
    "R_PING_PONG if ping_pong_penalty else 0": lambda c: c["R_PING_PONG"] if c["ping_pong_penalty"] else 0.0,
    "R_STRAIGHT_REACH if straight_streak_reach_on else 0": lambda c: c["R_STRAIGHT_REACH"] if c["straight_streak_reach_on"] else 0.0,
    "R_STRAIGHT_CAP if straight_streak_cap_on else 0": lambda c: c["R_STRAIGHT_CAP"] if c["straight_streak_cap_on"] else 0.0,
}


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
        if formula in _FAST_EVAL:
            parts[eid] = _FAST_EVAL[formula](ctx)
        else:
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
