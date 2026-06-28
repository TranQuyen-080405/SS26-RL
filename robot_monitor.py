#!/usr/bin/env python3
"""Tương thích cũ — mở tab Robot Monitor trong main.py."""

import os
import sys

_ROOT = os.path.dirname(os.path.abspath(__file__))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from main import RobotMonitorApp, run_app

if __name__ == "__main__":
    run_app(initial_tab=2)
