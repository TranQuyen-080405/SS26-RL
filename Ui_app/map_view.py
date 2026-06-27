"""
Vẽ sim_map + robot + đường đi (dùng cho infer visualization).
"""

import tkinter as tk
from tkinter import ttk

from RL_lib.grid import neighbor_xy, is_valid

CELL = 44
MARGIN = 24

_DIR_ARROW = {"N": (0, -10), "E": (10, 0), "S": (0, 10), "W": (-10, 0)}


class SimMapCanvas:
    def __init__(self, parent):
        self.frame = ttk.Frame(parent)
        self.canvas = tk.Canvas(self.frame, bg="#1e1e2e", highlightthickness=0)
        self.canvas.pack(fill=tk.BOTH, expand=True)

        self.sim_map = None
        self.walls = set()
        self.path = []
        self.robot_pos = None
        self.robot_dir = "N"
        self.step_info = ""

        self.info_var = tk.StringVar(value="Chọn map infer và bấm Run.")
        ttk.Label(self.frame, textvariable=self.info_var, anchor=tk.W).pack(fill=tk.X, pady=(4, 0))

    def pack(self, **kwargs):
        self.frame.pack(**kwargs)

    def pack_forget(self):
        self.frame.pack_forget()

    def cell_px(self, x, y):
        h = self.sim_map["height"]
        px = MARGIN + x * CELL
        py = MARGIN + (h - 1 - y) * CELL
        return px, py

    def cell_center(self, x, y):
        px, py = self.cell_px(x, y)
        return px + CELL // 2, py + CELL // 2

    def load_sim_map(self, sim_map):
        self.sim_map = sim_map
        self.walls = set()
        src = sim_map.get("source") or {}
        for w in src.get("walls") or []:
            self.walls.add((int(w["x"]), int(w["y"]), w["dir"]))
        if not self.walls:
            for key in sim_map.get("walls") or {}:
                if sim_map["walls"][key]:
                    self.walls.add(key)
        self.path = []
        sx, sy = sim_map["start"]
        self.robot_pos = (sx, sy)
        self.robot_dir = "N"
        self.redraw()

    def reset_path(self):
        self.path = []
        if self.sim_map:
            sx, sy = self.sim_map["start"]
            self.robot_pos = (sx, sy)
            self.robot_dir = "N"
        self.redraw()

    def show_step(self, entry, status_text=""):
        if entry:
            self.robot_pos = (entry.get("nx", entry["x"]), entry.get("ny", entry["y"]))
            self.robot_dir = entry.get("ndirect", entry["direct"])
            if entry["action"] == "forward" and entry.get("result", {}).get("moved"):
                self.path.append(self.robot_pos)
            step = entry["step"]
            act = entry["action"]
            x, y = entry["x"], entry["y"]
            d = entry["direct"]
            self.step_info = "Step %d | (%d,%d) %s → %s" % (step, x, y, d, act)
            if status_text:
                self.info_var.set(status_text)
            else:
                self.info_var.set(self.step_info)
        self.redraw()

    def set_status(self, text):
        self.info_var.set(text)

    def _edge_valid(self, x, y, d):
        w, h = self.sim_map["width"], self.sim_map["height"]
        if not is_valid(x, y, w, h):
            return False
        nx, ny = neighbor_xy(x, y, d)
        return is_valid(nx, ny, w, h)

    def redraw(self):
        c = self.canvas
        c.delete("all")
        if not self.sim_map:
            return

        w, h = self.sim_map["width"], self.sim_map["height"]
        cw = max(w * CELL + 2 * MARGIN, 200)
        ch = max(h * CELL + 2 * MARGIN, 200)
        c.config(scrollregion=(0, 0, cw, ch))

        start = tuple(self.sim_map["start"])
        goal = tuple(self.sim_map["goal"])
        cps = {tuple(cp) for cp in self.sim_map.get("checkpoints") or []}

        for y in range(h):
            for x in range(w):
                px, py = self.cell_px(x, y)
                fill = "#313244"
                if (x, y) == start:
                    fill = "#a6e3a1"
                elif (x, y) == goal:
                    fill = "#f38ba8"
                elif (x, y) in cps:
                    fill = "#f9e2af"
                c.create_rectangle(px, py, px + CELL, py + CELL, fill=fill, outline="#45475a", width=1)
                c.create_text(px + CELL // 2, py + CELL // 2, text="%d,%d" % (x, y), fill="#6c7086", font=("", 7))

        for y in range(h):
            for x in range(w):
                px, py = self.cell_px(x, y)
                for d, x1, y1, x2, y2 in [
                    ("N", px, py, px + CELL, py),
                    ("E", px + CELL, py, px + CELL, py + CELL),
                    ("S", px, py + CELL, px + CELL, py + CELL),
                    ("W", px, py, px, py + CELL),
                ]:
                    if not self._edge_valid(x, y, d):
                        c.create_line(x1, y1, x2, y2, fill="#11111b", width=4)
                        continue
                    key = (x, y, d)
                    color = "#f38ba8" if key in self.walls else "#585b70"
                    width = 5 if key in self.walls else 2
                    c.create_line(x1, y1, x2, y2, fill=color, width=width)

        if self.path:
            pts = [self.cell_center(*self.sim_map["start"])]
            for x, y in self.path:
                pts.append(self.cell_center(x, y))
            for i in range(len(pts) - 1):
                c.create_line(pts[i][0], pts[i][1], pts[i + 1][0], pts[i + 1][1], fill="#89b4fa", width=3)

        if self.robot_pos:
            rx, ry = self.robot_pos
            cx, cy = self.cell_center(rx, ry)
            r = CELL // 4
            c.create_oval(cx - r, cy - r, cx + r, cy + r, fill="#cba6f7", outline="#cdd6f4", width=2)
            dx, dy = _DIR_ARROW.get(self.robot_dir, (0, -10))
            c.create_line(cx, cy, cx + dx, cy + dy, fill="#1e1e2e", width=3, arrow=tk.LAST, arrowshape=(8, 10, 4))
