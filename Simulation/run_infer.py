"""CLI infer — đọc map từ map/infer/."""

import argparse
import os
import sys

_SIM = os.path.abspath(os.path.join(os.path.dirname(__file__)))
_ROOT = os.path.abspath(os.path.join(_SIM, ".."))
sys.path.insert(0, _ROOT)
sys.path.insert(0, _SIM)

from rl_runner import run_infer


def main():
    parser = argparse.ArgumentParser(description="Infer greedy trên map/infer/")
    parser.add_argument(
        "--policy",
        default=None,
        help="File .bin trong Q_table/ (vd. policy.bin); mặc định policy.bin",
    )
    args = parser.parse_args()
    run_infer(policy_bin=args.policy)


if __name__ == "__main__":
    main()
