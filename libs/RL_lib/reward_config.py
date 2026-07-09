"""
Hệ số reward — nguồn PC: Learn Lab + Simulation train.
ESP32 infer không import module này; chỉ dùng policy.bin + rl_core.py.
Chỉnh tại tab State & Reward: bật module, hằng R_*, công thức từng reward element.
"""

from RL_lib.lab_registry import (
    DEFAULT_ELEMENT_FORMULAS,
    DEFAULT_ENABLED_MODULES,
    REWARD_ELEMENTS,
    ELEMENT_WEIGHT_KEY,
)
from RL_lib.reward_formula import safe_eval_formula
from RL_lib.student_formula import default_total_formula, tokens_to_expr, parse_expr_to_tokens

# --- Hằng reward (đặt 0 nếu module tắt / không dùng) ---
DEFAULT_BLOCK_WEIGHT = 1.0
R_STEP = 1.0
R_COLLISION = 1.0
R_EXCESS_ROTATE = 1.0
R_GOAL_CLOSER = 1.0
R_GOAL_FARTHER = 1.0
R_CP_CLOSER = 1.0
R_CP_FARTHER = 1.0
R_CHECKPOINT_FIRST = 1.0
R_GOAL_REACHED = 1.0
R_ROTATE_IN_PLACE = 1.0
R_FACING_CLEAR = 1.0
R_FORWARD_CLEAR = 1.0
R_WASTED_ROTATE = 1.0
R_BLOCKED_ROTATE = 1.0
R_ROTATE_TO_N = 1.0
R_ROTATE_TO_E = 1.0
R_ROTATE_TO_S = 1.0
R_ROTATE_TO_W = 1.0
R_FORWARD_N = 1.0
R_FORWARD_E = 1.0
R_FORWARD_S = 1.0
R_FORWARD_W = 1.0
R_FORWARD_NEW = 1.0
R_STRAIGHT = 1.0
R_STRAIGHT_REACH = 1.0
R_STRAIGHT_CAP = 1.0
R_WALL_DETECT = 1.0
R_WALL_VISIBLE = 1.0
R_WALL_ON_ENTRY = 1.0
R_VISIT_WINDOW = 1.0
R_VISIT_REPEAT = 1.0
R_PING_PONG = 1.0

MAX_ROTATE_STREAK = 2
MAX_REVISIT_STEPS = 4
MAX_CELL_REPEAT = 2
MAX_PING_PONG_CYCLES = 1
MAX_PING_PONG_SPAN = 5
MAX_STRAIGHT_REACH = 3
MAX_STRAIGHT_CAP = 3
CP_TARGET_INDEX = 1
COLLISION_RESET = False
MAX_STEPS_PER_EPISODE = 600

# --- Learn Lab: module bật + công thức từng element ---
FORMULA_NAME = 'Reward_1'
ENABLED_MODULES = set(['checkpoint', 'explore_penalty', 'goal', 'heading', 'memory_loop', 'obstacle', 'rotation', 'step'])
ELEMENT_FORMULAS = dict(DEFAULT_ELEMENT_FORMULAS)
TOTAL_FORMULA_STUDENT = 'Xoay tại chỗ #1 +  (  Lặp ô gần #1 +  Quay lại ô #1 +  Đi qua đi lại liên tục #1 )  +  Mỗi bước đi #1 +  Lại gần goal #1 +  Lại gần checkpoint #1 +  Chạm checkpoint #1 +  Giữ hướng #1 +  Va chạm tường #1'
INSTANCE_CONFIGS = {
    "excess_rotate#1": {"eid": "excess_rotate", "weight": 1.0, "thresholds": {"MAX_ROTATE_STREAK": 2}},
    "excess_rotate#2": {"eid": "excess_rotate", "weight": 1.0, "thresholds": {"MAX_ROTATE_STREAK": 4}},
    "visit_window#1": {"eid": "visit_window", "weight": 1.0, "thresholds": {"MAX_REVISIT_STEPS": 5}},
    "visit_window#2": {"eid": "visit_window", "weight": 1.0, "thresholds": {"MAX_REVISIT_STEPS": 2}},
    "visit_repeat#1": {"eid": "visit_repeat", "weight": 1.0, "thresholds": {"MAX_CELL_REPEAT": 2}},
    "ping_pong#1": {
        "eid": "ping_pong",
        "weight": 1.0,
        "thresholds": {"MAX_PING_PONG_CYCLES": 1, "MAX_PING_PONG_SPAN": 4},
    },
}

_THRESHOLD_FOR_EID = {
    "cp_closer": ["CP_TARGET_INDEX"],
    "cp_farther": ["CP_TARGET_INDEX"],
    "checkpoint": ["CP_TARGET_INDEX"],
    "excess_rotate": ["MAX_ROTATE_STREAK"],
    "visit_window": ["MAX_REVISIT_STEPS"],
    "visit_repeat": ["MAX_CELL_REPEAT"],
    "ping_pong": ["MAX_PING_PONG_CYCLES", "MAX_PING_PONG_SPAN"],
    "straight_streak_reach": ["MAX_STRAIGHT_REACH"],
    "straight_streak_cap": ["MAX_STRAIGHT_CAP"],
}

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
    "R_ROTATE_TO_N",
    "R_ROTATE_TO_E",
    "R_ROTATE_TO_S",
    "R_ROTATE_TO_W",
    "R_FORWARD_N",
    "R_FORWARD_E",
    "R_FORWARD_S",
    "R_FORWARD_W",
    "R_FORWARD_NEW",
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
    "CP_TARGET_INDEX",
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


def set_instance_configs(configs):
    global INSTANCE_CONFIGS
    if not isinstance(configs, dict):
        INSTANCE_CONFIGS = {}
        return
    out = {}
    for iid, cfg in configs.items():
        if not isinstance(cfg, dict):
            continue
        eid = str(cfg.get("eid", "")).strip()
        if eid not in REWARD_ELEMENTS:
            continue
        try:
            weight = float(cfg.get("weight", DEFAULT_BLOCK_WEIGHT))
        except (TypeError, ValueError):
            weight = DEFAULT_BLOCK_WEIGHT
        thresholds = {}
        for k in (_THRESHOLD_FOR_EID.get(eid) or []):
            raw = (cfg.get("thresholds") or {}).get(k)
            if raw is None:
                continue
            try:
                thresholds[k] = int(raw)
            except (TypeError, ValueError):
                pass
        out[str(iid)] = {"eid": eid, "weight": weight, "thresholds": thresholds}
    INSTANCE_CONFIGS = out


def get_instance_configs():
    return dict(INSTANCE_CONFIGS)


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
    if "cp_closer" in element_weights:
        v = element_weights["cp_closer"]
        globals()["R_CP_CLOSER"] = v
    if "cp_farther" in element_weights:
        v = element_weights["cp_farther"]
        globals()["R_CP_FARTHER"] = v
    if "checkpoint" in element_weights:
        v = element_weights["checkpoint"]
        globals()["R_CHECKPOINT_FIRST"] = v
    if "straight_streak" in element_weights:
        globals()["R_STRAIGHT_REACH"] = element_weights["straight_streak"]
        globals()["R_STRAIGHT_CAP"] = element_weights["straight_streak"]


def _reward_instance_id(eid, idx):
    return "%s#%d" % (eid, idx)


def _threshold_instance_id(eid, idx, tk_key):
    return "%s#%d:%s" % (eid, idx, tk_key)


def _formula_tokens():
    labels = [meta["label"] for meta in REWARD_ELEMENTS.values()]
    return parse_expr_to_tokens(TOTAL_FORMULA_STUDENT, labels)


def _iter_formula_reward_instances(tokens):
    label_to_eid = {meta["label"]: eid for eid, meta in REWARD_ELEMENTS.items()}
    counts = {}
    for tok in tokens:
        if tok.get("kind") != "reward":
            continue
        eid = label_to_eid.get(tok.get("value"))
        if not eid:
            continue
        counts[eid] = counts.get(eid, 0) + 1
        idx = counts[eid]
        yield eid, idx, _reward_instance_id(eid, idx)


def _default_instance_cfg(eid):
    wkey = ELEMENT_WEIGHT_KEY.get(eid)
    weight = float(globals().get(wkey, DEFAULT_BLOCK_WEIGHT)) if wkey else DEFAULT_BLOCK_WEIGHT
    thresholds = {}
    for tk_key in _THRESHOLD_FOR_EID.get(eid, []):
        thresholds[tk_key] = int(globals().get(tk_key, 0))
    return {"eid": eid, "weight": weight, "thresholds": thresholds}


def _instance_cfg_for(eid, idx):
    iid = _reward_instance_id(eid, idx)
    cfg = INSTANCE_CONFIGS.get(iid)
    if cfg and cfg.get("eid") == eid:
        out = _default_instance_cfg(eid)
        out["weight"] = float(cfg.get("weight", out["weight"]))
        out["thresholds"].update(cfg.get("thresholds") or {})
        return out
    return _default_instance_cfg(eid)


def _ping_pong_count_for_span(robot, span_cells):
    hist = robot.get("pos_history") or []
    span_cells = max(1, int(span_cells))
    state = robot.setdefault("_ping_pong_counts_by_span", {})
    key = str(span_cells)
    rec = state.get(key) or {"hist_len": -1, "count": 0}
    if rec["hist_len"] == len(hist):
        return int(rec["count"])
    count = int(rec["count"])
    max_span = max(1, span_cells - 1)
    found = False
    for span in range(max_span, 0, -1):
        need = 2 * span + 1
        if len(hist) < need:
            continue
        segment = hist[-need:]
        if segment[0] == segment[-1] and segment == segment[::-1]:
            count += 1
            found = True
            break
    if not found and len(hist) >= 3 and len(set(hist[-3:])) == 3:
        count = 0
    rec["hist_len"] = len(hist)
    rec["count"] = count
    state[key] = rec
    return count


def _instance_ctx(base_ctx, robot, eid, cfg):
    c = dict(base_ctx)
    thresholds = dict(cfg.get("thresholds") or {})
    for k, v in thresholds.items():
        c[k] = int(v)
    wkey = ELEMENT_WEIGHT_KEY.get(eid) if eid else None
    if wkey:
        c[wkey] = float(cfg.get("weight", c.get(wkey, DEFAULT_BLOCK_WEIGHT)))

    max_rotate = int(c.get("MAX_ROTATE_STREAK", MAX_ROTATE_STREAK))
    max_revisit_steps = int(c.get("MAX_REVISIT_STEPS", MAX_REVISIT_STEPS))
    max_cell_repeat = int(c.get("MAX_CELL_REPEAT", MAX_CELL_REPEAT))
    max_ping_cycles = int(c.get("MAX_PING_PONG_CYCLES", MAX_PING_PONG_CYCLES))
    max_ping_span = int(c.get("MAX_PING_PONG_SPAN", MAX_PING_PONG_SPAN))
    max_straight_reach = int(c.get("MAX_STRAIGHT_REACH", MAX_STRAIGHT_REACH))
    max_straight_cap = int(c.get("MAX_STRAIGHT_CAP", MAX_STRAIGHT_CAP))
    cp_target_idx = int(c.get("CP_TARGET_INDEX", CP_TARGET_INDEX))
    cp_target_idx = max(1, min(3, cp_target_idx))

    rotate_streak = int(c.get("_rotate_streak", 0))
    spin_streak = int(c.get("_spin_streak", 0))
    no_progress = int(c.get("_no_progress", 0))
    repeat_visits = int(c.get("_repeat_visits", 0))
    straight_streak = int(c.get("_straight_streak", 0))
    revisit_gap = c.get("_revisit_gap")
    moved = bool(c.get("moved"))

    memory_spin_penalty = spin_streak >= max(3, max_rotate)
    memory_stagnation_penalty = no_progress >= 8
    memory_hard_stagnation_penalty = no_progress >= 16
    revisit_window_penalty = False
    if isinstance(revisit_gap, int) and max_revisit_steps > 0:
        revisit_window_penalty = revisit_gap <= max_revisit_steps

    ping_count = _ping_pong_count_for_span(robot, max_ping_span)

    c["excess_rotate"] = (rotate_streak > max_rotate) or memory_spin_penalty
    c["visit_window_penalty"] = revisit_window_penalty or memory_stagnation_penalty
    c["visit_repeat_penalty"] = (moved and repeat_visits > max_cell_repeat) or (spin_streak >= 6)
    c["ping_pong_penalty"] = (moved and ping_count > max_ping_cycles) or memory_hard_stagnation_penalty
    c["straight_streak_on"] = straight_streak >= max_straight_reach
    c["straight_streak_reach_on"] = moved and straight_streak >= max_straight_reach
    c["straight_streak_cap_on"] = moved and straight_streak <= max_straight_cap

    if eid in ("cp_closer", "cp_farther", "checkpoint"):
        suffix = str(cp_target_idx)
        c["cp_closer"] = bool(c.get("cp%s_closer" % suffix, False))
        c["cp_farther"] = bool(c.get("cp%s_farther" % suffix, False))
        c["at_cp_first"] = bool(c.get("at_cp%s_first" % suffix, False))
    c["cp_target_index"] = cp_target_idx
    return c


def _eval_total_from_tokens(tokens, instance_values):
    expr_parts = []
    vars_map = {}
    var_idx = 0
    label_to_eid = {meta["label"]: eid for eid, meta in REWARD_ELEMENTS.items()}
    counts = {}
    for tok in tokens:
        kind = tok.get("kind")
        if kind == "reward":
            eid = label_to_eid.get(tok.get("value"))
            if not eid:
                expr_parts.append("0.0")
                continue
            counts[eid] = counts.get(eid, 0) + 1
            iid = _reward_instance_id(eid, counts[eid])
            var_name = "_ri_%d" % var_idx
            var_idx += 1
            vars_map[var_name] = float(instance_values.get(iid, 0.0))
            expr_parts.append(var_name)
            continue
        if kind in ("op", "paren", "num"):
            expr_parts.append(str(tok.get("value", "")))
    if not expr_parts:
        return 0.0
    try:
        return safe_eval_formula(" ".join(expr_parts), vars_map)
    except (ValueError, SyntaxError, TypeError, ZeroDivisionError):
        return 0.0


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
    revisit_gap = None
    if moved:
        from robot import robot as rb

        rb.bump_ping_pong_count(robot, MAX_PING_PONG_SPAN)
        ping = robot.get("ping_pong_count", 0)
        hist = robot.get("pos_history") or []
        if len(hist) >= 2:
            key = hist[-1]
            for i in range(len(hist) - 2, -1, -1):
                if hist[i] == key:
                    revisit_gap = (len(hist) - 1) - i
                    break

    cp_closer_flags = [False, False, False]
    cp_farther_flags = [False, False, False]
    at_cp_first_flags = [False, False, False]
    at_cp_first_idx = None
    n_cp = sm.n_checkpoints(sim_map) if sim_map else 0
    visited = robot.get("cp_visited")
    if visited is None or not isinstance(visited, list) or len(visited) < n_cp:
        visited = [False] * n_cp
        robot["cp_visited"] = visited

    cp_trends = list(robot.get("dist_cp_trend", [0, 0, 0])[:3])
    while len(cp_trends) < 3:
        cp_trends.append(0)

    if moved and sim_map:
        for i in range(3):
            if i >= n_cp:
                continue
            if i >= len(visited) or visited[i]:
                continue
            ct = cp_trends[i]
            cp_closer_flags[i] = (ct == 1)
            cp_farther_flags[i] = (ct == -1)

    if "checkpoint_first_visited" in result:
        at_cp_first_idx = result.get("checkpoint_first_visited")
        if isinstance(at_cp_first_idx, int) and 0 <= at_cp_first_idx < 3:
            at_cp_first_flags[at_cp_first_idx] = True
    elif sim_map:
        for i in range(n_cp):
            if sm.is_at_checkpoint(sim_map, robot["x"], robot["y"], i):
                if i < len(visited) and not visited[i]:
                    at_cp_first_idx = i
                    at_cp_first_flags[i] = True
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

    # Reward-only memory (không đi vào encode_state):
    # - Phạt xoay tại chỗ kéo dài
    # - Phạt không tiến triển về goal trong nhiều bước liên tiếp
    cell = (robot.get("x"), robot.get("y"))
    anchor = robot.get("_reward_spin_anchor")
    spin_streak = int(robot.get("_reward_spin_streak", 0))
    no_progress = int(robot.get("_reward_no_progress_streak", 0))
    if rotated and not moved and not collision:
        if anchor == cell:
            spin_streak += 1
        else:
            spin_streak = 1
            anchor = cell
    else:
        if moved and trend == 1:
            spin_streak = 0
            anchor = None
        elif moved and trend != 1:
            spin_streak = max(0, spin_streak - 1)
    if collision:
        no_progress += 2
    elif moved:
        if trend == 1:
            no_progress = 0
        else:
            no_progress += 1
    elif rotated:
        no_progress += 1
    robot["_reward_spin_anchor"] = anchor
    robot["_reward_spin_streak"] = spin_streak
    robot["_reward_no_progress_streak"] = no_progress

    cp_closer = any(cp_closer_flags)
    cp_farther = any(cp_farther_flags)
    at_cp_first = any(at_cp_first_flags)

    ctx = dict(get_reward_dict())
    heading = str(robot.get("direct", "N")).upper()
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
            "cp1_closer": cp_closer_flags[0],
            "cp1_farther": cp_farther_flags[0],
            "cp2_closer": cp_closer_flags[1],
            "cp2_farther": cp_farther_flags[1],
            "cp3_closer": cp_closer_flags[2],
            "cp3_farther": cp_farther_flags[2],
            "at_cp1_first": at_cp_first_flags[0],
            "at_cp2_first": at_cp_first_flags[1],
            "at_cp3_first": at_cp_first_flags[2],
            "at_cp_first_idx": at_cp_first_idx,
            "facing_clear_on": facing_clear_on,
            "wasted_rotate_on": rotated and could_forward_before,
            "blocked_rotate_on": rotated and not could_forward_before,
            "rotate_to_n_on": rotated and heading == "N",
            "rotate_to_e_on": rotated and heading == "E",
            "rotate_to_s_on": rotated and heading == "S",
            "rotate_to_w_on": rotated and heading == "W",
            "forward_n_on": moved and heading == "N",
            "forward_e_on": moved and heading == "E",
            "forward_s_on": moved and heading == "S",
            "forward_w_on": moved and heading == "W",
            "forward_new_cell_on": moved and repeat_visits == 0,
            "_rotate_streak": int(streak),
            "_straight_streak": int(straight_streak),
            "_repeat_visits": int(repeat_visits),
            "_ping_pong_count": int(ping),
            "_revisit_gap": revisit_gap,
            "_spin_streak": int(spin_streak),
            "_no_progress": int(no_progress),
            "wall_detected": wall_first,
            "wall_visible": wall_on_rotate,
            "wall_first_discover": wall_first,
            "wall_on_rotate": wall_on_rotate,
            "wall_on_cell_entry": wall_on_cell_entry,
        }
    )
    # default flags with global thresholds (fallback khi chưa có instance config)
    return _instance_ctx(
        ctx,
        robot,
        None,
        {
            "weight": DEFAULT_BLOCK_WEIGHT,
            "thresholds": {
                "MAX_ROTATE_STREAK": MAX_ROTATE_STREAK,
                "MAX_REVISIT_STEPS": MAX_REVISIT_STEPS,
                "MAX_CELL_REPEAT": MAX_CELL_REPEAT,
                "MAX_PING_PONG_CYCLES": MAX_PING_PONG_CYCLES,
                "MAX_PING_PONG_SPAN": MAX_PING_PONG_SPAN,
                "MAX_STRAIGHT_REACH": MAX_STRAIGHT_REACH,
                "MAX_STRAIGHT_CAP": MAX_STRAIGHT_CAP,
                "CP_TARGET_INDEX": CP_TARGET_INDEX,
            },
        },
    )


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
    "R_ROTATE_TO_N if rotate_to_n_on else 0": lambda c: c["R_ROTATE_TO_N"] if c["rotate_to_n_on"] else 0.0,
    "R_ROTATE_TO_E if rotate_to_e_on else 0": lambda c: c["R_ROTATE_TO_E"] if c["rotate_to_e_on"] else 0.0,
    "R_ROTATE_TO_S if rotate_to_s_on else 0": lambda c: c["R_ROTATE_TO_S"] if c["rotate_to_s_on"] else 0.0,
    "R_ROTATE_TO_W if rotate_to_w_on else 0": lambda c: c["R_ROTATE_TO_W"] if c["rotate_to_w_on"] else 0.0,
    "R_FORWARD_N if forward_n_on else 0": lambda c: c["R_FORWARD_N"] if c["forward_n_on"] else 0.0,
    "R_FORWARD_E if forward_e_on else 0": lambda c: c["R_FORWARD_E"] if c["forward_e_on"] else 0.0,
    "R_FORWARD_S if forward_s_on else 0": lambda c: c["R_FORWARD_S"] if c["forward_s_on"] else 0.0,
    "R_FORWARD_W if forward_w_on else 0": lambda c: c["R_FORWARD_W"] if c["forward_w_on"] else 0.0,
    "R_FORWARD_NEW if forward_new_cell_on else 0": lambda c: c["R_FORWARD_NEW"] if c["forward_new_cell_on"] else 0.0,
    "R_EXCESS_ROTATE if excess_rotate else 0": lambda c: c["R_EXCESS_ROTATE"] if c["excess_rotate"] else 0.0,
    "R_VISIT_WINDOW if visit_window_penalty else 0": lambda c: c["R_VISIT_WINDOW"] if c["visit_window_penalty"] else 0.0,
    "R_VISIT_REPEAT if visit_repeat_penalty else 0": lambda c: c["R_VISIT_REPEAT"] if c["visit_repeat_penalty"] else 0.0,
    "R_PING_PONG if ping_pong_penalty else 0": lambda c: c["R_PING_PONG"] if c["ping_pong_penalty"] else 0.0,
    "R_STRAIGHT_REACH if straight_streak_reach_on else 0": lambda c: c["R_STRAIGHT_REACH"] if c["straight_streak_reach_on"] else 0.0,
    "R_STRAIGHT_CAP if straight_streak_cap_on else 0": lambda c: c["R_STRAIGHT_CAP"] if c["straight_streak_cap_on"] else 0.0,
}


def compute_reward_breakdown(robot, sim_map, result, action_name=None, could_forward_before=False, include_instances=False):
    """Trả (tổng, dict element); tùy chọn trả thêm breakdown theo từng instance."""
    tokens = _formula_tokens()
    if not tokens:
        return (0.0, {}, []) if include_instances else (0.0, {})

    base_ctx = _build_reward_context(robot, sim_map, result, could_forward_before)
    parts = {}
    instance_values = {}
    instance_rows = []
    for eid, idx, iid in _iter_formula_reward_instances(tokens):
        meta = REWARD_ELEMENTS.get(eid) or {}
        if meta.get("module") not in ENABLED_MODULES:
            instance_values[iid] = 0.0
            instance_rows.append({"iid": iid, "eid": eid, "idx": idx, "value": 0.0})
            continue
        cfg = _instance_cfg_for(eid, idx)
        ctx = _instance_ctx(base_ctx, robot, eid, cfg)
        formula = ELEMENT_FORMULAS.get(eid, meta.get("default_formula", "0"))
        if formula in _FAST_EVAL:
            val = _FAST_EVAL[formula](ctx)
        else:
            try:
                val = safe_eval_formula(formula, ctx)
            except (ValueError, SyntaxError, TypeError, ZeroDivisionError):
                val = 0.0
        instance_values[iid] = float(val)
        instance_rows.append({"iid": iid, "eid": eid, "idx": idx, "value": float(val)})
        parts[eid] = float(parts.get(eid, 0.0)) + float(val)
    total = _eval_total_from_tokens(tokens, instance_values)
    if include_instances:
        return total, parts, instance_rows
    return total, parts


def compute_reward(robot, sim_map, result, action_name=None, could_forward_before=False):
    total, _ = compute_reward_breakdown(
        robot, sim_map, result, action_name=action_name, could_forward_before=could_forward_before
    )
    return total
