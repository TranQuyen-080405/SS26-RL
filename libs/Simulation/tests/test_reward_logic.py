import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
SIM = os.path.join(ROOT, "Simulation")
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
if SIM not in sys.path:
    sys.path.insert(0, SIM)

from RL_lib import reward_config
from RL_lib.reward_config import _build_reward_context
from map.sim_map import init_sim_map, set_wall
from robot import robot as rb
from robot.robot_map import init_robot_map


def _robot_at_wall_facing_north():
    sm = init_sim_map(5, 5, goal=(4, 4), start=(0, 0))
    set_wall(sm, 1, 1, "N", True)
    rmap = init_robot_map(5, 5, goal=(4, 4), start=(0, 0))
    robot = rb.make_robot(1, 1, "N", rmap)
    rb.clear_obstacle_memory(robot)
    return robot, sm


def test_wall_on_entry_no_reward_without_memory():
    """Tường thật ở cạnh bên nhưng memory chưa biết — không cộng."""
    sm = init_sim_map(5, 5, goal=(4, 4), start=(0, 0))
    set_wall(sm, 1, 1, "N", True)
    rmap = init_robot_map(5, 5, goal=(4, 4), start=(0, 0))
    robot = rb.make_robot(0, 1, "E", rmap)
    rb.clear_obstacle_memory(robot)

    from robot import action as act

    act.execute_action_sim(robot, sm, "forward")
    node = rmap["nodes"][(1, 1)]
    assert node["N_obstacle"] == 0
    forward_result = {"success": True, "moved": True, "collision": False}
    ctx = _build_reward_context(robot, sm, forward_result)
    assert ctx["wall_on_cell_entry"] is False


def test_wall_on_entry_when_memory_has_wall():
    """Tiến vào ô, hướng nhìn có tường trong memory — cộng điểm."""
    sm = init_sim_map(5, 5, goal=(4, 4), start=(0, 0))
    set_wall(sm, 0, 1, "N", True)
    rmap = init_robot_map(5, 5, goal=(4, 4), start=(0, 0))
    robot = rb.make_robot(0, 0, "N", rmap)
    rb.clear_obstacle_memory(robot)

    from robot import action as act

    act.execute_action_sim(robot, sm, "forward")
    forward_result = {"success": True, "moved": True, "collision": False}
    ctx = _build_reward_context(robot, sm, forward_result)
    assert robot["x"] == 0 and robot["y"] == 1
    assert rmap["nodes"][(0, 1)]["N_obstacle"] == 1
    assert ctx["wall_on_cell_entry"] is True


def test_wall_on_entry_repeats_each_visit():
    """Quay lại ô đã biết tường — vẫn cộng mỗi lần tiến vào."""
    sm = init_sim_map(5, 5, goal=(4, 4), start=(0, 0))
    set_wall(sm, 0, 1, "N", True)
    rmap = init_robot_map(5, 5, goal=(4, 4), start=(0, 0))
    robot = rb.make_robot(0, 0, "N", rmap)
    rb.clear_obstacle_memory(robot)

    from robot import action as act

    act.execute_action_sim(robot, sm, "forward")
    ctx1 = _build_reward_context(robot, sm, {"success": True, "moved": True, "collision": False})
    assert ctx1["wall_on_cell_entry"] is True

    act.execute_action_sim(robot, sm, "rotate left")
    act.execute_action_sim(robot, sm, "forward")
    act.execute_action_sim(robot, sm, "rotate right")
    act.execute_action_sim(robot, sm, "forward")
    ctx2 = _build_reward_context(robot, sm, {"success": True, "moved": True, "collision": False})
    assert ctx2["wall_on_cell_entry"] is True


def test_obstacle_unknown_until_facing():
    """Bộ nhớ tường chỉ cập nhật hướng robot đang nhìn — không quét trước."""
    sm = init_sim_map(5, 5, goal=(4, 4), start=(0, 0))
    set_wall(sm, 0, 0, "N", True)
    rmap = init_robot_map(5, 5, goal=(4, 4), start=(0, 0))
    robot = rb.make_robot(0, 0, "E", rmap)
    node = rmap["nodes"][(0, 0)]
    assert node["N_obstacle"] == 0
    assert node["E_obstacle"] == 0

    rb.perceive_facing_from_sim(robot, sm, for_reward=False)
    assert node["N_obstacle"] == 0
    assert node["E_obstacle"] == 0

    robot["direct"] = "N"
    rb.perceive_facing_from_sim(robot, sm, for_reward=True)
    assert node["N_obstacle"] == 1


def test_boundary_wall_requires_facing():
    sm = init_sim_map(5, 5, goal=(4, 4), start=(0, 0))
    rmap = init_robot_map(5, 5, goal=(4, 4), start=(0, 0))
    robot = rb.make_robot(0, 0, "W", rmap)
    node = rmap["nodes"][(0, 0)]
    assert node["W_obstacle"] == 0
    rb.perceive_facing_from_sim(robot, sm, for_reward=True)
    assert node["W_obstacle"] == 1


def test_wall_first_discover_on_forward_collision():
    """Tiến thẳng vào tường — vẫn cộng lần đầu (reset không ăn điểm)."""
    sm = init_sim_map(5, 5, goal=(4, 4), start=(0, 0))
    set_wall(sm, 0, 0, "N", True)
    rmap = init_robot_map(5, 5, goal=(4, 4), start=(0, 0))
    robot = rb.make_robot(0, 0, "N", rmap)
    rb.clear_obstacle_memory(robot)
    rb.perceive_facing_from_sim(robot, sm, for_reward=False)

    from robot import action as act

    act.execute_action_sim(robot, sm, "forward")
    collision_result = {"success": False, "moved": False, "collision": True}
    ctx = _build_reward_context(robot, sm, collision_result)
    assert ctx["wall_detected"] is True
    assert ctx["wall_visible"] is False


def test_wall_first_discover_only_once():
    robot, sm = _robot_at_wall_facing_north()

    rb.perceive_facing_from_sim(robot, sm)
    assert robot["_reward_wall_first"] is True

    rotate_result = {"success": True, "moved": False, "collision": False}
    ctx = _build_reward_context(robot, sm, rotate_result)
    assert ctx["wall_detected"] is True
    assert ctx["wall_visible"] is True

    rb.perceive_facing_from_sim(robot, sm)
    assert robot["_reward_wall_first"] is False

    ctx2 = _build_reward_context(robot, sm, rotate_result)
    assert ctx2["wall_detected"] is False
    assert ctx2["wall_visible"] is True


def test_wall_visible_only_on_rotate():
    robot, sm = _robot_at_wall_facing_north()
    rb.perceive_facing_from_sim(robot, sm)

    forward_result = {"success": True, "moved": True, "collision": False}
    ctx = _build_reward_context(robot, sm, forward_result)
    assert ctx["wall_visible"] is False

    side_wall = init_sim_map(5, 5, goal=(4, 4), start=(0, 0))
    set_wall(side_wall, 1, 1, "E", True)
    rb.clear_obstacle_memory(robot)
    rb.perceive_facing_from_sim(robot, side_wall)
    ctx_side = _build_reward_context(robot, side_wall, forward_result)
    assert ctx_side["wall_detected"] is False
    assert ctx_side["wall_visible"] is False


def test_rotate_split():
    robot = {"x": 1, "y": 1, "direct": "N"}
    sim_map = {"width": 3, "height": 3, "walls": {}}
    result = {"success": True, "moved": False, "collision": False}

    ctx_wasted = _build_reward_context(robot, sim_map, result, could_forward_before=True)
    assert ctx_wasted["rotated"] is True
    assert ctx_wasted["wasted_rotate_on"] is True
    assert ctx_wasted["blocked_rotate_on"] is False

    ctx_blocked = _build_reward_context(robot, sim_map, result, could_forward_before=False)
    assert ctx_blocked["rotated"] is True
    assert ctx_blocked["wasted_rotate_on"] is False
    assert ctx_blocked["blocked_rotate_on"] is True


def test_straight_streak_split():
    robot = {"x": 1, "y": 1, "direct": "N", "straight_streak": 2}
    sim_map = {"width": 3, "height": 3, "walls": {}}
    result = {"moved": True}

    reward_config.MAX_STRAIGHT_REACH = 3
    reward_config.MAX_STRAIGHT_CAP = 3

    ctx1 = _build_reward_context(robot, sim_map, result)
    assert ctx1["straight_streak_reach_on"] is False
    assert ctx1["straight_streak_cap_on"] is True

    robot["straight_streak"] = 3
    ctx2 = _build_reward_context(robot, sim_map, result)
    assert ctx2["straight_streak_reach_on"] is True
    assert ctx2["straight_streak_cap_on"] is True

    robot["straight_streak"] = 4
    ctx3 = _build_reward_context(robot, sim_map, result)
    assert ctx3["straight_streak_reach_on"] is True
    assert ctx3["straight_streak_cap_on"] is False
