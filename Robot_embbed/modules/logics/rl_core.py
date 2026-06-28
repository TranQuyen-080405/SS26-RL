"""RL thuần hàm — bản MicroPython (sync từ RL_lib/rl_core.py)."""

from modules.logics.grid import DIRECTIONS

N_CP_MAX = 3
ACTIONS = ("forward", "rotate left", "rotate right")
HEADING_IDX = {"N": 0, "W": 1, "E": 2, "S": 3}
TREND_SLOTS = 1 + N_CP_MAX
TREND_COMBOS = 3 ** TREND_SLOTS
N_ROWS = 16 * TREND_COMBOS * 4


def dist_trend(prev_dist, current_dist):
    if current_dist < prev_dist:
        return 1
    if current_dist > prev_dist:
        return -1
    return 0


def obstacle_bits(obstacle_nwes):
    n, w, e, s = obstacle_nwes
    return (n & 1) * 8 + (w & 1) * 4 + (e & 1) * 2 + (s & 1)


def _pad_cp_trends(dist_cp_trends):
    out = [0] * N_CP_MAX
    for i in range(N_CP_MAX):
        if dist_cp_trends and i < len(dist_cp_trends):
            out[i] = dist_cp_trends[i]
    return out


def encode_state(obstacle_nwes, dist_goal_trend, dist_cp_trends, heading):
    bits = obstacle_bits(obstacle_nwes)
    trends = [dist_goal_trend] + _pad_cp_trends(dist_cp_trends)
    packed = 0
    for i, t in enumerate(trends):
        packed += (t + 1) * (3 ** i)
    if heading not in HEADING_IDX:
        heading = "N"
    return bits * TREND_COMBOS * 4 + packed * 4 + HEADING_IDX[heading]


def get_policy(encoded_state, q_table, actions=ACTIONS):
    if not q_table or encoded_state < 0 or encoded_state >= len(q_table):
        return actions[0]
    row = q_table[encoded_state]
    if not row:
        return actions[0]
    best = 0
    for i in range(1, len(row)):
        if row[i] > row[best]:
            best = i
    return actions[best]
