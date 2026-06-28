"""Map 5×5 tương tác — đặt robot, goal, CP, tường."""

import tkinter as tk
from tkinter import ttk

from RL_lib.grid import neighbor_xy, is_valid

CELL = 52
MARGIN = 22
_DIR_ARROW = {"N": (0, -11), "E": (11, 0), "S": (0, 11), "W": (-11, 0)}


class LabScenarioMap5:
    def __init__(self, parent, world, on_change=None):
        self.world = world
        self.on_change = on_change
        self.frame = ttk.LabelFrame(parent, text="Kịch bản 5×5", padding=6)
        self.frame.pack(fill=tk.BOTH, expand=True)

        tools = ttk.Frame(self.frame)
        tools.pack(fill=tk.X, pady=(0, 6))
        self._tool = tk.StringVar(value="robot")
        for val, label in (
            ("robot", "Robot"),
            ("goal", "Goal"),
            ("cp", "Checkpoint"),
            ("wall", "Tường (click cạnh)"),
        ):
            ttk.Radiobutton(tools, text=label, variable=self._tool, value=val).pack(side=tk.LEFT, padx=4)
        ttk.Button(tools, text="Reset map", command=self._reset).pack(side=tk.RIGHT, padx=4)

        self.canvas = tk.Canvas(self.frame, bg="#1e1e2e", highlightthickness=0, cursor="crosshair")
        self.canvas.pack()
        self.canvas.bind("<Button-1>", self._on_click)

        act_row = ttk.Frame(self.frame)
        act_row.pack(fill=tk.X, pady=8)
        ttk.Label(act_row, text="Di chuyển:").pack(side=tk.LEFT, padx=(0, 8))
        ttk.Button(act_row, text="Forward", command=lambda: self._action("forward")).pack(side=tk.LEFT, padx=3)
        ttk.Button(act_row, text="Rotate trái", command=lambda: self._action("rotate left")).pack(side=tk.LEFT, padx=3)
        ttk.Button(act_row, text="Rotate phải", command=lambda: self._action("rotate right")).pack(side=tk.LEFT, padx=3)

        self.result_var = tk.StringVar(value="Đặt robot / goal / CP / tường → bấm action.")
        ttk.Label(
            self.frame,
            textvariable=self.result_var,
            justify=tk.LEFT,
            wraplength=420,
            font=("Consolas", 9),
        ).pack(fill=tk.X, pady=(4, 0))

        self.redraw()

    def _reset(self):
        self.world.reset_scenario()
        self.redraw()
        self._notify()

    def _action(self, name):
        if self.on_change:
            self.on_change(name)

    def _notify(self):
        if self.on_change:
            self.on_change(None)

    def set_result_text(self, text):
        self.result_var.set(text)

    def _size(self):
        w = h = self.world.sim_map["width"]
        return w, h, w * CELL + 2 * MARGIN, h * CELL + 2 * MARGIN

    def _cell_px(self, x, y):
        _, h, _, _ = self._size()
        return MARGIN + x * CELL, MARGIN + (h - 1 - y) * CELL

    def _cell_center(self, x, y):
        px, py = self._cell_px(x, y)
        return px + CELL // 2, py + CELL // 2

    def _pick_cell(self, px, py):
        _, h, _, _ = self._size()
        x = int((px - MARGIN) // CELL)
        y = h - 1 - int((py - MARGIN) // CELL)
        w = self.world.sim_map["width"]
        if is_valid(x, y, w, h):
            return x, y
        return None

    def _pick_edge(self, px, py):
        w, h, _, _ = self._size()
        best = None
        best_d = 999
        for y in range(h):
            for x in range(w):
                for d, x1, y1, x2, y2 in self._edge_lines(x, y):
                    dseg = self._point_seg_dist(px, py, x1, y1, x2, y2)
                    if dseg < best_d and dseg < 12:
                        best_d = dseg
                        best = (x, y, d)
        return best

    def _edge_lines(self, x, y):
        px, py = self._cell_px(x, y)
        return [
            ("N", px, py, px + CELL, py),
            ("E", px + CELL, py, px + CELL, py + CELL),
            ("S", px, py + CELL, px + CELL, py + CELL),
            ("W", px, py, px, py + CELL),
        ]

    @staticmethod
    def _point_seg_dist(px, py, x1, y1, x2, y2):
        dx, dy = x2 - x1, y2 - y1
        if dx == dy == 0:
            return ((px - x1) ** 2 + (py - y1) ** 2) ** 0.5
        t = max(0, min(1, ((px - x1) * dx + (py - y1) * dy) / (dx * dx + dy * dy)))
        qx, qy = x1 + t * dx, y1 + t * dy
        return ((px - qx) ** 2 + (py - qy) ** 2) ** 0.5

    def _on_click(self, event):
        tool = self._tool.get()
        if tool == "wall":
            edge = self._pick_edge(event.x, event.y)
            if edge:
                self.world.toggle_wall(*edge)
        else:
            cell = self._pick_cell(event.x, event.y)
            if not cell:
                return
            x, y = cell
            if tool == "robot":
                self.world.place_robot(x, y)
            elif tool == "goal":
                self.world.place_goal(x, y)
            elif tool == "cp":
                self.world.place_checkpoint(x, y)
        self.redraw()
        self._notify()

    def redraw(self):
        c = self.canvas
        c.delete("all")
        sim = self.world.sim_map
        w, h, cw, ch = self._size()
        c.config(width=cw, height=ch, scrollregion=(0, 0, cw, ch))
        goal = tuple(sim.get("goal") or (4, 4))
        cps = [tuple(p) for p in (sim.get("checkpoints") or [])]
        walls = self.world.walls_set()
        rx, ry = self.world.robot["x"], self.world.robot["y"]
        rd = self.world.robot["direct"]

        for y in range(h):
            for x in range(w):
                px, py = self._cell_px(x, y)
                fill = "#313244"
                if (x, y) == goal:
                    fill = "#f38ba8"
                elif (x, y) in cps:
                    fill = "#f9e2af"
                c.create_rectangle(px, py, px + CELL, py + CELL, fill=fill, outline="#45475a")

        for y in range(h):
            for x in range(w):
                px, py = self._cell_px(x, y)
                for d, x1, y1, x2, y2 in self._edge_lines(x, y):
                    nx, ny = neighbor_xy(x, y, d)
                    if not is_valid(nx, ny, w, h):
                        c.create_line(x1, y1, x2, y2, fill="#11111b", width=4)
                        continue
                    key = (x, y, d)
                    if key in walls:
                        c.create_line(x1, y1, x2, y2, fill="#f38ba8", width=5)

        rcx, rcy = self._cell_center(rx, ry)
        r = CELL // 5
        c.create_oval(rcx - r, rcy - r, rcx + r, rcy + r, fill="#cba6f7", outline="#cdd6f4", width=2)
        dx, dy = _DIR_ARROW.get(rd, (0, -11))
        c.create_line(rcx, rcy, rcx + dx, rcy + dy, fill="#1e1e2e", width=3, arrow=tk.LAST)
