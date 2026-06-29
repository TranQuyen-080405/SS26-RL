"""Thế giới 12×5 cho Learn Lab — robot, goal, CP, tường, action thật."""

import os
import sys

_SIM = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "Simulation"))
if _SIM not in sys.path:
    sys.path.insert(0, _SIM)

from map.sim_map import init_sim_map, set_wall, get_block, can_move
from robot import robot as rb
from robot import robot_map as rm
from robot import action as act
from robot.robot_map import get_obstacle_nwes, get_node, n_checkpoints

from RL_lib.reward_config import compute_reward_breakdown, get_enabled_modules
from RL_lib.lab_state_test import encode_for_lab

LAB_WIDTH = 12
LAB_HEIGHT = 5
DEFAULT_GOAL = (11, 4)
DEFAULT_CP = (6, 2)
DEFAULT_START = (0, 0)


def _robot_map_from_sim(sim_map):
    rmap = rm.init_robot_map(
        sim_map["width"],
        sim_map["height"],
        goal=sim_map.get("goal"),
        checkpoints=list(sim_map.get("checkpoints") or []),
        start=sim_map.get("start"),
    )
    rm.apply_boundary_walls(rmap)
    rm.populate_all_distances(rmap)
    return rmap


class LabWorld5:
    def __init__(self):
        self.sim_map = init_sim_map(
            LAB_WIDTH,
            LAB_HEIGHT,
            goal=DEFAULT_GOAL,
            checkpoints=[DEFAULT_CP],
            start=DEFAULT_START,
        )
        self.rmap = _robot_map_from_sim(self.sim_map)
        self.robot = rb.make_robot(DEFAULT_START[0], DEFAULT_START[1], "N", self.rmap)
        self._reset_robot_state()
        self.paint_tool = "robot"
        self.last_total = 0.0
        self.last_parts = {}
        self.last_action = None

    def _reset_robot_state(self):
        sx, sy = self.sim_map["start"]
        self.robot["direct"] = "N"
        rb.update_position(self.robot, sx, sy)
        rb.reset_cp_visited(self.robot, n_checkpoints(self.rmap))
        self.robot["has_prev_node"] = False
        self.robot["dist_goal_trend"] = 0
        self.robot["dist_cp_trend"] = [0, 0, 0]
        self.robot["rotate_streak"] = 0
        self.robot["node_visits"] = {}
        self.robot["ping_pong_count"] = 0
        rb.clear_obstacle_memory(self.robot)
        rb.inject_distances_from_map(self.robot)
        rb.perceive_facing_from_sim(self.robot, self.sim_map)
        self.last_total = 0.0
        self.last_parts = {}
        self.last_action = None

    def sync_maps(self):
        """Đồng bộ goal/cp/start từ sim_map sang robot_map."""
        self.rmap = _robot_map_from_sim(self.sim_map)
        self.robot["robot_map"] = self.rmap
        rb.inject_distances_from_map(self.robot)
        rb.perceive_facing_from_sim(self.robot, self.sim_map)

    def set_tool(self, tool):
        self.paint_tool = tool

    def place_robot(self, x, y):
        w, h = self.sim_map["width"], self.sim_map["height"]
        if 0 <= x < w and 0 <= y < h:
            rb.update_position(self.robot, x, y)
            rb.inject_distances_from_map(self.robot)
            rb.perceive_facing_from_sim(self.robot, self.sim_map)

    def place_goal(self, x, y):
        self.sim_map["goal"] = (x, y)
        self.rmap["goal"] = (x, y)
        rm.populate_all_distances(self.rmap)
        rb.inject_distances_from_map(self.robot)

    def place_checkpoint(self, x, y):
        cps = [tuple(p) for p in (self.sim_map.get("checkpoints") or [])]
        if (x, y) in cps:
            cps.remove((x, y))
        else:
            if len(cps) >= 3:
                cps.pop(0)
            cps.append((x, y))
        self.sim_map["checkpoints"] = cps
        self.rmap["checkpoints"] = cps
        rb.reset_cp_visited(self.robot, len(cps))
        rm.populate_all_distances(self.rmap)
        rb.inject_distances_from_map(self.robot)

    def toggle_wall(self, x, y, direction):
        blocked = get_block(self.sim_map, x, y, direction)
        set_wall(self.sim_map, x, y, direction, not blocked)
        rb.perceive_facing_from_sim(self.robot, self.sim_map)

    def reset_scenario(self):
        self.sim_map = init_sim_map(
            LAB_WIDTH,
            LAB_HEIGHT,
            goal=DEFAULT_GOAL,
            checkpoints=[DEFAULT_CP],
            start=DEFAULT_START,
        )
        self.rmap = _robot_map_from_sim(self.sim_map)
        self.robot = rb.make_robot(DEFAULT_START[0], DEFAULT_START[1], "N", self.rmap)
        self._reset_robot_state()

    def do_action(self, action_name):
        could_fwd = can_move(self.sim_map, self.robot["x"], self.robot["y"], self.robot["direct"])
        result = act.execute_action_sim(self.robot, self.sim_map, action_name)
        total, parts = compute_reward_breakdown(
            self.robot, self.sim_map, result, action_name=action_name, could_forward_before=could_fwd
        )
        self._mark_checkpoint_visit()
        self.last_action = action_name
        self.last_total = total
        self.last_parts = parts
        return total, parts, result

    def _mark_checkpoint_visit(self):
        x, y = self.robot["x"], self.robot["y"]
        cps = self.sim_map.get("checkpoints") or []
        visited = self.robot.get("cp_visited") or []
        for i, (cx, cy) in enumerate(cps):
            if x == cx and y == cy and i < len(visited) and not visited[i]:
                visited[i] = True

    def get_obs_nwes(self):
        node = get_node(self.robot["robot_map"], self.robot["x"], self.robot["y"])
        if not node:
            return (0, 0, 0, 0)
        return get_obstacle_nwes(node)

    def get_state_snapshot(self, enabled_modules=None):
        enabled = enabled_modules if enabled_modules is not None else get_enabled_modules()
        obs = self.get_obs_nwes()
        gt = self.robot.get("dist_goal_trend", 0)
        cps = list(self.robot.get("dist_cp_trend", [0, 0, 0])[:3])
        hd = self.robot["direct"]
        dec = encode_for_lab(obs, gt, cps, hd, enabled)
        return {
            "s": dec["s"],
            "obs": dec["obstacle_nwes"],
            "goal_trend": dec["dist_goal_trend"],
            "cp_trends": dec["dist_cp_trends"],
            "heading": dec["heading"],
            "pos": (self.robot["x"], self.robot["y"]),
        }

    def walls_set(self):
        out = set()
        for key, val in (self.sim_map.get("walls") or {}).items():
            if val:
                out.add(key)
        return out
