"""
Robot state — dict + hàm thuần (Simulation).
"""

from RL_lib.grid import turn_left, turn_right
from RL_lib.rl_core import N_CP_MAX, dist_trend, encode_state
from robot.robot_map import (
    get_node,
    get_obstacle_nwes,
    set_distances,
    dist_to_goal,
    dist_to_checkpoints,
    is_at_goal as map_is_at_goal,
    perceive_edge as _perceive_edge,
)


def make_robot(x, y, direction, robot_map):
    n_cp = len(robot_map.get("checkpoints") or [])
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
        "cp_visited": [False] * n_cp,
        "rotate_streak": 0,
        "straight_streak": 0,
    }


def reset_cp_visited(robot, n_cp):
    robot["cp_visited"] = [False] * max(n_cp, 0)


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
    visited = robot.get("cp_visited") or []
    for i in range(N_CP_MAX):
        if i < len(visited) and visited[i]:
            robot["dist_cp_trend"][i] = 0
        else:
            prev = robot["prev_dist_cp"][i]
            cur = node["dist_checkpoint"][i]
            robot["dist_cp_trend"][i] = dist_trend(prev, cur) if prev is not None else 0
    robot["has_prev_node"] = True


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


def update_straight_streak(robot, result):
    """Đếm số lần đi thẳng liên tiếp thành công (chỉ forward thành công mới tăng; reset khi xoay thành công hoặc va chạm)."""
    moved = bool(result.get("success") and result.get("moved") and not result.get("collision"))
    if moved:
        robot["straight_streak"] = robot.get("straight_streak", 0) + 1
    else:
        robot["straight_streak"] = 0


def reset_explore_tracking(robot):
    """Reset đếm lặp ô / ping-pong đầu episode."""
    robot["node_visits"] = {}
    robot["pos_history"] = [(robot["x"], robot["y"])]
    robot["ping_pong_count"] = 0
    robot["_ping_pong_hist_len"] = 1


def update_explore_on_move(robot):
    """Sau forward thành công — đếm lần vào ô và chu kỳ A↔B."""
    key = (robot["x"], robot["y"])
    visits = robot.get("node_visits")
    if visits is None:
        visits = {}
        robot["node_visits"] = visits
    visits[key] = visits.get(key, 0) + 1

    hist = robot.setdefault("pos_history", [])
    hist.append(key)
    if len(hist) > 128:
        del hist[:-128]


def bump_ping_pong_count(robot, max_cells_per_leg):
    """Đếm lần đi qua-lại trên một đoạn thẳng (palindrome), tối đa max_cells_per_leg ô mỗi chiều."""
    hist = robot.get("pos_history") or []
    if robot.get("_ping_pong_hist_len") == len(hist):
        return
    robot["_ping_pong_hist_len"] = len(hist)
    count = robot.get("ping_pong_count", 0)
    max_span = max(1, int(max_cells_per_leg) - 1)
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
    robot["ping_pong_count"] = count


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


def clear_obstacle_memory(robot):
    """Xóa bộ nhớ tường trên RobotMap (đầu episode)."""
    for node in robot["robot_map"]["nodes"].values():
        node["N_obstacle"] = 0
        node["W_obstacle"] = 0
        node["E_obstacle"] = 0
        node["S_obstacle"] = 0


def perceive_facing_from_sim(robot, sim_map):
    """Cập nhật obstacle hướng đang nhìn — muốn quét S phải rotate tới S trước."""
    from map import sim_map as sm

    is_wall = sm.get_block(sim_map, robot["x"], robot["y"], robot["direct"])
    perceive_edge(robot, is_wall)
