"""Thiết lập sys.path — gọi từ main.py hoặc launcher tab trước khi import app."""

import os
import sys

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
_LIBS = os.path.abspath(os.path.dirname(__file__))
_SIM = os.path.join(_LIBS, "Simulation")
_ROBOT_EMBBED = os.path.join(_LIBS, "Robot_embbed")
_CHECKPOINTS = os.path.join(_REPO_ROOT, "checkpoints")


def setup_paths():
    """Thêm libs/, Simulation/, Robot_embbed/ vào sys.path."""
    for p in (_LIBS, _SIM, _ROBOT_EMBBED):
        if p not in sys.path:
            sys.path.insert(0, p)
    return _REPO_ROOT, _LIBS, _SIM


def repo_root():
    return _REPO_ROOT


def libs_dir():
    return _LIBS


def simulation_dir():
    return _SIM


def robot_embbed_dir():
    return _ROBOT_EMBBED


def checkpoints_dir():
    return _CHECKPOINTS
