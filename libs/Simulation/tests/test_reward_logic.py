import sys
import os

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, ROOT)

import reward_config
from RL_lib.reward_config import _build_reward_context

def test_wall_visible():
    robot = {"x": 1, "y": 1, "direct": "N"}
    sim_map = {
        "width": 3,
        "height": 3,
        "walls": {(1, 1, "N"): True}
    }
    result = {"moved": False, "collision": False}
    
    ctx = _build_reward_context(robot, sim_map, result)
    assert ctx["wall_detected"] is True
    assert ctx["wall_visible"] is True

    # No wall in front, but wall on East
    sim_map_2 = {
        "width": 3,
        "height": 3,
        "walls": {(1, 1, "E"): True}
    }
    ctx2 = _build_reward_context(robot, sim_map_2, result)
    assert ctx2["wall_detected"] is False
    assert ctx2["wall_visible"] is True


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
