"""
Khung train — backward (PC). Chưa curriculum / multi-map.
"""

import sys
import os
import random

_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
_SIM = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)
if _SIM not in sys.path:
    sys.path.insert(0, _SIM)

from RL_lib.rl_core import ACTIONS, get_policy
from RL_lib.grid import neighbor_xy
from map import sim_map as sm
from robot import robot as rb
from robot import action as act
from robot import robot_map as rm
from robot.policy_io import copy_q_table, empty_q_table, export_policy
from RL_lib.reward_config import (
    COLLISION_RESET,
    MAX_NODE_REVISITS,
    MAX_PING_PONG_CYCLES,
    MAX_ROTATE_STREAK,
    MAX_STEPS_PER_EPISODE,
    R_COLLISION,
    R_CP_CLOSER,
    R_CP_FARTHER,
    R_CHECKPOINT_FIRST,
    R_FACING_CLEAR,
    R_FORWARD_CLEAR,
    R_GOAL_CLOSER,
    R_GOAL_FARTHER,
    R_GOAL_REACHED,
    R_ROTATE_IN_PLACE,
    R_STEP,
    R_WASTED_ROTATE,
    compute_reward,
)

LOG_EVERY_EPISODES = 100


def _episode_at_goal(robot, sim_map):
    """Chạm goal → kết thúc episode (runtime, không phụ thuộc reward config)."""
    if sm.is_at_goal(sim_map, robot["x"], robot["y"]):
        return True
    return rb.is_at_goal(robot)


def _copy_q_table(q_table):
    return [row[:] for row in q_table]


def make_robot_for_sim(sim_map):
    rmap = rm.init_robot_map(
        sim_map["width"],
        sim_map["height"],
        goal=sim_map.get("goal"),
        checkpoints=sim_map.get("checkpoints"),
        start=sim_map.get("start"),
    )
    sx, sy = sim_map["start"]
    return rb.make_robot(sx, sy, "N", rmap)


def _max_steps_for_map(sim_map):
    return max(MAX_STEPS_PER_EPISODE, sim_map["width"] * sim_map["height"] * 2)


def eval_greedy_policy(sim_map, q_table, max_steps=None):
    """Chạy greedy từ start — cùng logic run_infer. Trả (được goal?, số bước)."""
    if max_steps is None:
        max_steps = _max_steps_for_map(sim_map)
    rmap = rm.init_robot_map(
        sim_map["width"],
        sim_map["height"],
        goal=sim_map.get("goal"),
        checkpoints=sim_map.get("checkpoints"),
        start=sim_map.get("start"),
    )
    bot = rb.make_robot(sim_map["start"][0], sim_map["start"][1], "N", rmap)
    _reset_episode_at_start(bot, sim_map)
    for step in range(1, max_steps + 1):
        if _episode_at_goal(bot, sim_map):
            return True, step - 1
        s = rb.build_encoded_state(bot)
        a_name = get_policy(s, q_table)
        result = act.execute_action_sim(bot, sim_map, a_name)
        if result.get("collision"):
            return False, step
        if _episode_at_goal(bot, sim_map):
            return True, step
    return False, max_steps


def eval_greedy_maps(sim_maps, q_table):
    """Greedy trên mọi map — phải đều tới goal. Trả (ok, worst_steps, fail_name)."""
    worst = 0
    for sim in sim_maps:
        ok, steps = eval_greedy_policy(sim, q_table)
        if not ok:
            return False, None, sim.get("name", "?")
        worst = max(worst, steps)
    return True, worst, None


def _maybe_save_best(q, train_sims, eval_sims, label, best_q, best_label, best_steps, best_tier):
    """
    Lưu Q khi greedy OK. Tier 2 = mọi eval map; tier 1 = mọi train map.
    """
    eval_sims = eval_sims or []
    if eval_sims:
        ok, steps, fail = eval_greedy_maps(eval_sims, q)
        if ok and (best_tier < 2 or (best_tier == 2 and steps < best_steps)):
            names = ", ".join(s.get("name", "?") for s in eval_sims)
            return _copy_q_table(q), "%s → eval [%s] (%d worst steps)" % (label, names, steps), steps, 2
        if not ok:
            pass

    ok, steps, fail = eval_greedy_maps(train_sims, q)
    if ok and best_tier < 2:
        if best_q is None or steps < best_steps:
            return _copy_q_table(q), "%s → all train (%d worst steps)" % (label, steps), steps, 1

    return best_q, best_label, best_steps, best_tier


def _bump_node_visit(robot, moved):
    """Đếm lần forward tới ô (x,y) trong episode."""
    key = (robot["x"], robot["y"])
    visits = robot.get("node_visits")
    if visits is None:
        visits = {}
        robot["node_visits"] = visits
    if moved:
        visits[key] = visits.get(key, 0) + 1
    return visits.get(key, 0)


def _track_ping_pong(robot, moved):
    """Phát hiện đi qua lại 2 ô (A→B→A→B). Trả số chu kỳ ping-pong liên tiếp."""
    if not moved:
        return robot.get("ping_pong_count", 0)
    hist = robot.setdefault("pos_history", [])
    hist.append((robot["x"], robot["y"]))
    if len(hist) > 8:
        del hist[:-8]
    count = robot.get("ping_pong_count", 0)
    if len(hist) >= 4:
        a, b, c, d = hist[-4:]
        if a == c and b == d and a != b:
            count += 1
        elif len(hist) >= 2 and hist[-1] != hist[-2]:
            count = 0
    robot["ping_pong_count"] = count
    return count


def q_update(q_table, s, action_idx, r, s_prime, done, alpha=0.3, gamma=0.95):
    row = q_table[s]
    target = r
    if not done:
        target = r + gamma * max(q_table[s_prime])
    row[action_idx] += alpha * (target - row[action_idx])


def _action_idx(name):
    return ACTIONS.index(name)


def _reset_episode_at_start(robot, sim_map):
    """Đưa robot về start — đầu episode."""
    sx, sy = sim_map["start"]
    robot["direct"] = "N"
    rb.update_position(robot, sx, sy)
    rb.reset_cp_visited(robot, rm.n_checkpoints(robot["robot_map"]))
    robot["has_prev_node"] = False
    robot["dist_goal_trend"] = 0
    robot["dist_cp_trend"] = [0, 0, 0]
    robot["rotate_streak"] = 0
    robot["node_visits"] = {}
    robot["pos_history"] = []
    robot["ping_pong_count"] = 0
    rb.clear_obstacle_memory(robot)
    rb.inject_distances_from_map(robot)
    rb.perceive_facing_from_sim(robot, sim_map)


def run_episode(
    robot,
    sim_map,
    q_table,
    epsilon=0.1,
    max_steps=None,
    on_step=None,
    step_wait=None,
    should_stop=None,
):
    if max_steps is None:
        max_steps = _max_steps_for_map(sim_map)
    _reset_episode_at_start(robot, sim_map)

    total_r = 0.0
    reached_goal = False
    for step in range(1, max_steps + 1):
        if should_stop and should_stop():
            break
        if _episode_at_goal(robot, sim_map):
            reached_goal = True
            break

        s = rb.build_encoded_state(robot)
        if random.random() < epsilon:
            a_name = ACTIONS[random.randint(0, len(ACTIONS) - 1)]
        else:
            a_name = get_policy(s, q_table)
        could_fwd = sm.can_move(sim_map, robot["x"], robot["y"], robot["direct"])
        x, y, d = robot["x"], robot["y"], robot["direct"]
        result = act.execute_action_sim(robot, sim_map, a_name)
        if on_step:
            on_step(
                {
                    "step": step,
                    "x": x,
                    "y": y,
                    "direct": d,
                    "s": s,
                    "action": a_name,
                    "result": result,
                    "nx": robot["x"],
                    "ny": robot["y"],
                    "ndirect": robot["direct"],
                }
            )
            if step_wait:
                step_wait()
            if should_stop and should_stop():
                break
        s_prime = rb.build_encoded_state(robot)
        r = compute_reward(
            robot, sim_map, result, action_name=a_name, could_forward_before=could_fwd
        )
        collision = result.get("collision")
        at_goal = _episode_at_goal(robot, sim_map)
        q_update(q_table, s, _action_idx(a_name), r, s_prime, done=(collision or at_goal))
        total_r += r
        if collision and COLLISION_RESET:
            _reset_episode_at_start(robot, sim_map)
            continue
        if at_goal:
            reached_goal = True
            break
    return total_r, reached_goal


def train_multi(
    train_sims,
    eval_sims=None,
    n_episodes=500,
    epsilon=0.2,
    epsilon_min=0.15,
    on_episode_start=None,
    on_step=None,
    step_wait=None,
    should_stop=None,
    initial_q=None,
    map_mode="random",
    sequential_plan=None,
):
    """Train nhiều map; map_mode='random' | 'sequential'. sequential_plan: [(sim, n_ep), ...]."""
    eval_sims = eval_sims or []
    if not train_sims and not sequential_plan:
        raise ValueError("Không có map train")

    if initial_q is not None:
        q = copy_q_table(initial_q)
        print("resume train from checkpoint (%d rows)" % len(q))
    else:
        q = empty_q_table()

    best_q = None
    best_label = None
    best_steps = 10**9
    best_tier = 0

    n_goal = 0
    episodes_done = 0
    stopped = False

    def _run_one_episode(sim, ep_index, eps, total_eps):
        nonlocal n_goal, episodes_done, stopped, best_q, best_label, best_steps, best_tier
        if should_stop and should_stop():
            stopped = True
            return False
        if on_episode_start:
            on_episode_start(sim, ep_index, eps, total_eps)
        if should_stop and should_stop():
            stopped = True
            return False
        bot = make_robot_for_sim(sim)
        _, reached_goal = run_episode(
            bot,
            sim,
            q,
            epsilon=eps,
            on_step=on_step,
            step_wait=step_wait,
            should_stop=should_stop,
        )
        episodes_done = ep_index + 1
        if should_stop and should_stop():
            stopped = True
            return False
        if reached_goal:
            n_goal += 1
            best_q, best_label, best_steps, best_tier = _maybe_save_best(
                q,
                train_sims,
                eval_sims,
                "episode %d" % ep_index,
                best_q,
                best_label,
                best_steps,
                best_tier,
            )
        if ep_index % LOG_EVERY_EPISODES == 0:
            tag = sim.get("name", "?")
            if map_mode == "sequential":
                print("episode", ep_index, "| epsilon %.3f | map %s (sequential)" % (eps, tag))
            else:
                print("episode", ep_index, "| epsilon %.3f | map random" % eps)
        return True

    if map_mode == "sequential" and sequential_plan:
        total_eps = sum(n for _, n in sequential_plan)
        if total_eps <= 0:
            raise ValueError("Sequential plan: tổng episodes = 0")
        print("train sequential: %d episodes on %d map(s)" % (total_eps, len(sequential_plan)))
        for name, n_ep in [(s.get("name", "?"), n) for s, n in sequential_plan]:
            print("  ", name, "→", n_ep, "episodes")
        ep_global = 0
        for sim, n_map_ep in sequential_plan:
            if stopped:
                break
            for _ in range(n_map_ep):
                if stopped:
                    break
                eps = epsilon_min + (epsilon - epsilon_min) * (
                    1.0 - ep_global / max(total_eps - 1, 1)
                )
                if not _run_one_episode(sim, ep_global, eps, total_eps):
                    break
                ep_global += 1
        n_episodes = total_eps
    else:
        if n_episodes > 0:
            print("train random: %d episodes on %d map(s)" % (n_episodes, len(train_sims)))
            for ep in range(n_episodes):
                if should_stop and should_stop():
                    stopped = True
                    print("Stopped by user at episode %d" % ep)
                    break
                eps = epsilon_min + (epsilon - epsilon_min) * (1.0 - ep / max(n_episodes - 1, 1))
                sim = random.choice(train_sims)
                if not _run_one_episode(sim, ep, eps, n_episodes):
                    break

    if stopped:
        print("export policy: stopped early (current Q)")
        export_policy(q)
        print("episodes reached goal:", n_goal, "/", episodes_done)
        return {"q": q, "stopped": True, "episodes_done": episodes_done, "n_goal": n_goal}

    if best_q is not None:
        q = best_q
        print("export policy:", best_label)
    else:
        print("WARNING: no greedy-success policy — exporting final Q")

    export_policy(q)
    print("episodes reached goal:", n_goal, "/", n_episodes)
    return {"q": q, "stopped": False, "episodes_done": episodes_done, "n_goal": n_goal}


def train(
    sim_map,
    robot,
    n_episodes=500,
    epsilon=0.2,
    epsilon_min=0.15,
):
    """Train 1 map (tương thích cũ) — khuyến nghị dùng train_multi."""
    return train_multi(
        [sim_map],
        eval_sims=None,
        n_episodes=n_episodes,
        epsilon=epsilon,
        epsilon_min=epsilon_min,
    )
