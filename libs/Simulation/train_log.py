"""Train / infer log — shared layout."""

import os
import textwrap

_WIDTH = 80
SEP = "-" * _WIDTH
TITLE_TRAIN = "SummerSchool 2026 - Train"
TITLE_INFER = "SummerSchool 2026 - Inference"
TITLE_INFER_LOG = "SummerSchool 2026 - Inference Log"

_MODE_LABELS = {
    "random": "random",
    "sequential": "sequence",
    "single": "single",
    "curriculum": "curriculum",
}


def _basename(path):
    if not path:
        return "-"
    return os.path.basename(str(path).replace("\\", "/"))


def banner(title):
    print("-" * _WIDTH)
    print(title)
    print("-" * _WIDTH)


def line(key, value):
    print("%-14s %s" % (key + ":", value))


def name_list(label, names):
    print("%s (%d)" % (label, len(names)))
    if not names:
        print("  (none)")
        return
    text = ", ".join(str(n) for n in names)
    for row in textwrap.wrap(text, width=_WIDTH - 2):
        print("  %s" % row)


_episode_header_printed = False


def print_train_header(
    train_names,
    eval_names,
    map_mode,
    n_episodes,
    checkpoint_label,
    export_path,
    resuming,
    reward_formula=None,
):
    global _episode_header_printed
    _episode_header_printed = False

    banner(TITLE_TRAIN)
    line("Mode", _MODE_LABELS.get(map_mode, map_mode))
    line("Episodes", n_episodes)
    reward_name = (reward_formula or "").strip()
    line("Reward formula", reward_name if reward_name else "(chưa đặt tên)")
    if resuming:
        line("Load Q from", _basename(checkpoint_label))
    else:
        line("Load Q from", "new (empty Q-table)")
    line("Save policy", _basename(export_path))
    name_list("Train maps", train_names)
    banner("Training")


def print_infer_header(sim_map, policy_path):
    banner(TITLE_INFER)
    print("Policy: %s" % _basename(policy_path))
    for meta in format_map_meta_lines(sim_map.get("name", "?"), sim_map)[1:]:
        print(meta)


def fmt_xy(pos):
    if not pos or len(pos) < 2:
        return "(?,?)"
    return "(%d,%d)" % (int(pos[0]), int(pos[1]))


def format_checkpoints_line(checkpoints):
    if checkpoints:
        return "Checkpoints: %s" % ", ".join(fmt_xy(cp) for cp in checkpoints)
    return "Checkpoints: (none)"


def format_map_meta_lines(map_label, sim_map):
    return [
        SEP,
        "Map: %s" % map_label,
        "Start: %s" % fmt_xy(sim_map.get("start")),
        "Goal: %s" % fmt_xy(sim_map.get("goal")),
        format_checkpoints_line(sim_map.get("checkpoints") or []),
    ]


def format_infer_end_reason(status, steps):
    if status == "goal":
        return "End: reached goal after %d steps" % steps
    if status == "collision":
        return "End: collision at step %d" % steps
    if status == "max_steps":
        return "End: max steps reached (%d steps)" % steps
    if status == "stopped":
        return "End: stopped at step %d" % steps
    return "End: %s (%d steps)" % (status, steps)


def format_robot_episode_stats(walls_seen, new_cells, checkpoints_touched):
    return "Stats: walls_seen=%d | new_cells=%d | checkpoints=%d" % (
        int(walls_seen),
        int(new_cells),
        int(checkpoints_touched),
    )


def format_export_log_header(policy_name, n_maps):
    return "\n".join(
        [
            SEP,
            TITLE_INFER_LOG,
            "Policy: %s" % policy_name,
            "Maps: %d" % n_maps,
            SEP,
            "",
        ]
    )


def format_episode_actions_log(map_label, sim_map, outcome, include_reward=False, include_end=True):
    lines = list(format_map_meta_lines(map_label, sim_map))
    lines.append(format_step_log_header(include_reward=include_reward))
    for entry in outcome.get("log") or []:
        lines.append(format_step_log_entry(entry, include_reward=include_reward))
    if include_end:
        lines.append(
            format_infer_end_reason(
                outcome.get("status", "?"),
                int(outcome.get("steps", 0)),
            )
        )
    return "\n".join(lines) + "\n\n"


def format_step_log_header(include_reward=True):
    if include_reward:
        return "%-5s  %-8s  %-3s  %5s  %-14s  %8s" % (
            "step",
            "pos",
            "dir",
            "s",
            "action",
            "reward",
        )
    return "%-5s  %-8s  %-3s  %5s  %s" % ("step", "pos", "dir", "s", "action")


def print_step_log_header():
    print(format_step_log_header())


def format_step_log_entry(entry, include_reward=True):
    return format_step_log_line(
        entry.get("step", 0),
        entry.get("x", 0),
        entry.get("y", 0),
        entry.get("direct", "?"),
        entry.get("s", 0),
        entry.get("action", "?"),
        reward=entry.get("reward"),
        include_reward=include_reward,
    )


def format_step_log_line(step, x, y, direction, state, action, reward=None, include_reward=True):
    pos = "(%d,%d)" % (x, y)
    if include_reward:
        reward_val = 0.0 if reward is None else float(reward)
        return "%-5d  %-8s  %-3s  %5d  %-14s  %+8.1f" % (
            step,
            pos,
            direction,
            state,
            action,
            reward_val,
        )
    return "%-5d  %-8s  %-3s  %5d  %s" % (step, pos, direction, state, action)


def print_infer_step(step, x, y, direction, state, action, reward=None):
    print(format_step_log_line(step, x, y, direction, state, action, reward=reward))


def print_infer_summary(status, steps):
    print(format_infer_end_reason(status, steps))


def print_train_start(map_mode, n_episodes, n_maps, q_rows=None, resuming=False):
    mode = _MODE_LABELS.get(map_mode, map_mode)
    line("Plan", "%s, %d episodes, %d map(s)" % (mode, n_episodes, n_maps))
    if resuming and q_rows is not None:
        line("Q-table", "resume, %d rows" % q_rows)


def print_sequential_plan(plan):
    print("Map order:")
    for sim, n_ep in plan:
        print("  %s -> %d ep" % (sim.get("name", "?"), n_ep))


def format_train_block_line(block_start, block_episodes, map_name, goals_in_block, include_map=True):
    if block_episodes <= 0:
        return ""
    ep_from = block_start + 1
    ep_to = block_start + block_episodes
    if include_map:
        return "Episodes %d-%d | map: %s | goals: %d/%d" % (
            ep_from,
            ep_to,
            map_name or "?",
            goals_in_block,
            block_episodes,
        )
    return "Episodes %d-%d | goals: %d/%d" % (
        ep_from,
        ep_to,
        goals_in_block,
        block_episodes,
    )


def print_train_block(block_start, block_episodes, map_name, goals_in_block, include_map=True):
    text = format_train_block_line(
        block_start, block_episodes, map_name, goals_in_block, include_map=include_map
    )
    if text:
        print(text)


def print_curriculum_block(sim_map, episodes_run, goals_hit, goal_target):
    name = sim_map.get("name", "?")
    for meta in format_map_meta_lines(name, sim_map)[1:]:
        print(meta)
    print(
        "Curriculum block | episodes: %d | goals: %d/%d"
        % (episodes_run, goals_hit, goal_target)
    )


def print_episode_table_header():
    global _episode_header_printed
    if _episode_header_printed:
        return
    _episode_header_printed = True
    print("%-8s  %-20s  %5s" % ("Episode", "Map", "Goals"))
    print("%-8s  %-20s  %5s" % ("-------", "--------------------", "-----"))


def print_episode(ep_index, map_name, goals_in_block):
    print_episode_table_header()
    tag = map_name or "?"
    print("%-8d  %-20s  %5d" % (ep_index, tag, goals_in_block))


def print_train_block_summary(block_start, block_episodes, map_name, goals_in_block):
    """Alias — log train theo cụm episode."""
    print_train_block(block_start, block_episodes, map_name, goals_in_block)


def print_stopped_at(ep_index):
    line("Stop", "user stopped at episode %d" % ep_index)


def print_train_summary(stopped, export_path, n_goal, episodes_done, best_label=None):
    banner("Result")
    line("Status", "stopped early" if stopped else "done")
    line("Episodes run", episodes_done)
    line("Reached goal", "%d / %d" % (n_goal, episodes_done))
    if episodes_done:
        line("Goal rate", "%.1f%%" % (100.0 * n_goal / episodes_done))
    if stopped:
        line("Policy saved", "%s (current Q)" % _basename(export_path))
    elif best_label:
        line("Policy saved", _basename(export_path))
        line("Best pick", best_label)
    else:
        line("Policy saved", _basename(export_path))
        print("! No greedy-OK policy on eval — saved final Q")
