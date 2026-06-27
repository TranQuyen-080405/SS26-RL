"""
Bộ map train (10×10) + map general eval (lớn hơn).
Mỗi spec: start, goal, checkpoints, path (đường đi hợp lệ) → tường chặn mọi cạnh ngoài path.
"""

import sys
import os

_MAP = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
_ROOT = os.path.abspath(os.path.join(_MAP, ".."))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)
if _MAP not in sys.path:
    sys.path.insert(0, _MAP)

from RL_lib.grid import DIRECTIONS, is_valid, neighbor_xy
from map import sim_map as sm


def _adjacent(a, b):
    ax, ay = a
    bx, by = b
    return abs(ax - bx) + abs(ay - by) == 1


def validate_path(path, width, height):
    if len(path) < 2:
        raise ValueError("path quá ngắn")
    for x, y in path:
        if not is_valid(x, y, width, height):
            raise ValueError("path ra ngoài map: (%d,%d)" % (x, y))
    for i in range(len(path) - 1):
        if not _adjacent(path[i], path[i + 1]):
            raise ValueError("path không liên tục: %s -> %s" % (path[i], path[i + 1]))


def walls_from_path(sim, path):
    """Chặn mọi cạnh không thuộc path → hành lang duy nhất theo path."""
    w, h = sim["width"], sim["height"]
    open_edges = set()
    for i in range(len(path) - 1):
        a, b = path[i], path[i + 1]
        open_edges.add((a, b))
        open_edges.add((b, a))
    for y in range(h):
        for x in range(w):
            for d in DIRECTIONS:
                nx, ny = neighbor_xy(x, y, d)
                if not is_valid(nx, ny, w, h):
                    continue
                if ((x, y), (nx, ny)) not in open_edges:
                    sm.set_wall(sim, x, y, d, True)


def build_map(spec):
    """Tạo sim_map từ spec dict."""
    validate_path(spec["path"], spec["width"], spec["height"])
    sim = sm.init_sim_map(
        spec["width"],
        spec["height"],
        goal=tuple(spec["goal"]),
        checkpoints=[tuple(c) for c in spec["checkpoints"]],
        start=tuple(spec["start"]),
    )
    walls_from_path(sim, spec["path"])
    sim["name"] = spec.get("name", "unnamed")
    return sim


# --- Train: 4 map 10×10, layout khác nhau, cùng kiểu start/CP/goal ---
MAZE_A = {
    "name": "train_a",
    "width": 10,
    "height": 10,
    "start": (0, 0),
    "goal": (9, 5),
    "checkpoints": [(2, 2)],
    "path": [
        (0, 0), (0, 1), (0, 2), (1, 2), (2, 2),
        (3, 2), (4, 2), (5, 2), (6, 2), (7, 2), (7, 3),
        (7, 4), (7, 5), (6, 5), (5, 5), (4, 5), (3, 5), (2, 5),
        (2, 6), (2, 7), (3, 7), (4, 7), (5, 7), (6, 7), (7, 7),
        (8, 7), (9, 7), (9, 6), (9, 5),
    ],
}

MAZE_B = {
    "name": "train_b",
    "width": 10,
    "height": 10,
    "start": (0, 0),
    "goal": (9, 5),
    "checkpoints": [(2, 2)],
    "path": [
        (0, 0), (1, 0), (2, 0), (3, 0), (3, 1), (3, 2), (2, 2),
        (2, 3), (2, 4), (2, 5), (3, 5), (4, 5), (5, 5), (6, 5),
        (7, 5), (8, 5), (9, 5),
    ],
}

MAZE_C = {
    "name": "train_c",
    "width": 10,
    "height": 10,
    "start": (0, 0),
    "goal": (9, 5),
    "checkpoints": [(4, 3)],
    "path": [
        (0, 0), (0, 1), (0, 2), (1, 2), (2, 2), (3, 2), (3, 3), (4, 3),
        (5, 3), (6, 3), (7, 3), (7, 4), (7, 5), (8, 5), (9, 5),
    ],
}

MAZE_D = {
    "name": "train_d",
    "width": 10,
    "height": 10,
    "start": (0, 0),
    "goal": (9, 9),
    "checkpoints": [(2, 4)],
    "path": [
        (0, 0), (0, 1), (0, 2), (0, 3), (0, 4), (1, 4), (2, 4),
        (3, 4), (4, 4), (5, 4), (6, 4), (7, 4), (8, 4), (9, 4),
        (9, 5), (9, 6), (9, 7), (9, 8), (9, 9),
    ],
}

TRAIN_MAP_SPECS = [MAZE_A, MAZE_B, MAZE_C, MAZE_D]

# --- Eval: map lớn hơn (14×14), chưa thấy khi train ---
GENERAL_EVAL_SPEC = {
    "name": "general_14",
    "width": 14,
    "height": 14,
    "start": (0, 0),
    "goal": (13, 9),
    "checkpoints": [(6, 4)],
    "path": [
        (0, 0), (0, 1), (0, 2), (0, 3), (1, 3), (2, 3), (3, 3), (4, 3),
        (5, 3), (6, 3), (6, 4), (6, 5), (5, 5), (4, 5), (4, 6), (4, 7),
        (5, 7), (6, 7), (7, 7), (8, 7), (9, 7), (10, 7), (11, 7), (12, 7),
        (13, 7), (13, 8), (13, 9),
    ],
}


def build_train_maps():
    return [build_map(s) for s in TRAIN_MAP_SPECS]


def build_general_eval_map():
    return build_map(GENERAL_EVAL_SPEC)
