"""Xuất snippet reward từ Learn Lab (PC train)."""


def export_reward_config_py(values):
    lines = [
        '"""',
        "reward_config.py — đồng bộ từ SS26 Learn Lab.",
        "PC: Simulation/robot/trainer import module này.",
        '"""',
        "",
    ]
    for k in (
        "R_STEP",
        "R_COLLISION",
        "R_GOAL_CLOSER",
        "R_GOAL_FARTHER",
        "R_CP_CLOSER",
        "R_CP_FARTHER",
        "R_CHECKPOINT_FIRST",
        "R_GOAL_REACHED",
        "R_ROTATE_IN_PLACE",
        "R_FACING_CLEAR",
        "R_FORWARD_CLEAR",
        "R_WASTED_ROTATE",
    ):
        v = values.get(k, 0)
        if isinstance(v, float) and v == int(v):
            lines.append("%s = %d.0" % (k, int(v)))
        else:
            lines.append("%s = %s" % (k, v))

    lines.append("")
    for k in (
        "MAX_ROTATE_STREAK",
        "MAX_NODE_REVISITS",
        "MAX_PING_PONG_CYCLES",
        "MAX_STEPS_PER_EPISODE",
    ):
        lines.append("%s = %d" % (k, int(values.get(k, 0))))

    lines.append("COLLISION_RESET = %s" % ("True" if values.get("COLLISION_RESET") else "False"))
    lines.append("")
    lines.append("# compute_reward — chỉ PC train; ESP32 infer dùng policy.bin.")
    lines.append("# Giữ nguyên phần logic trong RL_lib/reward_config.py trên repo PC.")
    return "\n".join(lines) + "\n"
