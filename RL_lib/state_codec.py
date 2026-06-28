"""Giải mã / ghép state cho Learn Lab (encode_state trong rl_core)."""

from RL_lib.rl_core import (
    ACTIONS,
    HEADING_IDX,
    N_CP_MAX,
    N_ROWS,
    TREND_COMBOS,
    TREND_SLOTS,
    encode_state,
    get_policy,
    obstacle_bits,
)

_IDX_HEADING = {v: k for k, v in HEADING_IDX.items()}


def decode_state(encoded):
    hi = encoded % 4
    rest = encoded // 4
    packed = rest % TREND_COMBOS
    bits = rest // TREND_COMBOS
    trends = []
    p = packed
    for _ in range(TREND_SLOTS):
        trends.append((p % 3) - 1)
        p //= 3
    obs = ((bits >> 3) & 1, (bits >> 2) & 1, (bits >> 1) & 1, bits & 1)
    return {
        "s": encoded,
        "obstacle_nwes": obs,
        "dist_goal_trend": trends[0],
        "dist_cp_trends": trends[1:],
        "heading": _IDX_HEADING.get(hi, "N"),
        "obstacle_bits": bits,
        "packed_trends": packed,
    }


def build_state(obstacle_nwes, dist_goal_trend, dist_cp_trends, heading):
    s = encode_state(obstacle_nwes, dist_goal_trend, dist_cp_trends, heading)
    dec = decode_state(s)
    dec["s"] = s
    return dec


def policy_preview(encoded, q_table):
    if not q_table or encoded < 0 or encoded >= len(q_table):
        return None
    row = q_table[encoded]
    action = get_policy(encoded, q_table)
    return {"action": action, "q_forward": row[0], "q_left": row[1], "q_right": row[2]}


def export_state_snippet(obstacle_nwes, dist_goal_trend, dist_cp_trends, heading, s):
    cp = list(dist_cp_trends) + [0] * N_CP_MAX
    cp = cp[:N_CP_MAX]
    lines = [
        '"""State preset — paste vào lab / test (encode_state trong rl_core)."""',
        "",
        "OBSTACLE_NWES = %s  # N, W, E, S" % (tuple(int(x) for x in obstacle_nwes),),
        "DIST_GOAL_TREND = %d  # -1 xa | 0 giữ | 1 gần" % dist_goal_trend,
        "DIST_CP_TRENDS = %s" % (cp,),
        'HEADING = "%s"' % heading,
        "",
        "# from modules.logics.rl_core import encode_state",
        "# s = encode_state(OBSTACLE_NWES, DIST_GOAL_TREND, DIST_CP_TRENDS, HEADING)",
        "# s == %d  (N_ROWS=%d)" % (s, N_ROWS),
    ]
    return "\n".join(lines)
