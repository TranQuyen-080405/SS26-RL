"""
Vẽ sim_map + robot + đường đi (dùng cho infer visualization).
Scale ô map vừa khung canvas — cùng phương thức với create_map_UI.
"""

import tkinter as tk
from tkinter import ttk

from RL_lib.grid import neighbor_xy, is_valid

CELL_MIN = 36
CELL_MAX = 80
CANVAS_PAD = 28

_TAG_STATIC = "static"
_TAG_DYNAMIC = "dynamic"


class SimMapCanvas:
    def __init__(self, parent):
        self.frame = ttk.Frame(parent)
        self.canvas = tk.Canvas(self.frame, bg="#1e1e2e", highlightthickness=0)
        self.canvas.pack(fill=tk.BOTH, expand=True)
        self.canvas.bind("<Configure>", self._on_canvas_configure)

        self.sim_map = None
        self.walls = set()
        self.path = []
        self.robot_pos = None
        self.robot_dir = "N"
        self.step_info = ""
        self._cell = 52
        self._offset_x = CANVAS_PAD
        self._offset_y = CANVAS_PAD
        self._layout_key = None
        self._map_fingerprint = None
        self._canvas_size = (0, 0)
        self._configure_after = None
        self._last_visited_cps = set()

        self.info_var = tk.StringVar(value="Chọn map infer và bấm Run.")
        ttk.Label(self.frame, textvariable=self.info_var, anchor=tk.W).pack(fill=tk.X, pady=(4, 0))

    def pack(self, **kwargs):
        self.frame.pack(**kwargs)

    def pack_forget(self):
        self.frame.pack_forget()

    def _on_canvas_configure(self, event):
        if event.widget is not self.canvas:
            return
        size = (event.width, event.height)
        if size[0] < 2 or size[1] < 2 or size == self._canvas_size:
            return
        self._canvas_size = size
        self._layout_key = None
        if self._configure_after is not None:
            self.canvas.after_cancel(self._configure_after)
        self._configure_after = self.canvas.after(80, self._redraw_after_resize)

    def _redraw_after_resize(self):
        self._configure_after = None
        self.redraw()

    @staticmethod
    def _fingerprint(sim_map):
        walls = sim_map.get("walls") or {}
        if isinstance(walls, dict):
            w_sig = tuple(sorted(k for k, v in walls.items() if v))
        else:
            w_sig = ()
        return (
            sim_map.get("name"),
            sim_map["width"],
            sim_map["height"],
            tuple(sim_map.get("start") or ()),
            tuple(sim_map.get("goal") or ()),
            w_sig,
        )

    def cell_px(self, x, y):
        h = self.sim_map["height"]
        px = self._offset_x + x * self._cell
        py = self._offset_y + (h - 1 - y) * self._cell
        return px, py

    def cell_center(self, x, y):
        px, py = self.cell_px(x, y)
        return px + self._cell // 2, py + self._cell // 2

    def _update_layout(self):
        """Scale ô map vừa canvas và căn giữa. Trả True nếu layout đổi."""
        c = self.canvas
        if not self.sim_map:
            cw = max(c.winfo_width(), 200)
            ch = max(c.winfo_height(), 200)
            key = (cw, ch, 0, 0, 0)
            if key != self._layout_key:
                c.config(scrollregion=(0, 0, cw, ch))
                self._layout_key = key
                return True
            return False

        w = self.sim_map["width"]
        h = self.sim_map["height"]
        cw = max(c.winfo_width(), 320)
        ch = max(c.winfo_height(), 280)
        if cw <= 1 or ch <= 1:
            c.update_idletasks()
            cw = max(c.winfo_width(), 320)
            ch = max(c.winfo_height(), 280)

        avail_w = max(cw - 2 * CANVAS_PAD, w * CELL_MIN)
        avail_h = max(ch - 2 * CANVAS_PAD, h * CELL_MIN)
        cell = int(min(avail_w / w, avail_h / h, CELL_MAX))
        self._cell = max(cell, CELL_MIN)
        map_w = w * self._cell
        map_h = h * self._cell
        self._offset_x = max(CANVAS_PAD, (cw - map_w) // 2)
        self._offset_y = max(CANVAS_PAD, (ch - map_h) // 2)

        key = (cw, ch, self._cell, self._offset_x, self._offset_y, w, h)
        changed = key != self._layout_key
        if changed:
            c.config(scrollregion=(0, 0, cw, ch))
            self._layout_key = key
        return changed

    def load_sim_map(self, sim_map):
        fp = self._fingerprint(sim_map)
        if fp == self._map_fingerprint and self.sim_map is not None:
            return
        self._map_fingerprint = fp
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
        self._layout_key = None
        self.redraw()

    def reset_path(self):
        self.path = []
        if self.sim_map:
            sx, sy = self.sim_map["start"]
            self.robot_pos = (sx, sy)
            self.robot_dir = "N"
        self._redraw_dynamic()

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
        self._redraw_dynamic()

    def set_status(self, text):
        self.info_var.set(text)

    def _edge_valid(self, x, y, d):
        w, h = self.sim_map["width"], self.sim_map["height"]
        if not is_valid(x, y, w, h):
            return False
        nx, ny = neighbor_xy(x, y, d)
        return is_valid(nx, ny, w, h)

    @staticmethod
    def _draw_edge_wall(c, d, px, py, cell, thick, blocked=False):
        half = max(2, thick // 2)
        inset = max(2, cell // 18)
        x0, x1 = px + inset, px + cell - inset
        y0, y1 = py + inset, py + cell - inset
        if d == "N":
            coords = (x0, py - half, x1, py + half)
        elif d == "S":
            coords = (x0, py + cell - half, x1, py + cell + half)
        elif d == "W":
            coords = (px - half, y0, px + half, y1)
        else:
            coords = (px + cell - half, y0, px + cell + half, y1)
        if blocked:
            c.create_rectangle(*coords, fill="#e64566", outline="#ffccd5", width=1, tags=(_TAG_STATIC,))
        else:
            c.create_rectangle(*coords, fill="#0a0a0f", outline="#313244", width=1, tags=(_TAG_STATIC,))

    def _draw_static(self):
        c = self.canvas
        cell = self._cell
        font_sz = max(8, min(12, cell // 5))
        blocked_thick = max(6, min(10, cell // 9))
        open_w = max(2, min(3, cell // 18))
        border_thick = max(6, min(9, cell // 10))

        w, h = self.sim_map["width"], self.sim_map["height"]
        start = tuple(self.sim_map["start"])
        goal = tuple(self.sim_map["goal"])
        cps = {tuple(cp) for cp in self.sim_map.get("checkpoints") or []}

        visited_cps = {cp for cp in cps if cp in self.path or cp == self.robot_pos}
        self._last_visited_cps = visited_cps

        for y in range(h):
            for x in range(w):
                px, py = self.cell_px(x, y)
                fill = "#313244"
                if (x, y) == start:
                    fill = "#a6e3a1"
                elif (x, y) == goal:
                    fill = "#f38ba8"
                elif (x, y) in cps:
                    if (x, y) in visited_cps:
                        fill = "#89dceb"
                    else:
                        fill = "#f9e2af"
                c.create_rectangle(
                    px, py, px + cell, py + cell,
                    fill=fill, outline="#45475a", width=1, tags=(_TAG_STATIC,),
                )
                c.create_text(
                    px + cell // 2,
                    py + cell // 2,
                    text="%d,%d" % (x, y),
                    fill="#6c7086",
                    font=("", font_sz),
                    tags=(_TAG_STATIC,),
                )

        for y in range(h):
            for x in range(w):
                px, py = self.cell_px(x, y)
                for d, x1, y1, x2, y2 in [
                    ("N", px, py, px + cell, py),
                    ("E", px + cell, py, px + cell, py + cell),
                    ("S", px, py + cell, px + cell, py + cell),
                    ("W", px, py, px, py + cell),
                ]:
                    if not self._edge_valid(x, y, d):
                        self._draw_edge_wall(c, d, px, py, cell, border_thick, blocked=False)
                        continue
                    key = (x, y, d)
                    if key in self.walls:
                        self._draw_edge_wall(c, d, px, py, cell, blocked_thick, blocked=True)
                    else:
                        c.create_line(x1, y1, x2, y2, fill="#56586e", width=open_w, tags=(_TAG_STATIC,))

    def _draw_dynamic(self):
        c = self.canvas
        if not self.sim_map:
            return
        cell = self._cell

        if self.path:
            pts = [self.cell_center(*self.sim_map["start"])]
            for x, y in self.path:
                pts.append(self.cell_center(x, y))
            path_w = max(2, min(4, cell // 14))
            for i in range(len(pts) - 1):
                c.create_line(
                    pts[i][0], pts[i][1], pts[i + 1][0], pts[i + 1][1],
                    fill="#89b4fa", width=path_w, tags=(_TAG_DYNAMIC,),
                )

        if self.robot_pos:
            rx, ry = self.robot_pos
            cx, cy = self.cell_center(rx, ry)
            r = max(6, cell // 4)
            c.create_oval(
                cx - r, cy - r, cx + r, cy + r,
                fill="#cba6f7", outline="#cdd6f4", width=2, tags=(_TAG_DYNAMIC,),
            )
            arrow_len = max(8, cell // 4)
            dirs = {"N": (0, -arrow_len), "E": (arrow_len, 0), "S": (0, arrow_len), "W": (-arrow_len, 0)}
            dx, dy = dirs.get(self.robot_dir, (0, -arrow_len))
            arrow_w = max(2, cell // 16)
            c.create_line(
                cx, cy, cx + dx, cy + dy,
                fill="#1e1e2e", width=arrow_w,
                arrow=tk.LAST,
                arrowshape=(max(6, cell // 6), max(8, cell // 5), max(3, cell // 12)),
                tags=(_TAG_DYNAMIC,),
            )

    def _redraw_dynamic(self):
        if not self.sim_map:
            self.redraw()
            return
        layout_changed = self._update_layout()
        
        cps = {tuple(cp) for cp in self.sim_map.get("checkpoints") or []}
        visited_cps = {cp for cp in cps if cp in self.path or cp == self.robot_pos}
        visited_changed = visited_cps != getattr(self, "_last_visited_cps", set())
        
        if layout_changed or visited_changed or not self.canvas.find_withtag(_TAG_STATIC):
            self.canvas.delete(_TAG_STATIC)
            self._draw_static()
        self.canvas.delete(_TAG_DYNAMIC)
        self._draw_dynamic()

    def redraw(self):
        if not self.sim_map:
            c = self.canvas
            c.delete(_TAG_STATIC)
            c.delete(_TAG_DYNAMIC)
            self._update_layout()
            return
        self._redraw_dynamic()
