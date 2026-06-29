"""
Action trên robot thật — cập nhật x,y,direct sau khi sensor xác nhận.

bot: dict state RL (x, y, direct, robot_map, …)
robot: module xBot (from robot import robot) — motor / xoay
"""
import time

from modules.logics.readSensor import read_obstacle, read_line
from modules.logics.grid import neighbor_xy
from modules.logics.robot_state import (
    update_direction,
    update_position,
    snapshot_dist_before_move,
    inject_distances_from_map,
    compute_trends_after_move,
    mark_moved,
    build_encoded_state,
    perceive_edge,
    update_rotate_streak,
    clear_move_trends,
)
from modules.logics.policy_io import get_policy_for_state
from modules.logics.robot_map import can_move

from robot import robot

_LINE_PORT = 0
_US_PORT = 1
_FOLLOW_SPEED = 25
_LOST_BACK_SPEED = 6
_FOLLOW_LOOP_MS = 12


def _drive_stop():
    try:
        robot.stop()
    except Exception:
        pass


def _obstacle_hit():
    return bool(read_obstacle(port=_US_PORT))


def _follow_line_step(port=_LINE_PORT):
    """Một bước bám — trả mode từ read_line (không dừng ở node)."""
    mode = read_line(port)
    if mode == "lost":
        robot.backward(_LOST_BACK_SPEED)
    elif mode == "forward" or mode == "node":
        robot.forward(_FOLLOW_SPEED)
    elif mode == "left":
        robot.turn_left(10)
    elif mode == "right":
        robot.turn_right(10)
    return mode


def _follow_line_to_next_node(port=_LINE_PORT):
    """
    Tiến tới node kế: nếu đang đứng trên node (4 sensor đen) thì chạy ra trước,
    rồi bám line đến khi gặp node tiếp theo.
    """
    while read_line(port) == "node":
        robot.forward(_FOLLOW_SPEED)
        if _obstacle_hit():
            _drive_stop()
            return False
        time.sleep_ms(_FOLLOW_LOOP_MS)

    while True:
        mode = _follow_line_step(port)
        if mode == "node":
            _drive_stop()
            return True
        if _obstacle_hit():
            _drive_stop()
            return False
        time.sleep_ms(_FOLLOW_LOOP_MS)


def _commit_forward(bot):
    """Sau khi đã tới node mới (sensor xác nhận): cập nhật x,y và trend."""
    snapshot_dist_before_move(bot)
    d = bot["direct"]
    nx, ny = neighbor_xy(bot["x"], bot["y"], d)
    update_position(bot, nx, ny)
    inject_distances_from_map(bot)
    compute_trends_after_move(bot)
    # Cập nhật danh sách checkpoint đã đi qua khi chạy thật
    cps = bot["robot_map"].get("checkpoints") or []
    visited = bot.get("cp_visited") or []
    for i, (cx, cy) in enumerate(cps):
        if bot["x"] == cx and bot["y"] == cy and i < len(visited):
            visited[i] = True
    mark_moved(bot)


def _finish_action(bot, result):
    update_rotate_streak(bot, result)
    return result


def forward_hw(bot):
    """
    Tiến 1 node trên robot thật:
    1. ultrasonic — tường phía trước
    2. follow line đến khi cả 4 sensor line đen (node)
    3. _commit_forward — cập nhật x,y, dist, trend (giống sim)
    """
    x, y, d = bot["x"], bot["y"], bot["direct"]

    if not can_move(bot["robot_map"], x, y, d):
        clear_move_trends(bot)
        return _finish_action(bot, {"success": False, "moved": False, "collision": True})

    hit = read_obstacle(port=_US_PORT)
    if hit:
        clear_move_trends(bot)
        return _finish_action(bot, {"success": False, "moved": False, "collision": True})

    if not _follow_line_to_next_node(_LINE_PORT):
        clear_move_trends(bot)
        return _finish_action(bot, {"success": False, "moved": False, "collision": True})

    _commit_forward(bot)
    return _finish_action(bot, {"success": True, "moved": True, "collision": False})


def rotate_left_hw(bot):
    robot.turn_left_angle(80)
    update_direction(bot, "left")
    clear_move_trends(bot)
    return _finish_action(bot, {"success": True, "moved": False, "collision": False})


def rotate_right_hw(bot):
    robot.turn_right_angle(80)
    update_direction(bot, "right")
    clear_move_trends(bot)
    return _finish_action(bot, {"success": True, "moved": False, "collision": False})


def execute_action(bot, action_name):
    if action_name == "forward":
        return forward_hw(bot)
    if action_name == "rotate left":
        return rotate_left_hw(bot)
    if action_name == "rotate right":
        return rotate_right_hw(bot)
    return _finish_action(bot, {"success": False, "moved": False, "collision": False})


def run_policy_step(bot):
    try:
        obs = read_obstacle(port=_US_PORT)
    except Exception:
        obs = None
    if obs is not None:
        perceive_edge(bot, bool(obs))
    s = build_encoded_state(bot)
    name = get_policy_for_state(s)
    result = execute_action(bot, name)
    time.sleep_ms(3000)
    return name, result
