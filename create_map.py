#!/usr/bin/env python3
"""Chạy tab Tạo map — xem main.py (app thống nhất)."""

import os
import sys

_ROOT = os.path.dirname(os.path.abspath(__file__))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from main import run_app

if __name__ == "__main__":
    run_app(initial_tab=0)
