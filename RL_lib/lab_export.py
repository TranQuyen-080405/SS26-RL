"""Xuất module Python đồng bộ PC ↔ Robot_embbed từ Learn Lab."""


def export_reward_config_py(values):
    lines = [
        '"""',
        "reward_config.py — đồng bộ từ SS26 Learn Lab.",
        "PC: Simulation/robot/trainer import module này.",
        "ESP32: copy vào modules/logics/reward_config.py (chỉ hằng số; train trên PC).",
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
    lines.append("# compute_reward — chỉ PC train; ESP32 infer không gọi.")
    lines.append("# Giữ nguyên phần logic trong RL_lib/reward_config.py trên repo PC.")
    return "\n".join(lines) + "\n"


def export_robot_reward_constants(values):
    """File gọn cho ESP32 — chỉ hằng số, không import Simulation."""
    lines = [
        '"""Hằng reward — sync từ PC Learn Lab (modules/logics/reward_config.py)."""',
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
        "MAX_ROTATE_STREAK",
        "MAX_NODE_REVISITS",
        "MAX_PING_PONG_CYCLES",
        "COLLISION_RESET",
        "MAX_STEPS_PER_EPISODE",
    ):
        v = values.get(k, 0)
        if k == "COLLISION_RESET":
            lines.append("%s = %s" % (k, "True" if v else "False"))
        elif isinstance(v, float):
            lines.append("%s = %s" % (k, v if v != int(v) else "%d.0" % int(v)))
        else:
            lines.append("%s = %d" % (k, int(v)))
    return "\n".join(lines) + "\n"
