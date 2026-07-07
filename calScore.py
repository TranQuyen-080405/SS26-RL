"""Kaggle custom metric chấm policy trên toàn bộ map inference.

Submission CSV phải có 5184 dòng và các cột:
    id,q_forward,q_rotate_left,q_rotate_right

Khi đóng gói metric trên Kaggle, đặt thư mục ``libs`` cạnh file này; các map
ẩn được đọc từ ``map/infer/*.json`` (cạnh main.py).
"""

import math
import os
import sys
from pathlib import Path

import pandas as pd
import pandas.api.types


class ParticipantVisibleError(Exception):
    """Lỗi dữ liệu submission được phép hiển thị cho thí sinh."""


_ROOT = os.path.dirname(os.path.abspath(globals().get("__file__", os.getcwd())))
_LIBS = os.path.join(_ROOT, "libs")
if _LIBS not in sys.path:
    sys.path.insert(0, _LIBS)

from bootstrap import setup_paths
setup_paths()

from map.map_io import build_sim_map_from_file
from RL_lib.rl_core import N_ROWS, get_policy
from Simulation.rl_runner import (
    MAX_STEPS_INFER,
    _episode_at_goal,
    _reset_at_start,
    _robot_map_from_sim,
)
from robot import action as act
from robot import robot as rb


POLICY_COLUMNS = ("q_forward", "q_rotate_left", "q_rotate_right")
KAGGLE_INFER_MAP_DIR = Path(
    "/kaggle/input/datasets/namphongnguynhu/maze-maps-csess26/map/infer"
)


def _list_infer_map_files():
    """Dùng dataset Kaggle khi có; local thì dùng map/infer cạnh main.py."""
    candidates = (
        KAGGLE_INFER_MAP_DIR,
        Path("/kaggle/input/maze-maps-csess26/map/infer"),
        Path(_ROOT) / "map" / "infer",
    )
    for directory in candidates:
        if directory.is_dir():
            paths = sorted(str(path) for path in directory.glob("*.json"))
            if paths:
                return paths
    raise RuntimeError(
        "Không tìm thấy map inference trong dataset maze-maps-csess26 "
        "hoặc map/infer cạnh main.py."
    )


def _submission_to_q_table(submission: pd.DataFrame, row_id_column_name: str):
    if row_id_column_name not in submission.columns:
        raise ParticipantVisibleError("Submission thiếu cột ID '%s'." % row_id_column_name)

    policy = submission.drop(columns=[row_id_column_name])
    if tuple(policy.columns) != POLICY_COLUMNS:
        raise ParticipantVisibleError(
            "Các cột policy phải đúng thứ tự: %s." % ", ".join(POLICY_COLUMNS)
        )
    if len(policy) != N_ROWS:
        raise ParticipantVisibleError(
            "Policy phải có đúng %d dòng, hiện có %d." % (N_ROWS, len(policy))
        )

    for column in POLICY_COLUMNS:
        if not pandas.api.types.is_numeric_dtype(policy[column]):
            raise ParticipantVisibleError("Cột '%s' phải chứa số." % column)

    q_table = policy.astype(float).values.tolist()
    if any(not math.isfinite(value) for row in q_table for value in row):
        raise ParticipantVisibleError("Policy không được chứa NaN hoặc giá trị vô hạn.")
    return q_table


def calculate_map_score(sim_map, q_table):
    """Chạy greedy policy trên một map và trả điểm của map đó."""
    rmap = _robot_map_from_sim(sim_map)
    bot = rb.make_robot(sim_map["start"][0], sim_map["start"][1], "N", rmap)
    _reset_at_start(bot, sim_map)

    visited_cps = set()
    checkpoints = set(tuple(cp) for cp in sim_map.get("checkpoints", []))
    if (bot["x"], bot["y"]) in checkpoints:
        visited_cps.add((bot["x"], bot["y"]))

    collision_occurred = False
    goal_reached = False
    step_count = 0

    for step in range(1, MAX_STEPS_INFER + 1):
        if _episode_at_goal(bot, sim_map):
            goal_reached = True
            break

        action_name = get_policy(rb.build_encoded_state(bot), q_table)
        result = act.execute_action_sim(bot, sim_map, action_name)
        step_count = step

        position = (bot["x"], bot["y"])
        if position in checkpoints:
            visited_cps.add(position)
        if result.get("collision"):
            collision_occurred = True
            break
        if _episode_at_goal(bot, sim_map):
            goal_reached = True
            break

    return float(
        (400 if goal_reached else 0)
        + 100 * len(visited_cps)
        - (100 if collision_occurred else 0)
        - 2 * step_count
    )


def score(solution: pd.DataFrame, submission: pd.DataFrame, row_id_column_name: str) -> float:
    """Chạy policy nộp lên trên mọi map inference ẩn và trả tổng điểm."""
    del solution
    q_table = _submission_to_q_table(submission, row_id_column_name)

    infer_paths = _list_infer_map_files()


    total = sum(
        calculate_map_score(build_sim_map_from_file(path), q_table)
        for path in infer_paths
    )
    if not math.isfinite(total):
        raise RuntimeError("Điểm tính được không hợp lệ.")
    return float(total)


def main(policy_csv="policy.csv"):
    """Chạy thử judge local bằng chính file CSV sẽ nộp Kaggle."""
    submission = pd.read_csv(policy_csv)
    print("Total Score:", score(pd.DataFrame(), submission, "id"))


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "policy.csv")
