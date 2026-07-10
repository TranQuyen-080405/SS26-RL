"""Apply SS26 app/window icon from bundled assets."""

import os
import sys
import tkinter as tk

from runtime_paths import app_data_path, bundled_path


def _asset_dirs():
    seen = set()
    dirs = []
    for base in (bundled_path("assets"), app_data_path("assets")):
        norm = os.path.normcase(os.path.abspath(base))
        if norm in seen:
            continue
        seen.add(norm)
        if os.path.isdir(base):
            dirs.append(base)
    return dirs


def _first_existing(filename):
    for base in _asset_dirs():
        path = os.path.join(base, filename)
        if os.path.isfile(path):
            return path
    return None


def apply_app_icon(root):
    """Set taskbar/title icon from assets/icon_app.* (fallback logo.png)."""
    if sys.platform.startswith("linux"):
        return

    ico_path = _first_existing("icon_app.ico")
    if ico_path and sys.platform == "win32":
        try:
            root.iconbitmap(default=ico_path)
        except tk.TclError:
            pass

    for filename in ("icon_app.png", "logo.png"):
        png_path = _first_existing(filename)
        if not png_path:
            continue
        try:
            icon = tk.PhotoImage(file=png_path)
            root.iconphoto(True, icon)
            root._app_icon = icon
            return
        except tk.TclError:
            continue
