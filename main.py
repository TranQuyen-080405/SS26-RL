#!/usr/bin/env python3
"""
SS26-RL — entry point.
  python main.py
  python libs/app_tabs/create_map.py      # tab Tạo map
  python libs/app_tabs/robot_monitor.py   # tab Robot Monitor (standalone BLE)
"""

import os
import sys

_LIBS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "libs")
if _LIBS not in sys.path:
    sys.path.insert(0, _LIBS)

from bootstrap import setup_paths

setup_paths()

from app_tabs.shell import main

if __name__ == "__main__":
    main()
