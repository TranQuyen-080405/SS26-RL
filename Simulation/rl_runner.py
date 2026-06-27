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
):
    from robot import trainer
    from robot.policy_io import resolve_checkpoint
    from RL_lib import rl_core

    train_sims, eval_sims, train_paths, infer_paths = load_train_and_eval_maps()
    print("N_ROWS train:", rl_core.N_ROWS)
    print("train maps (%d):" % len(train_paths), [s.get("name") for s in train_sims])
    if infer_paths:
        print("eval maps (%d):" % len(infer_paths), [s.get("name") for s in eval_sims])
    else:
        print("eval maps: (none — chỉ lưu khi greedy OK trên train)")

    initial_q, ck_label = resolve_checkpoint(checkpoint)
    if initial_q is not None:
        print("checkpoint:", ck_label)
    else:
        print("checkpoint: (mới — Q-table trống)")

    result = trainer.train_multi(
        train_sims,
        eval_sims=eval_sims,
        n_episodes=n_episodes,
        on_episode_start=on_episode_start,
        on_step=on_step,
        step_wait=step_wait,
        should_stop=should_stop,
        initial_q=initial_q,
    )
    print("exported Q_table/policy.json + Q_table/policy.bin")
    if result.get("stopped"):
        print("========train stopped — Q_table updated=========")
    else:
        print("========learning completed=========")
    return result


def load_policy():
    from robot.policy_io import load_q_table

    return load_q_table()


def load_policy_for_infer(policy_json=None):
    """Nạp Q-table cho infer; mặc định ưu tiên .bin rồi .json. Truyền policy_json để đọc file .json cụ thể."""
    from robot.policy_io import (
        DEFAULT_POLICY_BIN,
        DEFAULT_POLICY_JSON,
        load_policy_json,
        load_q_table,
        policy_json_path,
    )

    if policy_json:
        path = policy_json if os.path.isabs(policy_json) else policy_json_path(policy_json)
        return load_policy_json(path), path

    q = load_q_table()
    if q is None:
        return None, None
    path = DEFAULT_POLICY_BIN if os.path.isfile(DEFAULT_POLICY_BIN) else DEFAULT_POLICY_JSON
    return q, path


def _reset_at_start(robot, sim_map):
    from map import sim_map as sm
    from robot import robot as rb

    sx, sy = sim_map["start"]
    robot["direct"] = "N"
    rb.update_position(robot, sx, sy)
    robot["has_prev_node"] = False
    robot["dist_goal_trend"] = 0
    robot["dist_cp_trend"] = [0, 0, 0]
    robot["rotate_streak"] = 0
    rb.clear_obstacle_memory(robot)
    rb.inject_distances(
        robot,
        sm.dist_to_goal(sim_map, sx, sy),
        sm.dist_to_checkpoints(sim_map, sx, sy),
    )
    rb.perceive_facing_from_sim(robot, sim_map)


def run_infer_episode(sim_map, q_table, max_steps=MAX_STEPS_INFER, verbose=True, on_step=None):
    """Chạy policy thuần (argmax Q). Trả dict status, steps, log."""
    from RL_lib.rl_core import get_policy
    from map import sim_map as sm
    from robot import robot_map as rm
    from robot import robot as rb
    from robot import action as act

    rmap = rm.init_robot_map(sim_map["width"], sim_map["height"])
    bot = rb.make_robot(sim_map["start"][0], sim_map["start"][1], "N", rmap)
    _reset_at_start(bot, sim_map)
    log = []

    for step in range(1, max_steps + 1):
        if sm.is_at_goal(sim_map, bot["x"], bot["y"]):
            if verbose:
                print("GOAL — tới đích sau %d bước." % (step - 1))
            return {"status": "goal", "steps": step - 1, "log": log}

        s = rb.build_encoded_state(bot)
        a_name = get_policy(s, q_table)
        x, y, d = bot["x"], bot["y"], bot["direct"]

        if verbose:
            print("step %d | pos (%d,%d) %s | s=%d | action: %s" % (step, x, y, d, s, a_name))

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
                print("COLLISION — dừng infer (forward đụng tường / mép map).")
            return {"status": "collision", "steps": step, "log": log}

        if sm.is_at_goal(sim_map, bot["x"], bot["y"]):
            if verbose:
                print("GOAL — tới đích sau %d bước." % step)
            return {"status": "goal", "steps": step, "log": log}

    if verbose:
        print("MAX_STEPS — hết %d bước, chưa tới goal." % max_steps)
    return {"status": "max_steps", "steps": max_steps, "log": log}


def run_infer_episode_for_map(
    map_path,
    max_steps=MAX_STEPS_INFER,
    verbose=True,
    on_step=None,
    policy_json=None,
):
    """Nạp map + policy, chạy một episode infer."""
    from map.map_io import build_sim_map_from_file

    q, _policy_path = load_policy_for_infer(policy_json)
    if not q:
        raise FileNotFoundError("Không tìm thấy policy — chạy train trước hoặc chọn file .json.")
    sim = build_sim_map_from_file(map_path)
    return sim, run_infer_episode(sim, q, max_steps=max_steps, verbose=verbose, on_step=on_step)


def run_infer(map_path=None, max_steps=MAX_STEPS_INFER, verbose=True, policy_json=None):
    from map.map_io import list_map_files, build_sim_map_from_file

    q, policy_path = load_policy_for_infer(policy_json)
    if not q:
        print("Không tìm thấy policy — chạy train trước hoặc chọn file .json.")
        return None

    if map_path is None:
        infer_paths = list_map_files("infer")
        if not infer_paths:
            print("Không có map infer trong map/infer/")
            return None
        map_path = infer_paths[0]

    sim = build_sim_map_from_file(map_path)
    train_paths = list_map_files("train")

    print("--- SS26 infer (PC simulation) ---")
    print("map:", sim.get("name", "?"), "%dx%d" % (sim["width"], sim["height"]))
    print("file:", map_path)
    print("goal:", sim["goal"], "| checkpoints:", sim["checkpoints"], "| start:", sim["start"])
    print("train maps:", len(train_paths), "file(s) in map/train/")
    print("policy:", policy_path)
    print("---")

    outcome = run_infer_episode(sim, q, max_steps=max_steps, verbose=verbose)
    if outcome["status"] == "goal":
        print("=====goal success========")
    else:
        print("--- kết quả:", outcome["status"], "| steps:", outcome["steps"])
    return outcome
