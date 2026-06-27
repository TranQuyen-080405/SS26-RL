"""Vòng chính robot — infer policy (khung)."""

from robot_map import init_robot_map
from robot_state import make_robot
from policy_io import load_policy_bin
from action import run_policy_step


MAP_W = 10
MAP_H = 10


def run():
    print("--------------------------------------------------")
    print("SUMMER SCHOOL 2026 - ROBOT REINFORCEMENT LEARNING")
    print("--------------------------------------------------")

    q = load_policy_bin("Q_table/policy.bin")
    if not q:
        print("Q_table/policy.bin not found — train on PC first")
        return

    rmap = init_robot_map(MAP_W, MAP_H)
    bot = make_robot(0, 0, "N", rmap)

    # TODO: dist_goal / dist_cp từ nguồn thật hoặc config map
    dist_goal = 0
    dist_cp = [0, 0, 0]

    while True:
        run_policy_step(bot, q, dist_goal, dist_cp)
        # TODO: break khi at_goal
