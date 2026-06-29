"""Helper chạy một tab từ repo root (python libs/app_tabs/create_map.py)."""

import os
import sys


def run_tab(initial_tab=0):
    _repo = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    _libs = os.path.join(_repo, "libs")
    if _libs not in sys.path:
        sys.path.insert(0, _libs)
    from bootstrap import setup_paths

    setup_paths()
    from app_tabs.shell import run_app

    run_app(initial_tab=initial_tab)
