"""
Train / infer — đọc map JSON từ map/train/ và map/infer/.
"""

import os
import sys

_SIM = os.path.abspath(os.path.join(os.path.dirname(__file__)))
_ROOT = os.path.abspath(os.path.join(_SIM, ".."))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)
if _SIM not in sys.path:
    sys.path.insert(0, _SIM)

N_EPISODES_DEFAULT = 10000
MAX_STEPS_INFER = 800


def load_train_and_eval_maps():
    from map.map_io import list_map_files, build_sim_map_from_file

    train_paths = list_map_files("train")
    infer_paths = list_map_files("infer")
    if not train_paths:
        raise FileNotFoundError("Không có file map trong map/train/")
    train_sims = [build_sim_map_from_file(p) for p in train_paths]
    eval_sims = [build_sim_map_from_file(p) for p in infer_paths]
    return train_sims, eval_sims, train_paths, infer_paths


def run_train(
    n_episodes=N_EPISODES_DEFAULT,
    on_episode_start=None,
    on_step=None,
    step_wait=None,
    should_stop=None,
    checkpoint=None,
    train_map_mode="random",
    train_sims=None,
    sequential_plan=None,
    export_policy_path=None,
):
    from robot import trainer
    from robot.policy_io import resolve_checkpoint
    from RL_lib import rl_core
    import train_log

    all_train_sims, eval_sims, train_paths, infer_paths = load_train_and_eval_maps()
    if train_sims is not None:
        train_sims = list(train_sims)
    else:
        train_sims = all_train_sims
    if not train_sims:
        raise FileNotFoundError("Không có map train được chọn")

    initial_q, ck_label = resolve_checkpoint(checkpoint)
    train_log.print_train_header(
        train_names=[s.get("name", "?") for s in train_sims],
        eval_names=[s.get("name", "?") for s in eval_sims] if infer_paths else [],
        map_mode=train_map_mode,
        n_episodes=n_episodes,
        checkpoint_label=ck_label,
        export_path=export_policy_path,
        resuming=initial_q is not None,
    )

    result = trainer.train_multi(
        train_sims,
        eval_sims=eval_sims,
        n_episodes=n_episodes,
        on_episode_start=on_episode_start,
        on_step=on_step,
        step_wait=step_wait,
        should_stop=should_stop,
        initial_q=initial_q,
        map_mode=train_map_mode,
        sequential_plan=sequential_plan,
        export_bin_path=export_policy_path,
    )
    return result


def load_policy():
    from robot.policy_io import load_q_table

    return load_q_table()


def load_policy_for_infer(policy_bin=None):
    """Nạp Q-table cho infer từ .bin."""
    from robot.policy_io import DEFAULT_POLICY_BIN, load_policy_bin, load_q_table, policy_bin_path

    if policy_bin:
        path = policy_bin if os.path.isabs(policy_bin) else policy_bin_path(policy_bin)
        if not os.path.isfile(path):
            return None, path
        return load_policy_bin(path), path

    q = load_q_table()
    if q is None:
        return None, None
    return q, DEFAULT_POLICY_BIN


def _robot_map_from_sim(sim_map):
    from robot import robot_map as rm

    return rm.init_robot_map(
        sim_map["width"],
        sim_map["height"],
        goal=sim_map.get("goal"),
        checkpoints=sim_map.get("checkpoints"),
        start=sim_map.get("start"),
    )


def _reset_at_start(robot, sim_map):
    from robot import robot as rb

    sx, sy = sim_map["start"]
    robot["direct"] = "N"
    rb.update_position(robot, sx, sy)
    robot["has_prev_node"] = False
    robot["dist_goal_trend"] = 0
    robot["dist_cp_trend"] = [0, 0, 0]
    robot["rotate_streak"] = 0
    rb.clear_obstacle_memory(robot)
    rb.inject_distances_from_map(robot)
    rb.perceive_facing_from_sim(robot, sim_map)


def _episode_at_goal(robot, sim_map):
    """Chạm goal → kết thúc episode (runtime, không phụ thuộc reward config)."""
    from map import sim_map as sm
    from robot import robot as rb

    if sm.is_at_goal(sim_map, robot["x"], robot["y"]):
        return True
    return rb.is_at_goal(robot)


def run_infer_episode(sim_map, q_table, max_steps=MAX_STEPS_INFER, verbose=True, on_step=None):
    """Chạy policy thuần (argmax Q). Trả dict status, steps, log."""
    import train_log
    from RL_lib.rl_core import get_policy
    from robot import robot as rb
    from robot import action as act

    rmap = _robot_map_from_sim(sim_map)
    bot = rb.make_robot(sim_map["start"][0], sim_map["start"][1], "N", rmap)
    _reset_at_start(bot, sim_map)
    log = []

    for step in range(1, max_steps + 1):
        if _episode_at_goal(bot, sim_map):
            if verbose:
                train_log.print_infer_summary("goal", step - 1)
            return {"status": "goal", "steps": step - 1, "log": log}

        s = rb.build_encoded_state(bot)
        a_name = get_policy(s, q_table)
        x, y, d = bot["x"], bot["y"], bot["direct"]

        if verbose:
            train_log.print_infer_step(step, x, y, d, s, a_name)

        result = act.execute_action_sim(bot, sim_map, a_name)
        entry = {
            "step": step,
            "x": x,
            "y": y,
            "direct": d,
            "s": s,
            "action": a_name,
            "result": result,
            "nx": bot["x"],
            "ny": bot["y"],
            "ndirect": bot["direct"],
        }
        log.append(entry)
        if on_step:
            on_step(entry)

        if result.get("collision"):
            if verbose:
                train_log.print_infer_summary("collision", step)
            return {"status": "collision", "steps": step, "log": log}

        if _episode_at_goal(bot, sim_map):
            if verbose:
                train_log.print_infer_summary("goal", step)
            return {"status": "goal", "steps": step, "log": log}

    if verbose:
        train_log.print_infer_summary("max_steps", max_steps)
    return {"status": "max_steps", "steps": max_steps, "log": log}


def run_infer_episode_for_map(
    map_path,
    max_steps=MAX_STEPS_INFER,
    verbose=True,
    on_step=None,
    policy_bin=None,
):
    """Nạp map + policy, chạy một episode infer."""
    import train_log
    from map.map_io import build_sim_map_from_file

    q, policy_path = load_policy_for_infer(policy_bin)
    if not q:
        raise FileNotFoundError("Không tìm thấy policy — chạy train trước hoặc chọn file .bin.")
    sim = build_sim_map_from_file(map_path)
    if verbose:
        train_log.print_infer_header(sim, policy_path)
    return sim, run_infer_episode(sim, q, max_steps=max_steps, verbose=verbose, on_step=on_step)


def run_infer(map_path=None, max_steps=MAX_STEPS_INFER, verbose=True, policy_bin=None):
    import train_log
    from map.map_io import list_map_files, build_sim_map_from_file

    q, policy_path = load_policy_for_infer(policy_bin)
    if not q:
        print("No policy — train first or pick a .bin file.")
        return None

    if map_path is None:
        infer_paths = list_map_files("infer")
        if not infer_paths:
            print("No infer maps in map/infer/")
            return None
        map_path = infer_paths[0]

    sim = build_sim_map_from_file(map_path)
    if verbose:
        train_log.print_infer_header(sim, policy_path)

    outcome = run_infer_episode(sim, q, max_steps=max_steps, verbose=verbose)
    return outcome
