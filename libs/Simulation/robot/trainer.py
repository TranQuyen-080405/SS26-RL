"""
Khung train — backward (PC). Chưa curriculum / multi-map.
"""

import random

from RL_lib.rl_core import ACTIONS, get_policy
from RL_lib.grid import neighbor_xy
from map import sim_map as sm
from robot import robot as rb
from robot import action as act
from robot import robot_map as rm
from robot.policy_io import copy_q_table, empty_q_table, export_policy
from RL_lib.reward_config import (
    COLLISION_RESET,
    MAX_STEPS_PER_EPISODE,
    compute_reward,
)

LOG_EVERY_EPISODES = 100


def _episode_at_goal(robot, sim_map):
    """Chạm goal → kết thúc episode (runtime, không phụ thuộc reward config)."""
    if sm.is_at_goal(sim_map, robot["x"], robot["y"]):
        return True
    return rb.is_at_goal(robot)




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
            return copy_q_table(q), "%s -> eval [%s] (%d worst steps)" % (label, names, steps), steps, 2
        if not ok:
            pass

    ok, steps, fail = eval_greedy_maps(train_sims, q)
    if ok and best_tier < 2:
        if best_q is None or steps < best_steps:
            return copy_q_table(q), "%s -> all train (%d worst steps)" % (label, steps), steps, 1

    return best_q, best_label, best_steps, best_tier


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
    rb.reset_explore_tracking(robot)
    rb.clear_obstacle_memory(robot)
    rb.inject_distances_from_map(robot)
    rb.perceive_facing_from_sim(robot, sim_map, for_reward=False)


def _gate_pause(pause_gate, should_stop=None):
    if not pause_gate:
        return
    import time

    while pause_gate():
        if should_stop and should_stop():
            return
        time.sleep(0.05)


def run_episode(
    robot,
    sim_map,
    q_table,
    epsilon=0.1,
    max_steps=None,
    on_step=None,
    step_wait=None,
    should_stop=None,
    pause_gate=None,
):
    if max_steps is None:
        max_steps = _max_steps_for_map(sim_map)
    _reset_episode_at_start(robot, sim_map)

    total_r = 0.0
    reached_goal = False
    for step in range(1, max_steps + 1):
        _gate_pause(pause_gate, should_stop)
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
        r = compute_reward(
            robot, sim_map, result, action_name=a_name, could_forward_before=could_fwd
        )
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
                    "reward": r,
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
    pause_gate=None,
    initial_q=None,
    map_mode="random",
    sequential_plan=None,
    curriculum_goal_hits=None,
    export_bin_path=None,
):
    """Train nhiều map; map_mode='random' | 'sequential' | 'curriculum'."""
    from robot.policy_io import DEFAULT_POLICY_BIN

    export_path = export_bin_path or DEFAULT_POLICY_BIN
    eval_sims = eval_sims or []
    if not train_sims and not sequential_plan:
        raise ValueError("Không có map train")

    import train_log

    resuming = initial_q is not None
    if initial_q is not None:
        q = copy_q_table(initial_q)
    else:
        q = empty_q_table()

    best_q = None
    best_label = None
    best_steps = 10**9
    best_tier = 0

    n_goal = 0
    episodes_done = 0
    stopped = False
    block_goals = 0
    block_start = 0
    block_map = "?"
    block_episodes = 0
    summary_log = on_step is None
    block_include_map = True

    def _reset_block(ep_index, map_name):
        nonlocal block_start, block_map, block_goals, block_episodes
        block_start = ep_index
        block_map = map_name or "?"
        block_goals = 0
        block_episodes = 0

    def _flush_block():
        nonlocal block_episodes, block_goals
        if not summary_log or block_episodes <= 0:
            block_episodes = 0
            block_goals = 0
            return
        train_log.print_train_block(
            block_start, block_episodes, block_map, block_goals, include_map=block_include_map
        )
        block_episodes = 0
        block_goals = 0

    def _note_episode_result(reached_goal):
        nonlocal block_episodes, block_goals
        block_episodes += 1
        if reached_goal:
            block_goals += 1

    def _maybe_flush_random_batch(next_ep_index, map_name):
        if not summary_log:
            return
        if block_episodes >= LOG_EVERY_EPISODES:
            _flush_block()
            _reset_block(next_ep_index, map_name)

    def _run_one_episode(sim, ep_index, eps, total_eps):
        nonlocal n_goal, episodes_done, stopped, best_q, best_label, best_steps, best_tier
        if should_stop and should_stop():
            stopped = True
            return False
        _gate_pause(pause_gate, should_stop)
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
            pause_gate=pause_gate,
        )
        episodes_done = ep_index + 1
        _note_episode_result(reached_goal)
        if should_stop and should_stop():
            stopped = True
            return False
        if reached_goal:
            n_goal += 1
            if ep_index % 500 == 0 or ep_index == total_eps - 1:
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
        return True

    if map_mode == "sequential" and sequential_plan:
        total_eps = sum(n for _, n in sequential_plan)
        if total_eps <= 0:
            raise ValueError("Sequential plan: tổng episodes = 0")
        train_log.print_train_start(
            map_mode, total_eps, len(sequential_plan), len(q) if resuming else None, resuming
        )
        train_log.print_sequential_plan(sequential_plan)
        ep_global = 0
        block_include_map = True
        for sim, n_map_ep in sequential_plan:
            if stopped:
                break
            map_name = sim.get("name", "?")
            _reset_block(ep_global, map_name)
            for _ in range(n_map_ep):
                _gate_pause(pause_gate, should_stop)
                if stopped:
                    break
                eps = epsilon_min + (epsilon - epsilon_min) * (
                    1.0 - ep_global / max(total_eps - 1, 1)
                )
                if not _run_one_episode(sim, ep_global, eps, total_eps):
                    break
                ep_global += 1
                _maybe_flush_random_batch(ep_global, map_name)
            _flush_block()
        n_episodes = total_eps
    elif map_mode == "curriculum":
        if isinstance(curriculum_goal_hits, (list, tuple)):
            goals_per_map = [max(1, int(v)) for v in curriculum_goal_hits]
            if len(goals_per_map) < len(train_sims):
                goals_per_map.extend([10] * (len(train_sims) - len(goals_per_map)))
            goals_per_map = goals_per_map[: len(train_sims)]
        else:
            goal_target = max(1, int(curriculum_goal_hits or 10))
            goals_per_map = [goal_target] * len(train_sims)
        total_target = max(1, sum(goals_per_map))
        train_log.print_train_start(
            map_mode, total_target, len(train_sims), len(q) if resuming else None, resuming
        )
        ep_global = 0
        for sim_idx, sim in enumerate(train_sims):
            if stopped:
                break
            goal_target = goals_per_map[sim_idx]
            map_goals = 0
            block_episodes = 0
            block_goals = 0
            block_start = ep_global
            block_map = sim.get("name", "?")
            while map_goals < goal_target:
                _gate_pause(pause_gate, should_stop)
                if should_stop and should_stop():
                    stopped = True
                    train_log.print_stopped_at(ep_global)
                    break
                eps = epsilon_min + (epsilon - epsilon_min) * (
                    1.0 - min(ep_global, total_target - 1) / max(total_target - 1, 1)
                )
                before_goal = n_goal
                if not _run_one_episode(sim, ep_global, eps, total_target):
                    break
                if n_goal > before_goal:
                    map_goals += n_goal - before_goal
                ep_global += 1
                if stopped:
                    break
            if summary_log and block_episodes > 0:
                train_log.print_curriculum_block(sim, block_episodes, block_goals, goal_target)
            elif not summary_log:
                pass
            block_episodes = 0
            block_goals = 0
        n_episodes = ep_global
    else:
        if n_episodes > 0:
            block_include_map = map_mode != "random"
            train_log.print_train_start(
                map_mode, n_episodes, len(train_sims), len(q) if resuming else None, resuming
            )
            _reset_block(0, "?")
            for ep in range(n_episodes):
                _gate_pause(pause_gate, should_stop)
                if should_stop and should_stop():
                    stopped = True
                    train_log.print_stopped_at(ep)
                    break
                eps = epsilon_min + (epsilon - epsilon_min) * (1.0 - ep / max(n_episodes - 1, 1))
                sim = random.choice(train_sims)
                if block_episodes == 0:
                    block_map = sim.get("name", "?")
                if not _run_one_episode(sim, ep, eps, n_episodes):
                    break
                _maybe_flush_random_batch(ep + 1, sim.get("name", "?"))
            _flush_block()

    if stopped:
        export_policy(q, export_path)
        train_log.print_train_summary(
            stopped=True,
            export_path=export_path,
            n_goal=n_goal,
            episodes_done=episodes_done,
        )
        return {
            "q": q,
            "stopped": True,
            "episodes_done": episodes_done,
            "n_goal": n_goal,
            "export_path": export_path,
        }

    if best_q is not None:
        q = best_q

    export_policy(q, export_path)
    train_log.print_train_summary(
        stopped=False,
        export_path=export_path,
        n_goal=n_goal,
        episodes_done=episodes_done,
        best_label=best_label,
    )
    return {
        "q": q,
        "stopped": False,
        "episodes_done": episodes_done,
        "n_goal": n_goal,
        "export_path": export_path,
    }


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
