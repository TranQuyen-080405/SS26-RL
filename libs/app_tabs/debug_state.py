#!/usr/bin/env python3
"""Chạy tab State & Reward (Learn Lab)."""

import os
import sys

_LIBS = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if _LIBS not in sys.path:
    sys.path.insert(0, _LIBS)

from app_tabs._launcher import run_tab

if __name__ == "__main__":
    run_tab(initial_tab=2)
