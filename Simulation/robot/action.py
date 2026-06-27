"""
Action — Simulation cập nhật x,y,direct; ESP32 có TODO motor/sensor.
"""

import sys
import os

_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
_SIM = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)
if _SIM not in sys.path:
    sys.path.insert(0, _SIM)

from RL_lib.grid import neighbor_xy
from map import sim_map as sm
from robot import robot as rb


def _finish_action(robot, result):
    rb.update_rotate_streak(robot, result)
    return result


def execute_action_sim(robot, sim_map, action_name):
    """Simulation: cập nhật vị trí / hướng; sau mỗi action quét tường hướng đang nhìn."""
    if action_name == "forward":
        d = robot["direct"]
        x, y = robot["x"], robot["y"]
        if not sm.can_move(sim_map, x, y, d):
            rb.perceive_facing_from_sim(robot, sim_map)
            rb.clear_move_trends(robot)
            return _finish_action(robot, {"success": False, "moved": False, "collision": True})
        rb.snapshot_dist_before_move(robot)
        nx, ny = neighbor_xy(x, y, d)
        rb.update_position(robot, nx, ny)
        rb.inject_distances(
            robot,
            sm.dist_to_goal(sim_map, nx, ny),
            sm.dist_to_checkpoints(sim_map, nx, ny),
        )
        rb.compute_trends_after_move(robot)
        rb.mark_moved(robot)
        rb.perceive_facing_from_sim(robot, sim_map)
        return _finish_action(robot, {"success": True, "moved": True, "collision": False})

    if action_name == "rotate left":
        rb.update_direction(robot, "left")
        rb.clear_move_trends(robot)
        rb.perceive_facing_from_sim(robot, sim_map)
        return _finish_action(robot, {"success": True, "moved": False, "collision": False})

    if action_name == "rotate right":
        rb.update_direction(robot, "right")
        rb.clear_move_trends(robot)
        rb.perceive_facing_from_sim(robot, sim_map)
        return _finish_action(robot, {"success": True, "moved": False, "collision": False})

    return _finish_action(robot, {"success": False, "moved": False, "collision": False})


def execute_action_hw(robot, sim_map, action_name):
    """
  Robot thật: cập nhật direct / (x,y) giống sim sau khi xác nhận sensor.
  TODO: gọi motor + chờ node / ultrasonic trước khi update_position.
    """
    if action_name == "forward":
        # TODO: forward_action() / read_line() == "node" → mới gọi update_position
        # TODO: read_obstacle() trước khi tiến
        return execute_action_sim(robot, sim_map, action_name)

    if action_name == "rotate left":
        # TODO: robot.turn_left_angle(90)
        rb.update_direction(robot, "left")
        return _finish_action(robot, {"success": True, "moved": False, "collision": False})

    if action_name == "rotate right":
        # TODO: robot.turn_right_angle(90)
        rb.update_direction(robot, "right")
        return _finish_action(robot, {"success": True, "moved": False, "collision": False})

    return _finish_action(robot, {"success": False, "moved": False, "collision": False})
