#!/usr/bin/env python3
"""
Tra cứu thành phần RL state theo số thứ tự.

Chạy:
    python state_lookup.py

Nhập state index (0 .. N_ROWS-1) để xem tường N/W/E/S, ô đã qua,
trend goal/CP và hướng — giống panel STATE trong tab Edit State.
"""

from __future__ import annotations

import os
import sys
import tkinter as tk
from tkinter import messagebox, ttk

_ROOT = os.path.dirname(os.path.abspath(__file__))
_LIBS = os.path.join(_ROOT, "libs")
if _LIBS not in sys.path:
    sys.path.insert(0, _LIBS)

from bootstrap import setup_paths

setup_paths()

from RL_lib.rl_core import N_ROWS
from RL_lib.state_codec import decode_state

_STATE_BG = "#eceff4"
_STATE_FG = "#1e1e2e"
_FIND_PNG = "find.png"
_FIND_ICO = "find.ico"


def _asset_path(filename: str) -> str:
    if getattr(sys, "frozen", False):
        base = getattr(sys, "_MEIPASS", _ROOT)
    else:
        base = _ROOT
    return os.path.join(base, "assets", filename)


def _load_find_image(root: tk.Misc, target_px: int = 22) -> tk.PhotoImage | None:
    path = _asset_path(_FIND_PNG)
    if not os.path.isfile(path):
        return None
    try:
        img = tk.PhotoImage(file=path, master=root)
    except tk.TclError:
        return None
    factor = max(1, img.width() // target_px)
    if factor > 1:
        img = img.subsample(factor, factor)
    return img


def _apply_app_icon(root: tk.Tk):
    if sys.platform.startswith("linux"):
        return
    ico_path = _asset_path(_FIND_ICO)
    if ico_path and sys.platform == "win32" and os.path.isfile(ico_path):
        try:
            root.iconbitmap(default=ico_path)
        except tk.TclError:
            pass
    img = _load_find_image(root, target_px=32)
    if img is not None:
        root.iconphoto(True, img)
        root._app_icon = img


def format_state_rows(state_index: int) -> list[str]:
    decoded = decode_state(state_index)
    n_wall, w_wall, e_wall, s_wall = decoded["obstacle_nwes"]
    visited = int(decoded["visited_before"])
    return [
        "Hướng: %s" % decoded["heading"],
        "Tường nhìn thấy: N=%d W=%d E=%d S=%d" % (n_wall, w_wall, e_wall, s_wall),
        "Ô đã qua: %s" % visited,
        "Trend goal: %+d" % int(decoded["dist_goal_trend"]),
        "Trend CP: %s" % list(decoded["dist_cp_trends"]),
    ]


class StateLookupApp:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("SS26 — Tra cứu State")
        self.root.minsize(380, 280)
        self.root.configure(bg="#f5f5f5")
        _apply_app_icon(self.root)

        self._find_img: tk.PhotoImage | None = None
        self._state_labels: list[tk.Label] = []
        self._build_ui()
        self._lookup()

    def _build_ui(self):
        pad = {"padx": 12, "pady": 8}

        top = ttk.Frame(self.root, padding=(12, 12, 12, 4))
        top.pack(fill=tk.X)

        ttk.Label(top, text="Số thứ tự state:").pack(side=tk.LEFT)
        self._state_var = tk.StringVar(value="0")
        entry = ttk.Entry(top, textvariable=self._state_var, width=10)
        entry.pack(side=tk.LEFT, padx=(8, 8))
        entry.bind("<Return>", lambda _e: self._lookup())

        self._find_img = _load_find_image(self.root, target_px=22)
        if self._find_img is not None:
            tk.Button(
                top,
                image=self._find_img,
                command=self._lookup,
                relief=tk.FLAT,
                bd=0,
                bg="#f5f5f5",
                activebackground="#e8e8e8",
                cursor="hand2",
            ).pack(side=tk.LEFT)
        else:
            ttk.Button(top, text="Xem", command=self._lookup).pack(side=tk.LEFT)

        self._state_box = tk.LabelFrame(
            self.root,
            text=" STATE ",
            font=("", 10, "bold"),
            bg=_STATE_BG,
            fg=_STATE_FG,
            padx=10,
            pady=8,
        )
        self._state_box.pack(fill=tk.BOTH, expand=True, **pad)

        self._state_inner = tk.Frame(self._state_box, bg=_STATE_BG)
        self._state_inner.pack(fill=tk.BOTH, expand=True)

    def _update_state_rows(self, rows: list[str]):
        while len(self._state_labels) < len(rows):
            lbl = tk.Label(
                self._state_inner,
                text="",
                bg=_STATE_BG,
                fg=_STATE_FG,
                font=("Consolas", 11),
                anchor=tk.W,
            )
            lbl.pack(fill=tk.X, pady=1)
            self._state_labels.append(lbl)
        while len(self._state_labels) > len(rows):
            lbl = self._state_labels.pop()
            lbl.destroy()
        for lbl, text in zip(self._state_labels, rows):
            lbl.config(text=text)

    def _parse_state_index(self):
        raw = self._state_var.get().strip()
        if not raw:
            raise ValueError("Nhập số state.")
        value = int(raw)
        if value < 0 or value >= N_ROWS:
            raise ValueError("State phải từ 0 đến %d." % (N_ROWS - 1))
        return value

    def _lookup(self):
        try:
            state_index = self._parse_state_index()
            rows = format_state_rows(state_index)
        except ValueError as exc:
            messagebox.showerror("State", str(exc))
            return
        self._update_state_rows(rows)

    def run(self):
        self.root.mainloop()


def main():
    StateLookupApp().run()


if __name__ == "__main__":
    main()
