"""Hằng số lưới — bản MicroPython (sync từ RL_lib/grid.py)."""

DIRECTIONS = ("N", "W", "E", "S")
# Chiều xoay nhìn từ trên (N lên): phải = kim đồng hồ N→E→S→W
_TURN_ORDER = ("N", "E", "S", "W")
DIR_DELTA_ID = {"N": 10, "S": -10, "E": 1, "W": -1}
DIR_DELTA_XY = {"N": (0, 1), "S": (0, -1), "E": (1, 0), "W": (-1, 0)}
OPPOSITE = {"N": "S", "S": "N", "E": "W", "W": "E"}
OBSTACLE_KEYS = {
    "N": "N_obstacle",
    "W": "W_obstacle",
    "E": "E_obstacle",
    "S": "S_obstacle",
}


def node_id(x, y):
    return y * 10 + x


def neighbor_xy(x, y, direction):
    dx, dy = DIR_DELTA_XY[direction]
    return x + dx, y + dy


def is_valid(x, y, width, height):
    return 0 <= x < width and 0 <= y < height


def turn_left(direction):
    i = _TURN_ORDER.index(direction)
    return _TURN_ORDER[(i - 1) % 4]


def turn_right(direction):
    i = _TURN_ORDER.index(direction)
    return _TURN_ORDER[(i + 1) % 4]
