"""Runtime paths for source runs and PyInstaller builds."""

import os
import sys


def is_frozen():
    return bool(getattr(sys, "frozen", False))


def app_root():
    """Writable app root: repo root in source, exe folder in frozen builds."""
    if is_frozen():
        return os.path.dirname(os.path.abspath(sys.executable))
    return os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))


def bundled_root():
    """Read-only bundled root: PyInstaller _MEIPASS, or repo root in source."""
    if is_frozen():
        return os.path.abspath(getattr(sys, "_MEIPASS", app_root()))
    return app_root()


def app_data_path(*parts):
    return os.path.join(app_root(), *parts)


def bundled_path(*parts):
    return os.path.join(bundled_root(), *parts)
