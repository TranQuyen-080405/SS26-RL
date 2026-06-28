"""Kịch bản test reward trong Learn Lab."""

import os
import sys

_SIM = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "Simulation"))
if _SIM not in sys.path:
    sys.path.insert(0, _SIM)

from map.sim_map import init_sim_map, set_wall

from RL_lib.reward_config import compute_reward_breakdown


def _mini_map(goal=(9, 9), checkpoints=None, start=(0, 0), walls=None):
    sm = init_sim_map(10, 10, goal=goal, checkpoints=checkpoints or [], start=start)
    for x, y, d in walls or []:
        set_wall(sm, x, y, d, True)
    return sm


def _robot(
    x=0,
    y=0,
    direct="N",
    dist_goal_trend=0,
    dist_cp_trend=None,
    rotate_streak=0,
    cp_visited=None,
    node_visits=None,
    ping_pong_count=0,
):
    return {
        "x": x,
        "y": y,
        "direct": direct,
        "dist_goal_trend": dist_goal_trend,
        "dist_cp_trend": dist_cp_trend if dist_cp_trend is not None else [0, 0, 0],
        "rotate_streak": rotate_streak,
        "cp_visited": cp_visited if cp_visited is not None else [False, False, False],
        "node_visits": node_visits or {},
        "ping_pong_count": ping_pong_count,
        "robot_map": {"goal": (9, 9), "checkpoints": []},
    }


SCENARIO_LIST = [
    ("forward — gần goal (trend +1)", "forward_closer"),
    ("forward — va tường (collision)", "forward_collision"),
    ("forward — ô trống (forward_clear)", "forward_clear"),
    ("rotate tại chỗ", "rotate"),
    ("xoay lãng (wasted rotate)", "wasted_rotate"),
    ("tới goal", "at_goal"),
    ("checkpoint lần đầu", "checkpoint"),
    ("xoay quá nhiều (excess rotate)", "excess_rotate"),
]


def get_scenario(key):
    if key == "forward_closer":
        return (
            _robot(dist_goal_trend=1),
            _mini_map(),
            {"success": True, "moved": True, "collision": False},
            "forward",
            True,
        )
    if key == "forward_collision":
        return (
            _robot(),
            _mini_map(walls=[(0, 0, "N")]),
            {"success": False, "moved": False, "collision": True},
            "forward",
            True,
        )
    if key == "forward_clear":
        return (
            _robot(dist_goal_trend=0),
            _mini_map(),
            {"success": True, "moved": True, "collision": False},
            "forward",
            True,
        )
    if key == "rotate":
        return (
            _robot(rotate_streak=1),
            _mini_map(),
            {"success": True, "moved": False, "collision": False},
            "rotate left",
            False,
        )
    if key == "wasted_rotate":
        return (
            _robot(rotate_streak=0),
            _mini_map(),
            {"success": True, "moved": False, "collision": False},
            "rotate right",
            True,
        )
    if key == "at_goal":
        g = (9, 9)
        return (
            _robot(x=g[0], y=g[1]),
            _mini_map(goal=g, start=g),
            {"success": True, "moved": True, "collision": False},
            "forward",
            False,
        )
    if key == "checkpoint":
        cp = [(5, 5)]
        return (
            _robot(x=5, y=5, cp_visited=[False, False, False]),
            _mini_map(checkpoints=cp, start=(0, 0)),
            {"success": True, "moved": True, "collision": False},
            "forward",
            False,
        )
    if key == "excess_rotate":
        return (
            _robot(rotate_streak=5),
            _mini_map(),
            {"success": True, "moved": False, "collision": False},
            "rotate left",
            False,
        )
    return None


def run_scenario(key):
    data = get_scenario(key)
    if not data:
        return 0.0, {}
    robot, sim_map, result, action, could_fwd = data
    return compute_reward_breakdown(robot, sim_map, result, action, could_fwd)
