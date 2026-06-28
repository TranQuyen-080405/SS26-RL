"""
RobotMap — memory trên robot (PC sim + ESP32).
Map = dict; node = dict.
"""

import sys
import os

_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from RL_lib.grid import (
    node_id,
    neighbor_xy,
    is_valid,
    OPPOSITE,
    OBSTACLE_KEYS,
)
from RL_lib.rl_core import N_CP_MAX


def _empty_robot_node(x, y):
    return {
        "x": x,
        "y": y,
        "id": node_id(x, y),
        "N_obstacle": 0,
        "W_obstacle": 0,
        "E_obstacle": 0,
        "S_obstacle": 0,
        "dist_goal": 0,
        "dist_checkpoint": [0] * N_CP_MAX,
    }


def _norm_xy(pt):
    if pt is None:
        return None
    return (int(pt[0]), int(pt[1]))


def init_robot_map(width, height, goal=None, checkpoints=None, start=None):
    rmap = {
        "width": width,
        "height": height,
        "nodes": {},
        "goal": _norm_xy(goal),
        "checkpoints": [_norm_xy(c) for c in (checkpoints or [])],
        "start": _norm_xy(start) or (0, 0),
    }
    for y in range(height):
        for x in range(width):
            rmap["nodes"][(x, y)] = _empty_robot_node(x, y)
    apply_boundary_walls(rmap)
    populate_all_distances(rmap)
    return rmap


def apply_walls_from_spec(robot_map, walls):
    """Ghi tường từ map JSON vào obstacle memory."""
    for w in walls or []:
        if isinstance(w, dict):
            x, y, d = int(w["x"]), int(w["y"]), w["dir"]
        else:
            x, y, d = int(w[0]), int(w[1]), w[2]
        set_obstacle(robot_map, x, y, d, True)


def apply_boundary_walls(robot_map):
    """Đặt tường ảo ở mép map — giống sim_map.get_block khi ra ngoài biên."""
    w, h = robot_map["width"], robot_map["height"]
    for y in range(h):
        set_obstacle(robot_map, 0, y, "W", True)
        set_obstacle(robot_map, w - 1, y, "E", True)
    for x in range(w):
        set_obstacle(robot_map, x, 0, "S", True)
        set_obstacle(robot_map, x, h - 1, "N", True)


def can_move(robot_map, x, y, direction):
    """Forward được không — mép map hoặc obstacle memory."""
    node = get_node(robot_map, x, y)
    if node is None:
        return False
    nx, ny = neighbor_xy(x, y, direction)
    if not is_valid(nx, ny, robot_map["width"], robot_map["height"]):
        return False
    return node[OBSTACLE_KEYS[direction]] == 0


def manhattan(x1, y1, x2, y2):
    return abs(x1 - x2) + abs(y1 - y2)


def dist_to_goal(robot_map, x, y):
    g = robot_map.get("goal")
    if g is None:
        return 0
    return manhattan(x, y, g[0], g[1])


def dist_to_checkpoints(robot_map, x, y):
    cps = robot_map.get("checkpoints") or []
    return [manhattan(x, y, cx, cy) for cx, cy in cps]


def is_at_goal(robot_map, x, y):
    g = robot_map.get("goal")
    return g is not None and (x, y) == g


def is_at_checkpoint(robot_map, x, y, index):
    cps = robot_map.get("checkpoints") or []
    if index < 0 or index >= len(cps):
        return False
    cx, cy = cps[index]
    return x == cx and y == cy


def n_checkpoints(robot_map):
    return len(robot_map.get("checkpoints") or [])


def refresh_node_distances(robot_map, x, y):
    """Ghi dist_goal / dist_checkpoint lên node (x, y) từ goal/checkpoints của map."""
    node = get_node(robot_map, x, y)
    if node is None:
        return
    set_distances(
        node,
        dist_to_goal(robot_map, x, y),
        dist_to_checkpoints(robot_map, x, y),
    )


def populate_all_distances(robot_map):
    """Tính và lưu khoảng cách Manhattan cho mọi ô trên RobotMap."""
    for x, y in robot_map["nodes"]:
        refresh_node_distances(robot_map, x, y)


def get_node(robot_map, x, y):
    if not is_valid(x, y, robot_map["width"], robot_map["height"]):
        return None
    return robot_map["nodes"].get((x, y))


def get_obstacle_nwes(node):
    return (
        node["N_obstacle"],
        node["W_obstacle"],
        node["E_obstacle"],
        node["S_obstacle"],
    )


def get_obstacle(node, direction):
    return node[OBSTACLE_KEYS[direction]]


def set_obstacle(robot_map, x, y, direction, blocked):
    node = get_node(robot_map, x, y)
    if node is None:
        return
    val = 1 if blocked else 0
    node[OBSTACLE_KEYS[direction]] = val
    nx, ny = neighbor_xy(x, y, direction)
    neighbor = get_node(robot_map, nx, ny)
    if neighbor is not None:
        neighbor[OBSTACLE_KEYS[OPPOSITE[direction]]] = val


def perceive_edge(robot_map, x, y, direction, is_blocked):
    """Cập nhật obstacle memory khi robot quét cạnh."""
    set_obstacle(robot_map, x, y, direction, is_blocked)


def set_distances(node, dist_goal, dist_cp_list):
    node["dist_goal"] = dist_goal
    for i in range(N_CP_MAX):
        if dist_cp_list and i < len(dist_cp_list):
            node["dist_checkpoint"][i] = dist_cp_list[i]
        else:
            node["dist_checkpoint"][i] = 0
