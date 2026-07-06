import sys
import os

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, ROOT)

from RL_lib.rl_core import encode_state, dist_trend, N_ROWS, get_policy


def test_dist_trend():
    assert dist_trend(10, 8) == 1
    assert dist_trend(8, 10) == -1
    assert dist_trend(5, 5) == 0


def test_encode_range():
    s = encode_state((0, 0, 0, 0), 0, [0, 0, 0], "N")
    assert 0 <= s < N_ROWS
    s2 = encode_state((1, 1, 1, 1), -1, [1, -1, 0], "E")
    assert 0 <= s2 < N_ROWS


def test_encode_visited_bit_changes_state():
    s_new = encode_state((0, 0, 0, 0), 0, [0, 0, 0], "N", visited_before=0)
    s_revisit = encode_state((0, 0, 0, 0), 0, [0, 0, 0], "N", visited_before=1)
    assert s_new != s_revisit


def test_get_policy():
    q = [[1.0, 0.0, 0.0]] * N_ROWS
    q[0] = [0.0, 2.0, 0.0]
    assert get_policy(0, q) == "rotate left"


if __name__ == "__main__":
    test_dist_trend()
    test_encode_range()
    test_encode_visited_bit_changes_state()
    test_get_policy()
    print("ok")
