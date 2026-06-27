"""CLI train — đọc map từ map/train/, eval trên map/infer/."""

import argparse
import os
import sys

_SIM = os.path.abspath(os.path.join(os.path.dirname(__file__)))
_ROOT = os.path.abspath(os.path.join(_SIM, ".."))
sys.path.insert(0, _ROOT)
sys.path.insert(0, _SIM)

from rl_runner import run_train, N_EPISODES_DEFAULT


def main():
    parser = argparse.ArgumentParser(description="Train Q-learning trên map/train/")
    parser.add_argument(
        "--episodes",
        type=int,
        default=N_EPISODES_DEFAULT,
        help="Số episode (mặc định %d)" % N_EPISODES_DEFAULT,
    )
    parser.add_argument(
        "--checkpoint",
        default=None,
        help="Tên trong Q_table/ (vd. policy) hoặc đường dẫn .json/.bin để train tiếp",
    )
    args = parser.parse_args()
    run_train(n_episodes=args.episodes, checkpoint=args.checkpoint)


if __name__ == "__main__":
    main()
