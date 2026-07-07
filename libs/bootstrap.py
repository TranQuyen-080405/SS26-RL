"""Set up sys.path for source runs and packaged builds."""

import os
import sys

from runtime_paths import app_root, bundled_path

_REPO_ROOT = app_root()
_LIBS = bundled_path("libs")
_SIM = bundled_path("libs", "Simulation")
_ROBOT_EMBBED = bundled_path("libs", "Robot_embbed")
_CHECKPOINTS = os.path.join(_REPO_ROOT, "checkpoints")


def setup_paths():
    """Add libs/, Simulation/, and Robot_embbed/ to sys.path."""
    for p in (_LIBS, _SIM, _ROBOT_EMBBED):
        if os.path.isdir(p) and p not in sys.path:
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