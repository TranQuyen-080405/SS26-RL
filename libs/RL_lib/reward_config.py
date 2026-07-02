"""
Hệ số reward — nguồn PC: Learn Lab + Simulation train.
ESP32 infer không import module này; chỉ dùng policy.bin + rl_core.py.
Chỉnh tại tab State & Reward: bật module, hằng R_*, công thức từng reward element.
"""

from RL_lib.lab_registry import DEFAULT_ELEMENT_FORMULAS, DEFAULT_ENABLED_MODULES, REWARD_ELEMENTS
from RL_lib.reward_formula import safe_eval_formula
from RL_lib.student_formula import default_total_formula, tokens_to_expr, eval_student_formula

# --- Hằng reward (đặt 0 nếu module tắt / không dùng) ---
R_STEP = 0.0
R_COLLISION = 0.0
R_GOAL_CLOSER = 0.0
R_GOAL_FARTHER = 0.0
R_CP_CLOSER = 0.0
R_CP_FARTHER = 0.0
R_CHECKPOINT_FIRST = 0.0
R_GOAL_REACHED = 0.0
R_ROTATE_IN_PLACE = 0.0
R_FACING_CLEAR = 0.0
R_FORWARD_CLEAR = 0.0
R_WASTED_ROTATE = 0.0
R_STRAIGHT = 0.0
R_WALL_DETECT = 0.0
R_VISIT_WINDOW = 0.0
R_VISIT_REPEAT = 0.0
R_PING_PONG = 0.0

MAX_ROTATE_STREAK = 4
MAX_REVISIT_STEPS = 5
MAX_CELL_REPEAT = 3
MAX_PING_PONG_CYCLES = 1
MAX_PING_PONG_SPAN = 5
MAX_STRAIGHT_STREAK = 3
COLLISION_RESET = False
MAX_STEPS_PER_EPISODE = 600

# --- Learn Lab: module bật + công thức từng element ---
FORMULA_NAME = 'test'
ENABLED_MODULES = set(['explore_penalty', 'heading', 'obstacle', 'rotation'])
ELEMENT_FORMULAS = dict(DEFAULT_ELEMENT_FORMULAS)
TOTAL_FORMULA_STUDENT = 'Va chạm tường'

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
    "R_STRAIGHT",
    "R_WALL_DETECT",
    "R_VISIT_WINDOW",
    "R_VISIT_REPEAT",
    "R_PING_PONG",
    "MAX_ROTATE_STREAK",
    "MAX_REVISIT_STEPS",
    "MAX_CELL_REPEAT",
    "MAX_PING_PONG_CYCLES",
    "MAX_PING_PONG_SPAN",
    "MAX_STRAIGHT_STREAK",
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
        facing_clear_on = sm.can_move(sim_map, x, y, d)

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
            "visit_window_penalty": revisit_window,
            "visit_repeat_penalty": moved and repeat_visits > MAX_CELL_REPEAT,
            "ping_pong_penalty": moved and ping > MAX_PING_PONG_CYCLES,
            "straight_streak_on": straight_streak >= MAX_STRAIGHT_STREAK,
            "wall_detected": bool(sim_map and sm.get_block(sim_map, robot["x"], robot["y"], robot["direct"])),
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
