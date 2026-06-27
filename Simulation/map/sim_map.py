"""
SimMap — ground truth (chỉ PC / train).
Map = dict; không dùng class.
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
)


def _empty_node(x, y):
    return {"x": x, "y": y, "id": node_id(x, y)}


def init_sim_map(width, height, goal=None, checkpoints=None, start=None):
    """Tạo map GT: nodes + walls + goal/checkpoints."""
    sim = {
        "width": width,
        "height": height,
        "nodes": {},
        "walls": {},
        "goal": goal,
        "checkpoints": list(checkpoints or []),
        "start": start or (0, 0),
    }
    for y in range(height):
        for x in range(width):
            sim["nodes"][(x, y)] = _empty_node(x, y)
    return sim


def get_node(sim_map, x, y):
    if not is_valid(x, y, sim_map["width"], sim_map["height"]):
        return None
    return sim_map["nodes"].get((x, y))


def _apply_wall(sim_map, x, y, direction, blocked):
    key = (x, y, direction)
    if blocked:
        sim_map["walls"][key] = True
    else:
        sim_map["walls"].pop(key, None)


def set_wall(sim_map, x, y, direction, blocked=True):
    """Đặt vật cản trên cạnh (x,y)→direction; đồng bộ sang neighbor (OPPOSITE)."""
    blocked = bool(blocked)
    _apply_wall(sim_map, x, y, direction, blocked)
    nx, ny = neighbor_xy(x, y, direction)
    if is_valid(nx, ny, sim_map["width"], sim_map["height"]):
        _apply_wall(sim_map, nx, ny, OPPOSITE[direction], blocked)


def clear_wall(sim_map, x, y, direction):
    set_wall(sim_map, x, y, direction, False)


def get_block(sim_map, x, y, direction):
    """Oracle: cạnh có bị chặn không (biên map = tường)."""
    nx, ny = neighbor_xy(x, y, direction)
    if not is_valid(nx, ny, sim_map["width"], sim_map["height"]):
        return True
    if sim_map["walls"].get((x, y, direction), False):
        return True
    return sim_map["walls"].get((nx, ny, OPPOSITE[direction]), False)


def can_move(sim_map, x, y, direction):
    return not get_block(sim_map, x, y, direction)


def manhattan(x1, y1, x2, y2):
    return abs(x1 - x2) + abs(y1 - y2)


def dist_to_goal(sim_map, x, y):
    g = sim_map.get("goal")
    if g is None:
        return 0
    return manhattan(x, y, g[0], g[1])


def dist_to_checkpoints(sim_map, x, y):
    cps = sim_map.get("checkpoints") or []
    return [manhattan(x, y, cx, cy) for cx, cy in cps]


def is_at_goal(sim_map, x, y):
    g = sim_map.get("goal")
    return g is not None and (x, y) == tuple(g)


def is_at_checkpoint(sim_map, x, y, index):
    cps = sim_map.get("checkpoints") or []
    if index < 0 or index >= len(cps):
        return False
    cx, cy = cps[index]
    return x == cx and y == cy


def n_checkpoints(sim_map):
    return len(sim_map.get("checkpoints") or [])
