"""Robot state dict — MicroPython (tránh trùng tên module motor `robot`)."""

from modules.logics.grid import turn_left, turn_right
from modules.logics.rl_core import N_CP_MAX, dist_trend, encode_state
from modules.logics.robot_map import (
    get_node,
    get_obstacle_nwes,
    set_distances,
    dist_to_goal,
    dist_to_checkpoints,
    is_at_goal as map_is_at_goal,
    perceive_edge as _perceive_edge,
)


def make_robot(x, y, direction, robot_map):
    return {
        "x": x,
        "y": y,
        "direct": direction,
        "robot_map": robot_map,
        "prev_dist_goal": None,
        "prev_dist_cp": [None] * N_CP_MAX,
        "dist_goal_trend": 0,
        "dist_cp_trend": [0] * N_CP_MAX,
        "has_prev_node": False,
        "cp_visited": [],
        "rotate_streak": 0,
    }


def update_direction(robot, turn):
    if turn == "left":
        robot["direct"] = turn_left(robot["direct"])
    elif turn == "right":
        robot["direct"] = turn_right(robot["direct"])


def update_position(robot, x, y):
    robot["x"] = x
    robot["y"] = y


def snapshot_dist_before_move(robot):
    node = get_node(robot["robot_map"], robot["x"], robot["y"])
    if node is None:
        return
    robot["prev_dist_goal"] = node["dist_goal"]
    robot["prev_dist_cp"] = list(node["dist_checkpoint"])


def inject_distances(robot, dist_goal, dist_cp_list):
    node = get_node(robot["robot_map"], robot["x"], robot["y"])
    if node is None:
        return
    set_distances(node, dist_goal, dist_cp_list)


def inject_distances_from_map(robot):
    """Cập nhật dist trên node hiện tại từ goal/checkpoints lưu trong RobotMap."""
    rmap = robot["robot_map"]
    x, y = robot["x"], robot["y"]
    inject_distances(robot, dist_to_goal(rmap, x, y), dist_to_checkpoints(rmap, x, y))


def is_at_goal(robot):
    return map_is_at_goal(robot["robot_map"], robot["x"], robot["y"])


def compute_trends_after_move(robot):
    node = get_node(robot["robot_map"], robot["x"], robot["y"])
    if node is None or not robot["has_prev_node"]:
        robot["dist_goal_trend"] = 0
        robot["dist_cp_trend"] = [0] * N_CP_MAX
        return
    pg = robot["prev_dist_goal"]
    robot["dist_goal_trend"] = dist_trend(pg, node["dist_goal"]) if pg is not None else 0
    for i in range(N_CP_MAX):
        prev = robot["prev_dist_cp"][i]
        cur = node["dist_checkpoint"][i]
        robot["dist_cp_trend"][i] = dist_trend(prev, cur) if prev is not None else 0


def mark_moved(robot):
    robot["has_prev_node"] = True


def clear_move_trends(robot):
    """Xóa trend sau rotate / collision — chỉ forward mới cập nhật trend."""
    robot["dist_goal_trend"] = 0
    robot["dist_cp_trend"] = [0] * N_CP_MAX


def update_rotate_streak(robot, result):
    """Đếm mọi lần xoay tại chỗ liên tiếp (trái + phải gộp chung); reset khi forward."""
    if (
        result.get("success")
        and not result.get("moved")
        and not result.get("collision")
    ):
        robot["rotate_streak"] = robot.get("rotate_streak", 0) + 1
    else:
        robot["rotate_streak"] = 0


def build_encoded_state(robot):
    node = get_node(robot["robot_map"], robot["x"], robot["y"])
    if node is None:
        return 0
    obs = get_obstacle_nwes(node)
    return encode_state(
        obs,
        robot["dist_goal_trend"],
        robot["dist_cp_trend"],
        robot["direct"],
    )


def perceive_edge(robot, is_blocked):
    _perceive_edge(robot["robot_map"], robot["x"], robot["y"], robot["direct"], is_blocked)
