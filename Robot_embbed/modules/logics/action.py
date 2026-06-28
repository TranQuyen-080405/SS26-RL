"""
Action trên robot thật — cập nhật x,y,direct sau khi sensor xác nhận.
"""
from modules.logics.readSensor import read_obstacle
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

# from robot import robot  # TODO: motor API — forward_action, turn_left_angle, ...


def _commit_forward(robot):
    """Sau khi đã tới node mới (sim hoặc sensor xác nhận): cập nhật x,y và trend."""
    snapshot_dist_before_move(robot)
    d = robot["direct"]
    nx, ny = neighbor_xy(robot["x"], robot["y"], d)
    update_position(robot, nx, ny)
    inject_distances_from_map(robot)
    compute_trends_after_move(robot)
    mark_moved(robot)


def _finish_action(robot, result):
    update_rotate_streak(robot, result)
    return result


def forward_hw(robot):
    """
    Tiến 1 node trên robot thật:
    1. ultrasonic — tường phía trước
    2. TODO: forward_action() / read_line() == "node" — chờ tới mốc thật
    3. _commit_forward — cập nhật x,y, dist, trend (giống sim)
    """
    x, y, d = robot["x"], robot["y"], robot["direct"]
    print("[action] forward | pos (%d,%d) %s" % (x, y, d))

    if not can_move(robot["robot_map"], x, y, d):
        print("[action] forward BLOCKED (map edge)")
        clear_move_trends(robot)
        return _finish_action(robot, {"success": False, "moved": False, "collision": True})

    hit = read_obstacle(port=1)
    if hit:
        print("[action] forward BLOCKED (ultrasonic)")
        clear_move_trends(robot)
        return _finish_action(robot, {"success": False, "moved": False, "collision": True})

    # TODO: gọi motor (forward_action / follow_line) đến khi read_line() == "node"
    # Tạm thời nhảy tọa độ ngay để test logic RL (bỏ khi nối sensor node).
    print("[action] forward OK (placeholder — chưa gọi motor)")

    _commit_forward(robot)
    print("[action] forward done | pos (%d,%d) %s" % (robot["x"], robot["y"], robot["direct"]))
    return _finish_action(robot, {"success": True, "moved": True, "collision": False})


def rotate_left_hw(robot):
    # TODO: robot.turn_left_angle(90)
    old = robot["direct"]
    print("[action] rotate left | pos (%d,%d) %s" % (robot["x"], robot["y"], old))
    update_direction(robot, "left")
    clear_move_trends(robot)
    print("[action] rotate left done (placeholder — chưa gọi motor) | %s -> %s" % (old, robot["direct"]))
    return _finish_action(robot, {"success": True, "moved": False, "collision": False})


def rotate_right_hw(robot):
    # TODO: robot.turn_right_angle(90)
    old = robot["direct"]
    print("[action] rotate right | pos (%d,%d) %s" % (robot["x"], robot["y"], old))
    update_direction(robot, "right")
    clear_move_trends(robot)
    print("[action] rotate right done (placeholder — chưa gọi motor) | %s -> %s" % (old, robot["direct"]))
    return _finish_action(robot, {"success": True, "moved": False, "collision": False})


def execute_action(robot, action_name):
    if action_name == "forward":
        return forward_hw(robot)
    if action_name == "rotate left":
        return rotate_left_hw(robot)
    if action_name == "rotate right":
        return rotate_right_hw(robot)
    return _finish_action(robot, {"success": False, "moved": False, "collision": False})


def run_policy_step(robot):
    try:
        obs = read_obstacle(port=1)
    except Exception:
        obs = None
    if obs is not None:
        perceive_edge(robot, bool(obs))
    s = build_encoded_state(robot)
    name = get_policy_for_state(s)
    result = execute_action(robot, name)
    return name, result
