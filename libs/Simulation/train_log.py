"""Train / infer log — shared layout."""

import os
import textwrap

_WIDTH = 46
TITLE_TRAIN = "SummerSchool 2026 - Train"
TITLE_INFER = "SummerSchool 2026 - Inference"

_MODE_LABELS = {
    "random": "random",
    "sequential": "sequential",
    "single": "single map",
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
):
    global _episode_header_printed
    _episode_header_printed = False

    banner(TITLE_TRAIN)
    line("Mode", _MODE_LABELS.get(map_mode, map_mode))
    line("Episodes", n_episodes)
    if resuming:
        line("Load Q from", _basename(checkpoint_label))
    else:
        line("Load Q from", "new (empty Q-table)")
    line("Save policy", _basename(export_path))
    name_list("Train maps", train_names)
    banner("Training")


def print_infer_header(sim_map, policy_path):
    banner(TITLE_INFER)
    cps = sim_map.get("checkpoints") or []
    cp_txt = ("  cp %s" % (cps,)) if cps else ""
    line(
        "Run",
        "map %s %dx%d  policy %s  start %s  goal %s%s"
        % (
            sim_map.get("name", "?"),
            sim_map["width"],
            sim_map["height"],
            _basename(policy_path),
            sim_map.get("start"),
            sim_map.get("goal"),
            cp_txt,
        ),
    )


def print_infer_step(step, x, y, direction, state, action):
    print(
        "step %3d  pos (%d,%d) %s  s=%d  action %s"
        % (step, x, y, direction, state, action)
    )


def print_infer_summary(status, steps):
    if status == "goal":
        line("Result", "goal in %d steps" % steps)
    elif status == "collision":
        line("Result", "collision at step %d" % steps)
    else:
        line("Result", "%s after %d steps" % (status, steps))


def print_train_start(map_mode, n_episodes, n_maps, q_rows=None, resuming=False):
    mode = _MODE_LABELS.get(map_mode, map_mode)
    line("Plan", "%s, %d episodes, %d map(s)" % (mode, n_episodes, n_maps))
    if resuming and q_rows is not None:
        line("Q-table", "resume, %d rows" % q_rows)


def print_sequential_plan(plan):
    print("Map order:")
    for sim, n_ep in plan:
        print("  %s -> %d ep" % (sim.get("name", "?"), n_ep))


def print_episode_table_header():
    global _episode_header_printed
    if _episode_header_printed:
        return
    _episode_header_printed = True
    print("%-8s %-16s %s" % ("Episode", "Map", "Goals"))
    print("%-8s %-16s %s" % ("-------", "----------------", "-----"))


def print_episode(ep_index, map_name, goals_in_block):
    print_episode_table_header()
    tag = map_name or "?"
    print("%-8d %-16s %d" % (ep_index, tag, goals_in_block))


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
