#!/usr/bin/env python3
"""Mở UI tạo / chỉnh map → lưu JSON trong map/train/ hoặc map/infer/."""

import os
import sys

_ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _ROOT)
sys.path.insert(0, os.path.join(_ROOT, "Simulation"))


def main():
    from Ui_app.create_map_UI import run_app

    run_app()


if __name__ == "__main__":
    main()
