"""
Action trên robot thật — cập nhật x,y,direct sau khi sensor xác nhận.
"""

from grid import neighbor_xy
from robot_state import (
    update_direction,
    update_position,
    snapshot_dist_before_move,
    inject_distances,
    compute_trends_after_move,
    mark_moved,
    build_encoded_state,
    perceive_edge,
    update_rotate_streak,
    clear_move_trends,
)
from readSensor import read_obstacle
from rl_core import get_policy

# from robot import robot  # TODO: motor API — forward_action, turn_left_angle, ...


def _commit_forward(robot, dist_goal, dist_cp_list):
    """Sau khi đã tới node mới (sim hoặc sensor xác nhận): cập nhật x,y và trend."""
    snapshot_dist_before_move(robot)
    d = robot["direct"]
    nx, ny = neighbor_xy(robot["x"], robot["y"], d)
    update_position(robot, nx, ny)
    inject_distances(robot, dist_goal, dist_cp_list)
    compute_trends_after_move(robot)
    mark_moved(robot)


def _finish_action(robot, result):
    update_rotate_streak(robot, result)
    return result


def forward_hw(robot, dist_goal, dist_cp_list):
    """
    Tiến 1 node trên robot thật:
    1. ultrasonic — tường phía trước
    2. TODO: forward_action() / read_line() == "node" — chờ tới mốc thật
    3. _commit_forward — cập nhật x,y, dist, trend (giống sim)
    """
    hit = read_obstacle(port=1)
    if hit:
        clear_move_trends(robot)
        return _finish_action(robot, {"success": False, "moved": False, "collision": True})

    # TODO: gọi motor (forward_action / follow_line) đến khi read_line() == "node"
    # Tạm thời nhảy tọa độ ngay để test logic RL (bỏ khi nối sensor node).

    _commit_forward(robot, dist_goal, dist_cp_list or [0, 0, 0])
    return _finish_action(robot, {"success": True, "moved": True, "collision": False})


def rotate_left_hw(robot):
    # TODO: robot.turn_left_angle(90)
    update_direction(robot, "left")
    clear_move_trends(robot)
    return _finish_action(robot, {"success": True, "moved": False, "collision": False})


def rotate_right_hw(robot):
    # TODO: robot.turn_right_angle(90)
    update_direction(robot, "right")
    clear_move_trends(robot)
    return _finish_action(robot, {"success": True, "moved": False, "collision": False})


def execute_action(robot, action_name, dist_goal=0, dist_cp_list=None):
    if action_name == "forward":
        return forward_hw(robot, dist_goal, dist_cp_list)
    if action_name == "rotate left":
        return rotate_left_hw(robot)
    if action_name == "rotate right":
        return rotate_right_hw(robot)
    return _finish_action(robot, {"success": False, "moved": False, "collision": False})


def run_policy_step(robot, q_table, dist_goal=0, dist_cp_list=None):
    obs = read_obstacle(port=1)
    if obs is not None:
        perceive_edge(robot, bool(obs))
    s = build_encoded_state(robot)
    name = get_policy(s, q_table)
    return execute_action(robot, name, dist_goal, dist_cp_list)
