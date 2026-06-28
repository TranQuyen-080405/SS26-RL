"""Tính reward từ state tiếp theo + action (Learn Lab)."""

import os
import sys

_SIM = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "Simulation"))
if _SIM not in sys.path:
    sys.path.insert(0, _SIM)

from map.sim_map import init_sim_map

from RL_lib.reward_config import compute_reward_breakdown, get_enabled_modules


def infer_action_result(action, obs_nwes):
    """Suy ra kết quả hành động từ obstacle phía trước (N trong khung robot)."""
    wall_ahead = bool(obs_nwes[0])
    if action == "forward":
        if wall_ahead:
            return {"success": False, "moved": False, "collision": True}
        return {"success": True, "moved": True, "collision": False}
    return {"success": True, "moved": False, "collision": False}


def build_robot_from_state(
    obs_nwes,
    goal_trend,
    cp_trends,
    heading,
    *,
    action_hint="forward",
    at_goal=False,
    at_checkpoint=False,
    cp_index=0,
    rotate_streak=0,
    could_forward_before=None,
    wasted_rotate=False,
):
    cp_visited = [True, True, True]
    if at_checkpoint and 0 <= cp_index < 3:
        cp_visited = [i == cp_index for i in range(3)]
        cp_visited[cp_index] = False

    wall_ahead = bool(obs_nwes[0])
    if could_forward_before is None:
        if action_hint == "forward":
            could_forward_before = not wall_ahead
        else:
            could_forward_before = wasted_rotate or not wall_ahead

    return {
        "x": 9 if at_goal else (5 if at_checkpoint else 0),
        "y": 9 if at_goal else (5 if at_checkpoint else 0),
        "direct": heading,
        "dist_goal_trend": goal_trend,
        "dist_cp_trend": list(cp_trends) + [0, 0, 0],
        "rotate_streak": rotate_streak,
        "cp_visited": cp_visited[:3],
        "node_visits": {},
        "ping_pong_count": 0,
        "robot_map": {"goal": (9, 9), "checkpoints": [(5, 5)]},
        "_could_forward_before": could_forward_before,
    }


def build_sim_map(*, at_goal=False, at_checkpoint=False):
    goal = (9, 9)
    cps = [(5, 5)] if at_checkpoint else []
    return init_sim_map(10, 10, goal=goal, checkpoints=cps, start=(0, 0))


def encode_for_lab(obs_nwes, goal_trend, cp_trends, heading, enabled_modules=None):
    """Ghép s chỉ với các module state đang bật."""
    from RL_lib.state_codec import build_state

    enabled = enabled_modules if enabled_modules is not None else get_enabled_modules()
    obs = obs_nwes
    gt = goal_trend
    cps = cp_trends
    hd = heading
    if "obstacle" not in enabled:
        obs = (0, 0, 0, 0)
    if "goal" not in enabled:
        gt = 0
    if "checkpoint" not in enabled:
        cps = [0, 0, 0]
    if "heading" not in enabled:
        hd = "N"
    return build_state(obs, gt, cps, hd)


def run_state_test(
    action,
    obs_nwes,
    goal_trend,
    cp_trends,
    heading,
    *,
    at_goal=False,
    at_checkpoint=False,
    rotate_streak=0,
    wasted_rotate=False,
):
    result = infer_action_result(action, obs_nwes)
    robot = build_robot_from_state(
        obs_nwes,
        goal_trend,
        cp_trends,
        heading,
        action_hint=action,
        at_goal=at_goal,
        at_checkpoint=at_checkpoint,
        rotate_streak=rotate_streak,
        wasted_rotate=wasted_rotate,
    )
    could_fwd = robot.pop("_could_forward_before")
    sim_map = build_sim_map(at_goal=at_goal, at_checkpoint=at_checkpoint)
    return compute_reward_breakdown(robot, sim_map, result, action, could_fwd)
